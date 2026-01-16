from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    # 1. QuerySet 레벨의 delete (예: MyModel.objects.filter(...).delete())
    def delete(self):
        return super().update(deleted_at=timezone.now())

    # 2. 진짜 삭제가 필요할 때를 대비한 메서드
    def hard_delete(self):
        return super().delete()

    # 3. 삭제된 데이터만 조회하고 싶을 때 (선택 사항)
    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    # 4. 삭제되지 않은 데이터만 조회
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        # 기본적으로 삭제되지 않은 데이터만 반환하도록 설정
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    # Manager에서 직접 hard_delete를 호출할 수 있게 연결
    def hard_delete(self):
        return self.get_queryset().hard_delete()
