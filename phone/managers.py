from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
