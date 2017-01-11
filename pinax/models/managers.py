from django.db import models

from . import settings as app_settings
from .query import LogicalDeleteQuerySet


class LogicalDeletedManager(models.Manager):
    """
    A manager that serves as the default manager for
    `pinax.models.LogicalDeleteModel` providing the filtering out of logically
    deleted objects. In addition, it provides named querysets for getting the
    deleted objects.
    """
    queryset_class = LogicalDeleteQuerySet

    filter_key = '{field_name}__isnull'.format(
        field_name=app_settings.FIELD_NAME
    )

    def __init__(self, queryset_class=None, *args, **kwargs):
        """Hook for setting custom queryset class
        """
        super(LogicalDeletedManager, self).__init__(*args, **kwargs)
        if queryset_class:
            self.queryset_class = queryset_class

    def all_with_deleted(self):
        if self.model:
            return self.queryset_class(self.model, using=self._db)

    def get_queryset(self):
        """Retrieve only not deleted objects
        """
        if self.model:
            return self.queryset_class(
                self.model, using=self._db).not_deleted()

    def only_deleted(self):
        if self.model:
            return self.queryset_class(self.model, using=self._db).deleted()

    def get(self, *args, **kwargs):
        if app_settings.ACCESSIBLE_BY_PK:
            queryset = self.all_with_deleted()
        else:
            queryset = self.get_queryset()
        return queryset.get(*args, **kwargs)

    def filter(self, *args, **kwargs):
        if "pk" in kwargs and app_settings.ACCESSIBLE_BY_PK:
            queryset = self.all_with_deleted()
        else:
            queryset = self.get_queryset()
        return queryset.filter(*args, **kwargs)
