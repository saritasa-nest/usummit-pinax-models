from functools import partial

from django import forms
from django.contrib import admin
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.contrib.admin.utils import flatten_fieldsets, unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import modelform_defines_fields, inlineformset_factory
from django.utils.encoding import force_str
from django.utils.text import get_text_list
from django.utils.translation import gettext_lazy as _

from .utils import get_logical_deleted_objects
from .deletion import LogicalDeleteNestedObjects


class LogicalDeleteModelAdmin(admin.ModelAdmin):
    """
    A base model admin to use in providing access to to logically deleted
    objects.
    """
    list_display = ("id", "__unicode__", "active")
    list_display_filter = ("active",)

    def queryset(self, request):
        qs = self.model._default_manager.all_with_deleted()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class LogicalDeleteViewMixin:
    """Mixin for ``ModelAdmin`` classes with custom `delete_view`.

    This mixin is used to correctly process deleting relations using Django
    admin. Mixin uses custom method with custom ``Collector`` class that
    collects objects that should be deleted - now it excludes
    soft-deleted objects.

    """

    def get_deleted_objects(self, objs, request):
        """Specify custom function for getting deleted objects.

        Django provides this hook for customizing the delete process for the
        delete view and the "delete selected" action.

        """
        return get_logical_deleted_objects(objs, request, self.admin_site)


class LogicalDeleteInlineMixin(object):
    """Mixin for ``InlineModelAdmin`` with custom `get_formset`.

    This mixin is used to correctly process deleting relations using Django
    CMS. Mixin uses custom method with custom ``Collector`` class that collects
    objects that should be deleted - now it excludes soft-deleted objects.

    """

    def get_formset(self, request, obj=None, **kwargs):
        """Custom `get_formset` method.

        This is the original `get_formset` method that uses custom
        ``LogicalDeleteNestedObjects`` collector class instead of original
        ``NestedObjects`` class.

        """
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        excluded = self.get_exclude(request, obj)
        exclude = [] if excluded is None else list(excluded)
        exclude.extend(self.get_readonly_fields(request, obj))
        if excluded is None and hasattr(self.form, '_meta') and self.form._meta.exclude:
            # Take the custom ModelForm's Meta.exclude into account only if the
            # InlineModelAdmin doesn't define its own.
            exclude.extend(self.form._meta.exclude)
        # If exclude is an empty list we use None, since that's the actual
        # default.
        exclude = exclude or None
        can_delete = self.can_delete and self.has_delete_permission(request, obj)
        defaults = {
            "form": self.form,
            "formset": self.formset,
            "fk_name": self.fk_name,
            "fields": fields,
            "exclude": exclude,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            "extra": self.get_extra(request, obj, **kwargs),
            "min_num": self.get_min_num(request, obj, **kwargs),
            "max_num": self.get_max_num(request, obj, **kwargs),
            "can_delete": can_delete,
        }

        defaults.update(kwargs)
        base_model_form = defaults['form']

        class DeleteProtectedModelForm(base_model_form):
            def hand_clean_DELETE(self):
                """
                We don't validate the 'DELETE' field itself because on
                templates it's not rendered using the field information, but
                just using a generic "deletion_field" of the InlineModelAdmin.
                """
                if self.cleaned_data.get(DELETION_FIELD_NAME, False):
                    using = router.db_for_write(self._meta.model)
                    collector = LogicalDeleteNestedObjects(using=using)
                    if self.instance.pk is None:
                        return
                    collector.collect([self.instance])
                    if collector.protected:
                        objs = []
                        for p in collector.protected:
                            objs.append(
                                # Translators: Model verbose name and instance representation,
                                # suitable to be an item in a list.
                                _('%(class_name)s %(instance)s') % {
                                    'class_name': p._meta.verbose_name,
                                    'instance': p}
                            )
                        params = {'class_name': self._meta.model._meta.verbose_name,
                                  'instance': self.instance,
                                  'related_objects': get_text_list(objs, _('and'))}
                        msg = _("Deleting %(class_name)s %(instance)s would require "
                                "deleting the following protected related objects: "
                                "%(related_objects)s")
                        raise ValidationError(msg, code='deleting_protected', params=params)

            def is_valid(self):
                result = super(DeleteProtectedModelForm, self).is_valid()
                self.hand_clean_DELETE()
                return result

        defaults['form'] = DeleteProtectedModelForm

        if defaults['fields'] is None and not modelform_defines_fields(defaults['form']):
            defaults['fields'] = forms.ALL_FIELDS

        return inlineformset_factory(self.parent_model, self.model, **defaults)
