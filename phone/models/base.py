import math

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from phone.managers import SoftDeleteManager
from phone.utils import UniqueFilePathGenerator


def get_int_or_zero(value):
    if value is None:
        return 0
    if isinstance(value, float) and math.isnan(value):
        return 0
    return int(value)


class SoftDeleteModel(models.Model):
    """
    Abstract model to add soft delete functionality.
    """

    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    objects = SoftDeleteManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["created_at"]),
        ]
        default_manager_name = "objects"
        base_manager_name = "objects"

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        return super().delete()


class SoftDeleteImageModel(SoftDeleteModel):
    image = models.ImageField(
        upload_to=UniqueFilePathGenerator("images/"), null=True, blank=True
    )

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)
