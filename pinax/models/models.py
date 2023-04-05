from functools import reduce
from operator import or_

from django.core.exceptions import NON_FIELD_ERRORS
from django.db import models
from django.utils import timezone

from . import managers
from . import settings as app_settings
from .signals import post_softdelete, pre_softdelete
from .utils import get_collector, get_related_objects


class LogicalDeleteModel(models.Model):
    """
    This base model provides date fields and functionality to enable logical
    delete functionality in derived models.

    Field itself declared in the bottom of file
    """

    objects = managers.LogicalDeletedManager()

    def active(self):
        return getattr(self, app_settings.FIELD_NAME) is None
    active.boolean = True

    def delete(self, hard_delete=False, _collect_related=True):
        """Soft-delete the object.

        Args:
            hard_delete(bool): force hard object deletion
            _collect_related(bool): is deletion of this object requires to
                collect and delete some related objects.

        `_collect_related` used with cascade deletion. Just root object
        should collect related objects. If related objects will also start to
        collect realted objects we may fail into endless recursion
        """
        if hard_delete:
            return self.hard_delete()

        # Call pre_delete signals
        pre_softdelete.send(sender=self.__class__, instance=self)

        # Fetch related models
        if _collect_related:
            collector = get_collector(self)
            to_delete = get_related_objects(self, collector=collector)
        else:
            collector = None
            to_delete = []

        for obj in to_delete:
            if isinstance(obj, LogicalDeleteModel):
                # check if object is already deleted
                if not getattr(obj, app_settings.FIELD_NAME):
                    obj.delete(_collect_related=False)
            else:
                obj.delete()

        # Soft delete the object
        setattr(self, app_settings.FIELD_NAME, timezone.now())
        self.save()

        # Update related object fields (SET_NULL)
        if _collect_related and collector:
            for (field, value), instances_list in collector.field_updates.items():
                updates = []
                objs = []
                for instances in instances_list:
                    if (
                        isinstance(instances, models.QuerySet)
                        and instances._result_cache is None
                    ):
                        updates.append(instances)
                    else:
                        objs.extend(instances)
                if updates:
                    combined_updates = reduce(or_, updates)
                    combined_updates.update(**{field.name: value})
                if objs:
                    model = objs[0].__class__
                    query = models.sql.UpdateQuery(model)
                    query.update_batch(
                        [obj.pk for obj in instances],
                        {field.name: value},
                        collector.using
                    )

        post_softdelete.send(sender=self.__class__, instance=self)

    def hard_delete(self, using=None, keep_parents=False):
        """Method to hard delete object.

        This is the original `delete()` method from ``Model`` class, but
        with using of ``LogicalDeleteCollector`` instead of ``Collector``.

        """
        super().delete()

    class Meta:
        abstract = True

    def _perform_unique_checks(self, unique_checks):
        """This is overriden django model's method.

        It almost fully copy-pasted from django sources. Changed just
        line where filtered model objects
        """
        errors = {}

        for model_class, unique_check in unique_checks:
            # Try to look up an existing object with the same values as this
            # object's values for all the unique field.

            lookup_kwargs = {}
            for field_name in unique_check:
                f = self._meta.get_field(field_name)
                lookup_value = getattr(self, f.attname)
                if lookup_value is None:
                    # no value, skip the lookup
                    continue
                if f.primary_key and not self._state.adding:
                    # no need to check for unique primary key when editing
                    continue
                lookup_kwargs[str(field_name)] = lookup_value

            # some fields were skipped, no reason to do the check
            if len(unique_check) != len(lookup_kwargs):
                continue

            # Here are the changes
            qs = self._get_queryset_for_unique_checks(
                model_class, lookup_kwargs
            )

            # Exclude the current object from the query if we are editing an
            # instance (as opposed to creating a new one)
            # Note that we need to use the pk as defined by model_class, not
            # self.pk. These can be different fields because model inheritance
            # allows single model to have effectively multiple primary keys.
            # Refs #17615.
            model_class_pk = self._get_pk_val(model_class._meta)
            if not self._state.adding and model_class_pk is not None:
                qs = qs.exclude(pk=model_class_pk)
            if qs.exists():
                if len(unique_check) == 1:
                    key = unique_check[0]
                else:
                    key = NON_FIELD_ERRORS
                errors.setdefault(key, []).append(
                    self.unique_error_message(model_class, unique_check)
                )

        return errors

    def _get_queryset_for_unique_checks(self, model_class, lookup_kwargs):
        """Hook for inserting custom queryset for unique checks

        See docstring of ``_perform_unique_checks``
        """
        manager = model_class._default_manager
        if hasattr(manager, 'all_with_deleted'):
            qs = manager.all_with_deleted()
        else:
            qs = manager.all()
        return qs.filter(**lookup_kwargs)


# add field with deletion datetime to model with configurable name
LogicalDeleteModel.add_to_class(
    app_settings.FIELD_NAME,
    models.DateTimeField(null=True, blank=True, editable=False)
)
