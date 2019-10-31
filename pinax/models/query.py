from django.db.models.query import QuerySet

from . import settings as app_settings
from .deletion import LogicalDeleteCollector


class LogicalDeleteQuerySet(QuerySet):
    filter_key = '{field_name}__isnull'.format(
        field_name=app_settings.FIELD_NAME
    )

    def deleted(self):
        """Custom filter for retrieving deleted objects only"""
        return self.filter(**{self.filter_key: False})

    def not_deleted(self):
        """Custom filter for retrieving not deleted objects only"""
        return self.filter(**{self.filter_key: True})

    def delete(self, hard_delete=False):
        """Delete objects in queryset.

        Args:
            hard_delete(bool): force hard object deletion
        """
        if hard_delete:
            return self.hard_delete()
        msg = 'Cannot use "limit" or "offset" with delete.'
        assert self.query.can_filter(), msg
        for obj in self.all():
            obj.delete()
        self._result_cache = None
    delete.alters_data = True

    def hard_delete(self):
        """Method to hard delete object.

        This is the original `delete()` method from ``QuerySet`` class, but
        with using of ``LogicalDeleteCollector`` instead of ``Collector``.

        """
        return super().delete()
