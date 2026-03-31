from django.db import models
from tinymce import models as tinymce_models

from phone.constants import CarrierChoices
from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel, SoftDeleteImageModel
from .product import Product


class FAQ(SoftDeleteModel):
    category = models.CharField(max_length=100)
    question = models.TextField(max_length=255)
    answer = models.TextField()
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.question


class Notice(SoftDeleteModel):
    title = models.CharField(max_length=100)
    content = tinymce_models.HTMLField(default="", blank=True)
    type = models.CharField(
        max_length=25,
        choices=[("caution", "caution"), ("event", "event"), ("general", "general")],
        default="general",
    )

    def __str__(self):
        return self.title


class Banner(SoftDeleteImageModel):
    title = models.CharField(max_length=100, default="")
    image_pc = models.ImageField(
        upload_to=UniqueFilePathGenerator("banners/"), default=""
    )
    image_mobile = models.ImageField(
        upload_to=UniqueFilePathGenerator("banners/"), default=""
    )
    link = models.URLField(blank=True, null=True, help_text="배너 클릭 시 이동할 링크")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="배너 활성화 여부")
    sort_order_test = models.IntegerField(default=0)
    location = models.CharField(max_length=100, default="")

    def __str__(self):
        return self.title


class Review(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    customer_name = models.CharField(max_length=100)
    rating = models.IntegerField(default=0, help_text="Rating from 1 to 5")
    comment = models.TextField(blank=True, null=True)
    image = models.ImageField(
        upload_to=UniqueFilePathGenerator("review_images/"),
        blank=True,
        null=True,
        help_text="Review image",
    )
    is_public = models.BooleanField(default=False, help_text="Is the review public?")

    def __str__(self):
        return f"{self.customer_name} - {self.created_at}"


class PolicyDocument(SoftDeleteModel):
    document_type = models.CharField(
        choices=[
            ("terms", "이용약관"),
            ("privacy", "개인정보처리방침"),
        ],
        max_length=20,
        default="terms",
    )
    content = models.FileField(upload_to=UniqueFilePathGenerator("policy_documents/"))
    effective_date = models.DateField(help_text="Effective date of the policy")

    def __str__(self):
        return self.document_type


class PartnerCard(SoftDeleteImageModel):
    carrier = models.CharField(
        max_length=100, null=True, choices=CarrierChoices.CHOICES
    )
    benefit_type = models.CharField(max_length=100, null=True)
    name = models.CharField(max_length=100, null=True)
    contact = models.CharField(max_length=100, null=True)
    link = models.TextField()
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)


class CardBenefit(SoftDeleteModel):
    condition = models.CharField(max_length=255, null=True)
    benefit_price = models.IntegerField(default=0)
    card = models.ForeignKey(
        PartnerCard, on_delete=models.CASCADE, related_name="card_benefits"
    )
    is_optional = models.BooleanField(default=False)


class Event(SoftDeleteModel):
    title = models.CharField(max_length=100)
    thumbnail = models.ImageField(
        upload_to=UniqueFilePathGenerator("event_thumbnails/"), null=True, blank=True
    )
    description = tinymce_models.HTMLField(default="", blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class CustomImage(SoftDeleteImageModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
