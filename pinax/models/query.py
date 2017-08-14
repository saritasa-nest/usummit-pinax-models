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
        assert self.query.can_filter(), \
            "Cannot use 'limit' or 'offset' with delete."

        if self._fields is not None:
            raise TypeError(
                "Cannot call delete() after .values() or .values_list()"
            )

        del_query = self._clone()

        # The delete is actually 2 queries - one to find related objects,
        # and one to delete. Make sure that the discovery of related
        # objects is performed on the same database as the deletion.
        del_query._for_write = True

        # Disable non-supported fields.
        del_query.query.select_for_update = False
        del_query.query.select_related = False
        del_query.query.clear_ordering(force_empty=True)

        collector = LogicalDeleteCollector(using=del_query.db)
        collector.collect(del_query)
        deleted, _rows_count = collector.delete()

        # Clear the result cache, in case this QuerySet gets reused.
        self._result_cache = None
        return deleted, _rows_count
