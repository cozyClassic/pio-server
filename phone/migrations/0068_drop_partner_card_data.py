import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def drop_data(apps, schema_editor):
    """0067 → 0068 forward 시 PartnerCard / CardBenefit 모든 row 삭제.
    복구는 Step 0의 backup_data_*.sql로만 가능."""
    CardBenefit = apps.get_model("phone", "CardBenefit")
    PartnerCard = apps.get_model("phone", "PartnerCard")
    cb_deleted = CardBenefit.objects.all().delete()
    pc_deleted = PartnerCard.objects.all().delete()
    logger.info("0068: dropped CardBenefit=%s, PartnerCard=%s", cb_deleted, pc_deleted)


def reverse_noop(apps, schema_editor):
    """의도적 noop. 0068의 데이터 손실은 forward-only이며, 복원이 필요하면
    Step 0에서 생성한 pg_dump backup_data_*.sql 파일로 별도 복구해야 한다."""
    logger.warning("0068 reverse is noop. Use pg_dump backup to restore data.")


class Migration(migrations.Migration):

    dependencies = [
        ("phone", "0067_alter_cardbenefit_options_and_more"),
    ]

    operations = [
        migrations.RunPython(drop_data, reverse_noop),
    ]
