import django.db.models.deletion
import logging
import phone.utils
from django.db import migrations, models
from django.contrib.postgres.fields import ArrayField

logger = logging.getLogger(__name__)


class Migration(migrations.Migration):

    dependencies = [
        ("phone", "0068_drop_partner_card_data"),
    ]

    operations = [
        # 1. CardIssuer 신규 모델 생성
        migrations.CreateModel(
            name="CardIssuer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=50, unique=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "abstract": False,
                "base_manager_name": "objects",
                "default_manager_name": "objects",
                "indexes": [
                    models.Index(
                        fields=["created_at"], name="phone_cardi_created_5c6d18_idx"
                    )
                ],
            },
        ),
        # 2. PartnerCard 기존 필드 제거 (carrier, benefit_type, contact, link)
        migrations.RemoveField(
            model_name="partnercard",
            name="carrier",
        ),
        migrations.RemoveField(
            model_name="partnercard",
            name="benefit_type",
        ),
        migrations.RemoveField(
            model_name="partnercard",
            name="contact",
        ),
        migrations.RemoveField(
            model_name="partnercard",
            name="link",
        ),
        # 3. PartnerCard name 필드 변경 (null 제거)
        migrations.AlterField(
            model_name="partnercard",
            name="name",
            field=models.CharField(max_length=100),
        ),
        # 4. PartnerCard image 필드 변경 (upload_to 경로 변경)
        migrations.AlterField(
            model_name="partnercard",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=phone.utils.UniqueFilePathGenerator("partner_cards/"),
            ),
        ),
        # 5. PartnerCard 신규 필드 추가
        migrations.AddField(
            model_name="partnercard",
            name="issuer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cards",
                to="phone.cardissuer",
            ),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="carriers",
            field=ArrayField(
                models.CharField(
                    choices=[
                        ("SK", "SK"),
                        ("KT", "KT"),
                        ("LG", "LG"),
                        ("알뜰폰", "알뜰폰"),
                    ],
                    max_length=20,
                ),
                default=list,
            ),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="discount_types",
            field=ArrayField(
                models.CharField(
                    choices=[
                        ("할부", "할부"),
                        ("무선청구", "무선청구"),
                        ("유선청구", "유선청구"),
                    ],
                    max_length=20,
                ),
                default=list,
            ),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="signup_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="signup_end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="add_discount_months",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="add_discount_condition",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="min_installment_amount",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="installment_excluded_items",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="partnercard",
            name="annual_fee",
            field=models.IntegerField(default=0),
        ),
        # 6. PartnerCard Meta 옵션 갱신 (default_manager_name 옵션 제거)
        migrations.AlterModelOptions(
            name="partnercard",
            options={
                "base_manager_name": "objects",
                "default_manager_name": "objects",
            },
        ),
        # 7. CardBenefit 기존 필드 제거 (condition, benefit_price, is_optional)
        migrations.RemoveField(
            model_name="cardbenefit",
            name="condition",
        ),
        migrations.RemoveField(
            model_name="cardbenefit",
            name="benefit_price",
        ),
        migrations.RemoveField(
            model_name="cardbenefit",
            name="is_optional",
        ),
        # 8. CardBenefit 신규 필드 추가
        migrations.AddField(
            model_name="cardbenefit",
            name="kind",
            field=models.CharField(
                choices=[("basic", "기본할인"), ("additional", "추가할인")],
                default="basic",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="cardbenefit",
            name="threshold_amount",
            field=models.IntegerField(default=0, help_text="전월실적 기준 (원)"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="cardbenefit",
            name="amount",
            field=models.IntegerField(default=0, help_text="할인 금액 (원)"),
            preserve_default=False,
        ),
        # 9. CardBenefit Meta 옵션 갱신 (default_manager_name 옵션은 0067에서 설정됨, 유지)
        migrations.AlterModelOptions(
            name="cardbenefit",
            options={
                "base_manager_name": "objects",
                "default_manager_name": "objects",
            },
        ),
        # 10. CardAdditionalPromotion 신규 모델 생성
        migrations.CreateModel(
            name="CardAdditionalPromotion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=phone.utils.UniqueFilePathGenerator(
                            "card_promotions/"
                        ),
                    ),
                ),
                (
                    "card",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="additional_promotions",
                        to="phone.partnercard",
                    ),
                ),
                (
                    "target_series",
                    models.ManyToManyField(blank=True, to="phone.productseries"),
                ),
                ("min_installment_amount", models.IntegerField(blank=True, null=True)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("cashback_amount", models.IntegerField(blank=True, null=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "abstract": False,
                "base_manager_name": "objects",
                "default_manager_name": "objects",
            },
        ),
    ]
