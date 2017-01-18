from django.db import models
from django.utils import timezone

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


# add field with deletion datetime to model with configurable name
LogicalDeleteModel.add_to_class(
    app_settings.FIELD_NAME,
    models.DateTimeField(null=True, blank=True, editable=False)
)
