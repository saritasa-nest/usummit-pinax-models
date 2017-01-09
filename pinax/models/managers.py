from django.db import models

from . import settings as app_settings
from .query import LogicalDeleteQuerySet


class LogicalDeletedManager(models.Manager):
    """
    A manager that serves as the default manager for `pinax.models.LogicalDeleteModel`
    providing the filtering out of logically deleted objects. In addition, it
    provides named querysets for getting the deleted objects.
    """
    filter_key = '{field_name}__isnull'.format(
        field_name=app_settings.FIELD_NAME
    )

    def get_queryset(self):
        if self.model:
            return LogicalDeleteQuerySet(self.model, using=self._db).filter(
                **{self.filter_key: True}
            )

    def all_with_deleted(self):
        if self.model:
            return super(LogicalDeletedManager, self).get_queryset()

    def only_deleted(self):
        if self.model:
            return super(LogicalDeletedManager, self).get_queryset().filter(
                **{self.filter_key: False}
            )

    def get(self, *args, **kwargs):
        return self.all_with_deleted().get(*args, **kwargs)

    def filter(self, *args, **kwargs):
        if "pk" in kwargs:
            return self.all_with_deleted().filter(*args, **kwargs)
        return self.get_queryset().filter(*args, **kwargs)
