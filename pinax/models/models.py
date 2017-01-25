from django.db import models
from django.utils import timezone
from django.core.exceptions import NON_FIELD_ERRORS

from . import managers
from .utils import get_related_objects
from . import settings as app_settings


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

    def delete(self):
        # Fetch related models
        to_delete = get_related_objects(self)

        for obj in to_delete:
            # check that model is not inherited to avoid circular deletion
            if not issubclass(obj.__class__, self.__class__):
                obj.delete()

        # Soft delete the object
        setattr(self, app_settings.FIELD_NAME, timezone.now())
        self.save()

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
