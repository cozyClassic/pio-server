from django.db import models

from django.utils import timezone
from django.db.models import QuerySet
from simple_history.models import HistoricalRecords
from threading import local
import pandas as pd

from mdeditor.fields import MDTextField

# Thread-local storage for tracking products that need updates
_thread_locals = local()


# Create your models here.
def get_int_or_zero(value):
    return 0 if value is None or pd.isna(value) else int(value)


class SoftDeleteModel(models.Model):
    """
    Abstract model to add soft delete functionality.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


class SoftDeleteImageModel(SoftDeleteModel):
    image = models.ImageField(upload_to="images/", null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)


class Plan(SoftDeleteModel):
    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=100)
    category_1 = models.CharField(max_length=100, help_text="e.g., 5G, LTE, 3G")
    category_2 = models.CharField(
        max_length=100, help_text="통신사 별 요금제 구분 (5GX, 0청년 등)"
    )
    description = models.CharField(
        max_length=255,
        help_text="Brief description of the plan",
        null=True,
        blank=True,
        default="",
    )
    price = models.IntegerField(default=0, help_text="Price in KRW")
    data_allowance = models.CharField(max_length=100, help_text="Data limit in MB")
    call_allowance = models.CharField(max_length=100, help_text="Call minutes limit")
    sms_allowance = models.CharField(max_length=100, help_text="sms_allowance limit")
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.carrier} / {self.name} - {self.price}"


class Device(SoftDeleteModel):
    model_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    series = models.CharField(
        max_length=100,
        help_text="e.g., 갤럭시 S, 아이폰, 갤럭시 Z",
        blank=True,
        default="",
    )

    def __str__(self):
        return f"{self.model_name}"


class DeviceColor(SoftDeleteModel):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="colors")
    color = models.CharField(max_length=50)
    color_code = models.CharField(
        max_length=7, help_text="Hex color code, e.g., #FFFFFF"
    )

    def __str__(self):
        return f"{self.color} / {self.device.model_name}"


class DevicesColorImage(SoftDeleteImageModel):
    device_color = models.ForeignKey(
        DeviceColor, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="device_color_images/")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return (
            f"image - {self.device_color.device.model_name}  {self.device_color.color}"
        )


class DeviceVariant(SoftDeleteModel):
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="variants"
    )
    storage_capacity = models.CharField(max_length=100)
    device_price = models.IntegerField(default=0, help_text="Price in KRW")

    def __str__(self):
        return f"{self.id}"

    # 가격이 업데이트 되면 연결된 product 옵션들도 가격을 업데이트해야 합니다.
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # DeviceVariant의 가격이 변경되면 연결된 ProductOption의 가격도 업데이트합니다.
        product_options: QuerySet[ProductOption] = self.product_options.filter(
            device_variant_id=self.id
        )

        for option in product_options:
            option.final_price = option._get_final_price()
            option.save()


class ProductOption(SoftDeleteModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="options"
    )
    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.CASCADE,
        related_name="product_options",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="product_options",
    )
    discount_type = models.CharField(
        max_length=50,
        choices=[
            ("공시지원금", "공시지원금"),
            ("선택약정", "선택약정"),
        ],
        default=("공시지원금", "공시지원금"),
    )
    contract_type = models.CharField(
        max_length=50,
        choices=[
            ("신규가입", "신규가입"),
            ("번호이동", "번호이동"),
            ("기기변경", "기기변경"),
        ],
        default=("기기변경", "기기변경"),
    )
    subsidy_amount = models.IntegerField(
        help_text="공시지원금",
        null=True,
        blank=True,
    )
    subsidy_amount_mnp = models.IntegerField(
        help_text="전환지원금",
        null=True,
        blank=True,
    )
    additional_discount = models.IntegerField(
        help_text="추가지원금",
        null=True,
        blank=True,
    )
    final_price = models.IntegerField(
        help_text="최종 가격",
        null=True,
        blank=True,
    )
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.id}"

    def _get_final_price(self):
        return self.calculate_final_price(
            device_price=self.device_variant.device_price,
            discount_type=self.discount_type,
            contract_type=self.contract_type,
            subsidy_amount=self.subsidy_amount,
            subsidy_amount_mnp=self.subsidy_amount_mnp,
            additional_discount=self.additional_discount,
        )

    def save(self, *args, **kwargs):
        self.final_price = self._get_final_price()
        super().save(*args, **kwargs)

    @classmethod
    def calculate_final_price(
        cls,
        device_price,
        discount_type,
        contract_type,
        subsidy_amount,
        subsidy_amount_mnp,
        additional_discount,
    ):
        final_price = get_int_or_zero(device_price) - get_int_or_zero(
            additional_discount
        )

        if discount_type == "공시지원금":
            final_price -= get_int_or_zero(subsidy_amount)
            if contract_type == "번호이동":
                final_price -= get_int_or_zero(subsidy_amount_mnp)

        return final_price

    @classmethod
    def _get_pending_products(cls):
        """현재 트랜잭션에서 업데이트가 필요한 제품들을 반환"""
        if not hasattr(_thread_locals, "pending_products"):
            _thread_locals.pending_products = set()
        return _thread_locals.pending_products

    @classmethod
    def _add_pending_product(cls, product_id):
        """업데이트가 필요한 제품 ID를 추가"""
        cls._get_pending_products().add(product_id)

    @classmethod
    def _update_pending_products(cls):
        """대기 중인 모든 제품들의 best_option을 업데이트"""
        from .models import Product  # 순환 import 방지

        pending_product_ids = cls._get_pending_products()
        if not pending_product_ids:
            return

        products = Product.objects.filter(id__in=pending_product_ids)
        for product in products:
            product._update_product_best_option()

        # 처리 완료 후 초기화
        _thread_locals.pending_products.clear()


class ProductDetailImage(SoftDeleteImageModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="product_images/")
    type = models.CharField(
        max_length=25, choices=[("pc", "pc"), ("mobile", "mobile")], default="pc"
    )
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return (
            f"Image for {self.product.name} - {self.description[:20]}..."
            if self.description
            else f"Image for {self.product.name}"
        )


class Product(SoftDeleteModel):
    name = models.CharField(max_length=100)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="products",
    )
    best_price_option = models.ForeignKey(
        "ProductOption",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="best_price_option",
    )
    image_main = models.ImageField(upload_to="product_images/", blank=True)
    description = models.TextField(default="", blank=True)
    sort_order = models.IntegerField(default=0, help_text="정렬 순서")
    is_featured = models.BooleanField(default=False, help_text="추천 상품 여부")
    is_active = models.BooleanField(default=False, help_text="활성화 여부")

    def __str__(self):
        return f"{self.name}"

    def _update_product_best_option(self):
        best_option = (
            self.options.filter(deleted_at__isnull=True)
            .select_related("plan")
            .filter(plan__deleted_at__isnull=True)
            .order_by("final_price", "plan__price")
            .first()
        )

        self.best_price_option = best_option
        self.save()


class Order(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="orders"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="orders",
        help_text="요금제 (e.g., 5G 요금제)",
    )
    # 신청 내역
    plan_monthly_fee = models.IntegerField(default=0)
    monthly_discount = models.IntegerField(default=0)
    discount_type = models.CharField(
        max_length=50,
        choices=[
            ("공시지원금", "공시지원금"),
            ("선택약정", "선택약정"),
        ],
        default="공시지원금",
    )
    contract_type = models.CharField(
        max_length=50,
        choices=[
            ("신규가입", "신규가입"),
            ("번호이동", "번호이동"),
            ("기기변경", "기기변경"),
        ],
        default="기기변경",
    )
    payment_period = models.CharField(
        max_length=50,
        choices=[
            ("24개월", "24개월"),
            ("30개월", "30개월"),
            ("36개월", "36개월"),
            ("일시불", "일시불"),
        ],
        default="24개월",
    )
    device_price = models.IntegerField(
        help_text="기기 가격",
        null=True,
        blank=True,
    )
    storage_capacity = models.IntegerField(default=0)
    color = models.CharField(max_length=50, blank=True, null=True)
    subsidy_standard = models.IntegerField(
        help_text="공시지원금",
        null=True,
        blank=True,
    )
    subsidy_mnp = models.IntegerField(
        help_text="전환지원금",
        null=True,
        blank=True,
    )
    additional_discount = models.IntegerField(
        help_text="추가지원금",
        null=True,
        blank=True,
    )
    final_price = models.IntegerField(
        help_text="최종 가격",
        null=True,
        blank=True,
    )

    # 고객 정보
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    customer_phone2 = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True, null=True)
    customer_birth = models.DateField(
        blank=True, null=True, help_text="생년월일 (YYYY-MM-DD)"
    )

    # 배송
    shipping_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="배송 방법",
        default="우체국",
    )
    shipping_address = models.CharField(
        max_length=255, blank=True, null=True, help_text="주소 1 (e.g., 도로명 주소)"
    )
    shipping_address_detail = models.CharField(
        max_length=255, blank=True, null=True, help_text="주소 2 (e.g., 상세 주소)"
    )
    zipcode = models.CharField(
        max_length=10, blank=True, null=True, help_text="우편번호"
    )
    shipping_number = models.CharField(
        max_length=20, blank=True, null=True, help_text="배송 추적 번호"
    )

    # 상태관리
    customer_memo = models.TextField(
        blank=True, null=True, help_text="고객 메모 (e.g., 배송 요청사항)"
    )
    admin_memo = models.TextField(
        blank=True, null=True, help_text="관리자 메모 (e.g., 주문 처리 관련 메모)"
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ("주문접수", "주문접수"),
            ("해피콜진행중", "해피콜진행중"),
            ("해피콜완료", "해피콜완료"),
            ("신용조회중", "신용조회중"),
            ("배송요청", "배송요청"),
            ("배송중", "배송중"),
            ("배송완료", "배송완료"),
            ("개통대기", "개통대기"),
            ("개통완료", "개통완료"),
            ("취소요청", "취소요청"),
            ("취소완료", "취소완료"),
        ],
        default="주문접수",
    )
    payment_status = models.CharField(
        max_length=50, blank=True, null=True, help_text="결제 상태"
    )
    ga4_id = models.CharField(
        max_length=255, blank=True, help_text="GA4 ID", default=""
    )

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.product.name} {self.customer_name}"


class FAQ(SoftDeleteModel):
    category = models.CharField(max_length=100)
    question = models.TextField(max_length=255)
    answer = models.TextField()
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.question


class Notice(SoftDeleteModel):
    title = models.CharField(max_length=100)
    content = models.TextField()

    def __str__(self):
        return self.title


class Banner(SoftDeleteImageModel):
    title = models.CharField(max_length=100)
    image_pc = models.ImageField(upload_to="banners/", default="")
    image_mobile = models.ImageField(upload_to="banners/", default="")
    link = models.URLField(blank=True, null=True, help_text="배너 클릭 시 이동할 링크")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="배너 활성화 여부")
    # remove field 'image'

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
        upload_to="review_images/", blank=True, null=True, help_text="Review image"
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
    content = models.FileField(upload_to="policy_documents/")
    effective_date = models.DateField(help_text="Effective date of the policy")

    def __str__(self):
        return self.document_type


class PartnerCard(SoftDeleteImageModel):
    carrier = models.CharField(max_length=100, null=True)
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
    description = MDTextField(null=True, blank=True)
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
