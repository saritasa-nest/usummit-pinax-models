from django.conf import settings


FIELD_NAME = getattr(settings, 'LOGICAL_DELETE_FIELD', 'date_removed')
