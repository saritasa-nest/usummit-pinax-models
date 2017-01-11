from django.conf import settings


FIELD_NAME = getattr(
    settings,
    'LOGICAL_DELETE_FIELD',
    'date_removed'
)

# is deleted objects may be retrieved by PK using manager
ACCESSIBLE_BY_PK = getattr(
    settings,
    'LOGICAL_DELETE_ACCESSIBLE_BY_PK',
    True
)
