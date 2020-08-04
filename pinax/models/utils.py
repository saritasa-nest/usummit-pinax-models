# -*- coding: utf-8 -*-

import itertools

from django.contrib.admin.utils import quote
from django.contrib.auth import get_permission_codename
from django.db import DEFAULT_DB_ALIAS
from django.db.models.deletion import ProtectedError
from django.urls import NoReverseMatch, reverse
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.text import capfirst

from .deletion import LogicalDeleteNestedObjects


def get_collector(obj, using=DEFAULT_DB_ALIAS, collect=True):
    """Method to get collector with already collected or not related objects.

    Method uses ``LogicalDeleteNestedObjects`` instead of ``NestedObjects``
    class, that originally is used in `pinax-models`.

    It just makes initialization of a new collector and collects its related
    objects or not depending on `collect` flag.

    Attributes:
          obj (Model): object which related instances should be collected
          using (str): currently used DB alias
          collect (bool): flag if related objects should be collected

    Returns:
          (LogicalDeleteNestedObjects): collector instance with already
          collected objects

    """
    collector = LogicalDeleteNestedObjects(using=using)
    if collect:
        collector.collect([obj])
    return collector


def get_related_objects(obj, using=DEFAULT_DB_ALIAS, collector=None):
    """Method to get related objects.

    This code is based on https://github.com/makinacorpus/django-safedelete

    It forbids to delete object if it has protected related objects.

    """
    if not collector:
        collector = get_collector(obj, using)

    if collector.protected:
        raise ProtectedError(
            (
                'Cannot delete object "{obj}" as it has protected relations.'
                .format(obj=obj)
            ),
            list(collector.protected)
        )

    def flatten(elem):
        if isinstance(elem, list):
            return itertools.chain.from_iterable(map(flatten, elem))
        elif obj != elem:
            return (elem,)
        return ()

    return flatten(collector.nested())


def get_logical_deleted_objects(objs, opts, user, admin_site, using):
    """Custom `get_deleted_objects` function.

    This is the original `get_deleted_objects` function that uses custom
    ``LogicalDeleteNestedObjects`` collector class instead of original
    ``NestedObjects`` class.

    """
    collector = LogicalDeleteNestedObjects(using=using)
    collector.collect(objs)
    perms_needed = set()

    def format_callback(obj):
        has_admin = obj.__class__ in admin_site._registry
        opts = obj._meta

        no_edit_link = '%s: %s' % (capfirst(opts.verbose_name),
                                   force_text(obj))

        if has_admin:
            try:
                admin_url = reverse('%s:%s_%s_change'
                                    % (admin_site.name,
                                       opts.app_label,
                                       opts.model_name),
                                    None, (quote(obj._get_pk_val()),))
            except NoReverseMatch:
                # Change url doesn't exist -- don't display link to edit
                return no_edit_link

            p = '%s.%s' % (opts.app_label,
                           get_permission_codename('delete', opts))
            if not user.has_perm(p):
                perms_needed.add(opts.verbose_name)
            # Display a link to the admin page.
            return format_html('{}: <a href="{}">{}</a>',
                               capfirst(opts.verbose_name),
                               admin_url,
                               obj)
        else:
            # Don't display link to edit, because it either has no
            # admin or is edited inline.
            return no_edit_link

    to_delete = collector.nested(format_callback)

    protected = [format_callback(obj) for obj in collector.protected]
    model_count = {
        model._meta.verbose_name_plural: len(objs)
        for model, objs in collector.model_objs.items()
    }

    return to_delete, model_count, perms_needed, protected
