from django.db import models

from django.utils import timezone
from django.db.models import QuerySet
from simple_history.models import HistoricalRecords
from threading import local
import pandas as pd
from .managers import SoftDeleteManager

from tinymce import models as tinymce_models
from .utils import UniqueFilePathGenerator
from .constants import CarrierChoices, ContractTypeChoices, OpenMarketChoices

# Thread-local storage for tracking products that need updates
_thread_locals = local()


def get_int_or_zero(value):
    return 0 if value is None or pd.isna(value) else int(value)


class SoftDeleteModel(models.Model):
    """
    Abstract model to add soft delete functionality.
    """

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


class PlanPremiumChoices(SoftDeleteImageModel):
    carrier = models.CharField(max_length=10, choices=CarrierChoices.CHOICES)
    name = models.CharField(max_length=100, help_text="넷플릭스, 유튜브 등")
    description = models.TextField()


class Plan(SoftDeleteModel):
    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=100, choices=CarrierChoices.CHOICES)
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
    membership_level = models.CharField(max_length=100, default="")
    short_name = models.CharField(max_length=100, default="", null=True, blank=True)
    # many to many: PlanPremiumChoices

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
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.color}"


class DevicesColorImage(SoftDeleteImageModel):
    device_color = models.ForeignKey(
        DeviceColor, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=UniqueFilePathGenerator("device_color_images/"))
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
    name_sk = models.CharField(
        max_length=100, help_text="SK 모델명", blank=True, default="", null=True
    )
    price_sk = models.IntegerField(
        help_text="SK 모델 가격", blank=True, default=0, null=True
    )
    name_kt = models.CharField(
        max_length=100, help_text="KT 모델명", blank=True, default="", null=True
    )
    price_kt = models.IntegerField(
        help_text="KT 모델 가격", blank=True, default=0, null=True
    )
    name_lg = models.CharField(
        max_length=100, help_text="LG 모델명", blank=True, default="", null=True
    )
    price_lg = models.IntegerField(
        help_text="LG 모델 가격", blank=True, default=0, null=True
    )

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
    device_price = models.IntegerField(
        help_text="기기 가격",
        null=True,
        default=0,
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
        choices=ContractTypeChoices.CHOICES,
        default=ContractTypeChoices.CHANGE,
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
    dealer = models.ForeignKey(
        "Dealership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_options",
    )
    official_contract_link = models.ForeignKey(
        "OfficialContractLink",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_options",
        default=None,
    )

    def __str__(self):
        return f"{self.id}"

    def _get_final_price(self):
        return self.calculate_final_price(
            device_price=self.device_price,
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

    @property
    def monthly_payment(self):
        result = 0
        if self.final_price:
            result += self.final_price * (1.0625 / 24)
        return int(
            result
            + (
                self.plan.price * 0.75
                if self.discount_type == "선택약정"
                else self.plan.price
            )
        )

    @property
    def six_month_total_gongsi(self):
        return self.plan.price * 6 + self.final_price


class ProductDetailImage(SoftDeleteImageModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=UniqueFilePathGenerator("product_images/"))
    type = models.CharField(
        max_length=25,
        choices=[("pc", "pc"), ("mobile", "mobile"), ("detail", "detail")],
        default="pc",
    )
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return str(self.id)


class ProductSeries(SoftDeleteModel):
    # 하나의 시리즈는 여러 제품에 속할 수 있음
    # 하나의 제품은 하나의 시리즈에만 속함
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.name


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
    description = models.TextField(default="", blank=True)
    sort_order = models.IntegerField(default=0, help_text="정렬 순서")
    is_featured = models.BooleanField(default=False, help_text="추천 상품 여부")
    is_active = models.BooleanField(default=False, help_text="활성화 여부")
    views = models.IntegerField(default=0, help_text="조회수")
    product_series = models.ForeignKey(
        ProductSeries,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productseries",
    )

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
        choices=ContractTypeChoices.CHOICES,
        default=ContractTypeChoices.CHANGE,
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
            ("해피콜 부재중", "해피콜 부재중"),
            ("해피콜완료", "해피콜완료"),
            ("공식신청서접수대기", "공식신청서접수대기"),
            ("재고대기", "재고대기"),
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

    prev_carrier = models.CharField(
        max_length=50,
        choices=[
            ("SK", "SK"),
            ("KT", "KT"),
            ("LG", "LG"),
        ],
        blank=True,
        null=True,
        help_text="이전 통신사",
    )

    history = HistoricalRecords()
    channeltalk_user_id = models.CharField(
        max_length=100, blank=True, null=True, default=None
    )

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
    content = tinymce_models.HTMLField(default="", blank=True)
    type = models.CharField(
        max_length=25,
        choices=[("caution", "caution"), ("event", "event"), ("general", "general")],
        default="general",
    )

    def __str__(self):
        return self.title


class DecoratorTag(SoftDeleteModel):
    name = models.CharField(max_length=100)
    text_color = models.CharField(max_length=7)
    tag_color = models.CharField(max_length=7)
    product = models.ManyToManyField("Product", related_name="tags", blank=True)
    # product에도, product option에도 추가할 수 있음

    def __str__(self):
        return f"{self.name} {self.text_color} {self.tag_color}"


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


class PriceHistory(SoftDeleteModel):
    # 공시지원금, 요금제중에 최저가만 기준 잡아서 기록
    # device 및 device_variant는 product로 알 수 있으므로 따로 저장하지 않음.
    # capacity가 가장 작고 가장 저렴한 variant를 기준으로 삼음
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="best_prices"
    )
    carrier = models.CharField(max_length=100, choices=CarrierChoices.CHOICES)
    final_price = models.IntegerField(help_text="최종 가격", null=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="best_prices")
    # created_at과 별도로 저장
    price_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.price_at}"

    class Meta:
        unique_together = ("product", "price_at", "carrier")


class PriceNotificationRequest(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_notifications"
    )
    customer_phone = models.CharField(max_length=15)
    target_price = models.IntegerField(help_text="Target price for notification")
    prev_carrier = models.CharField(
        max_length=50,
        choices=CarrierChoices.CHOICES,
        help_text="Previous carrier",
        default=CarrierChoices.MVNO,
    )
    notified_at = models.DateTimeField(
        null=True, blank=True, help_text="Notification timestamp", default=None
    )
    channel_talk_user_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Channel Talk User ID for notification",
        default="",
    )


class Dealership(SoftDeleteModel):
    """대리점 관리 테이블"""

    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=50, choices=CarrierChoices.CHOICES)
    contact_number = models.CharField(max_length=20)
    manager = models.CharField(max_length=100)
    credit_check_agree_format = models.TextField(null=True)
    opening_request_format = models.TextField(null=True)

    def __str__(self):
        return self.name


class OfficialContractLink(SoftDeleteModel):
    """공식신청서 관리 테이블 - (대리점, 단말기(용량), 신규/기변/번이) 별 관리"""

    dealer = models.ForeignKey(
        Dealership, on_delete=models.CASCADE, related_name="official_links"
    )
    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.CASCADE,
        related_name="official_links",
    )
    contract_type = models.CharField(
        max_length=50,
        choices=ContractTypeChoices.CHOICES,
        default=ContractTypeChoices.CHANGE,
    )
    link = models.URLField(help_text="Official contract submission link")

    class Meta:
        unique_together = ("dealer", "device_variant", "contract_type")


class CreditCheckAgreement(SoftDeleteModel):
    """신용조회 확인용 링크 테이블"""

    image = models.ImageField(
        upload_to=UniqueFilePathGenerator("credit_check_agreements/"),
        blank=True,
        null=True,
        help_text="신용조회 동의서 스크린샷",
    )
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="credit_check_agreements"
    )

    def __str__(self):
        return f"Credit Check Agreement for Order {self.order.id}"


class Inventory(SoftDeleteModel):
    """각 대리점에서 받는 재고표와 DB에 있는 device_varaint, device_color 정보를 매칭하기 위한 테이블"""

    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    name_in_sheet = models.CharField(
        max_length=100,
        help_text="재고표에 있는 모델명. 텍스트 안에 쉼표가 들어가서 여러 모델명이 있을 수 있음",
    )
    dealership = models.ForeignKey(
        Dealership,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    device_color = models.ForeignKey(
        DeviceColor,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    color_in_sheet = models.CharField(
        max_length=50,
        help_text="재고표에 있는 색상명. 텍스트 안에 쉼표가 들어가서 여러 색상명이 있을 수 있음",
    )
    count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name_in_sheet} ({self.color_in_sheet})"

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["device_variant", "device_color", "dealership"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["device_variant", "device_color", "dealership"],
                name="unique_inventory_item",
            )
        ]


class OpenMarket(SoftDeleteModel):
    source = models.CharField(
        "오픈마켓업체",
        choices=OpenMarketChoices.Choices,
        null=False,
        blank=False,
        default=OpenMarketChoices.ST11,
        max_length=20,
    )
    option_min_rate = models.IntegerField(default=0)
    option_max_rate = models.IntegerField(default=0)
    commision_rate_default = models.FloatField(default=0.08)
    commision_rate_compare_platform = models.FloatField(default=0.02)
    api_key = models.CharField(max_length=255, default="", blank=True)

    def __str__(self):
        return self.source


class OpenMarketProduct(SoftDeleteModel):
    open_market = models.ForeignKey(
        OpenMarket, on_delete=models.CASCADE, related_name="products"
    )
    om_product_id = models.CharField(
        max_length=100, blank=True, null=True, default=None
    )
    seller_code = models.CharField(max_length=100, blank=True, null=True, default=None)
    name = models.CharField(max_length=255, default="", blank=True)
    registered_price = models.PositiveIntegerField(default=10000)
    detail_page_html = tinymce_models.HTMLField(default="", blank=True)
    last_price_updated_at = models.DateTimeField(default=None, null=True)


class OpenMarketProductOption(SoftDeleteModel):
    open_market_product = models.ForeignKey(
        OpenMarketProduct, on_delete=models.CASCADE, related_name="options"
    )
    pio_product_option = models.ForeignKey(
        ProductOption, on_delete=models.CASCADE, related_name="open_market_options"
    )
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="open_market_options",
    )
    om_id = models.CharField(max_length=255, default="", blank=True)
    option_name = models.CharField(max_length=255, default="", blank=True)
    price = models.IntegerField(default=0)

    def _assert_relations_cached_for_validate_name(self):
        if not all(
            (key in self.__dict__ for key in ("pio_product_option", "open_market"))
        ):
            raise RuntimeError("N+1 방지: select_related 누락")

        if not all(
            (
                key in self.__dict__["pio_product_option"].__dict__
                for key in ("plan", "device_variant")
            )
        ):
            raise RuntimeError("N+1 방지: select_related 누락")

    def validate_product_name(self):
        # N+1 방지
        self._assert_relations_cached_for_validate_name()

        # 데이터 호출하기
        om_product_name = self.open_market.name
        pio_product_option = self.pio_product_option
        carrier = pio_product_option.plan.carrier
        contract_type = pio_product_option.contract_type
        discount_type = pio_product_option.discount_type
        capacity = pio_product_option.device_variant.storage_capacity

        error_list = []

        # 통신사명
        if carrier not in om_product_name:
            error_list.append(("통신사명", carrier))

        # 검색어 고려해서 '기변', '번이' 쓰지 말기 - 기변:기기변경 - 1:3, 번이: 번호이동 - 1:10
        if contract_type not in om_product_name:
            error_list.append(("가입유형", contract_type))

        discount_type_keywords = {
            "공시지원금": ("공시", "공통", "단말"),
            "선택약정": ("선약", "선택약정", "요금"),
        }
        if discount_type in discount_type_keywords:
            keywords = discount_type_keywords[discount_type]
            if not any(key in om_product_name for key in keywords):
                error_list.append(("할인유형", discount_type))

        if str(capacity) not in om_product_name:
            error_list.append(("저장용량", capacity))

        return error_list

    def validate_price(self):
        product = self.open_market_product
        open_market = product.open_market

        if (self.price / product.registered_price) * 100 > open_market.option_max_rate:
            raise Exception("")
        if (self.price / product.registered_price) * 100 < open_market.option_min_rate:
            raise Exception("")

    def validate_plan(self):
        plan = self.pio_product_option.plan
        name_split = plan.split(" ")
        if name_split[-1] in self.option_name:
            return
        raise Exception("옵션명 요금제명 확인 필요")
