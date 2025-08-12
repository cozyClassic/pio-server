from django.db import models
from django.utils import timezone
from django.db.models import QuerySet
from simple_history.models import HistoricalRecords


# Create your models here.
def get_int_or_zero(value):
    return int(value) if value is not None else 0


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
    image = models.ImageField(upload_to="images/")

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
        return f"{self.model_name} by {self.brand}"


class DeviceColor(SoftDeleteModel):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="colors")
    color = models.CharField(max_length=50)
    color_code = models.CharField(
        max_length=7, help_text="Hex color code, e.g., #FFFFFF"
    )

    def __str__(self):
        return f"{self.color} for {self.device.model_name}"


class DevicesColorImage(SoftDeleteImageModel):
    device_color = models.ForeignKey(
        DeviceColor, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="device_color_images/")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"image for {self.device_color.device.model_name} - {self.device_color.color}"


class DeviceVariant(SoftDeleteModel):
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="variants"
    )
    storage_capacity = models.CharField(max_length=100)
    device_price = models.IntegerField(default=0, help_text="Price in KRW")

    def __str__(self):
        return f"{self.device.model_name} - {self.storage_capacity}"

    # 가격이 업데이트 되면 연결된 product 옵션들도 가격을 업데이트해야 합니다.
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # DeviceVariant의 가격이 변경되면 연결된 ProductOption의 가격도 업데이트합니다.
        product_options: QuerySet[ProductOption] = self.product_options.filter(
            device_variant_id=self.id
        )

        for option in product_options:
            option.final_price = option.get_final_price()
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
        return f"{self.discount_type}/{self.contract_type}"

    def get_final_price(self):
        """
        Calculate the final price based on the discount type and contract type.
        """
        final_price = get_int_or_zero(
            self.device_variant.device_price
        ) - get_int_or_zero(self.additional_discount)

        if self.discount_type == "공시지원금":
            final_price -= get_int_or_zero(self.subsidy_amount)
            if self.contract_type == "번호이동":
                final_price -= get_int_or_zero(self.subsidy_amount_mnp)
        elif self.discount_type == "선택약정":
            final_price -= get_int_or_zero(self.plan.price) * 6

        return final_price

    def save(self, *args, **kwargs):
        self.final_price = self.get_final_price()
        # 먼저 객체를 저장합니다.
        super().save(*args, **kwargs)
        # 저장 후, 최적의 옵션을 찾아 Product 모델을 업데이트합니다.
        self.update_product_best_option()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)

        # 삭제 후, 최적의 옵션을 다시 업데이트합니다.
        product.update_best_option_on_delete()  # Product 모델에 정의된 메서드를 호출

    def update_product_best_option(self):
        # TODO: 하나의 가격이 바뀌어도 동작해야 하지만, 여러개의 가격이 바뀔 때는 한번만 돌아가야 함
        product = self.product
        options: QuerySet[ProductOption] = product.options.select_related("plan").all()
        best_option = options.order_by("final_price", "plan__price").first()
        product.best_price_option = best_option
        product.save()


class ProductDetailImage(SoftDeleteImageModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="product_images/")
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

    def __str__(self):
        return f"{self.name}"


class Order(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="orders"
    )
    device_variant = models.ForeignKey(
        DeviceVariant, on_delete=models.CASCADE, related_name="orders"
    )
    device_color = models.ForeignKey(
        DeviceColor,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
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
    device_price = models.IntegerField(
        help_text="기기 가격",
        null=True,
        blank=True,
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

    # 고객 정보
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    customer_phone2 = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True, null=True)
    customer_birth = models.DateField(
        blank=True, null=True, help_text="생년월일 (YYYY-MM-DD)"
    )
    password = models.CharField(max_length=100, blank=True, null=True)

    # 배송
    shipping_method = models.CharField(
        max_length=50, blank=True, null=True, help_text="배송 방법"
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
    image = models.ImageField(upload_to="banners/")
    link = models.URLField(blank=True, null=True, help_text="배너 클릭 시 이동할 링크")

    def __str__(self):
        return self.title


class ReviewImage(SoftDeleteImageModel):
    review = models.ForeignKey(
        "Review", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="review_images/")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Image for review by {self.review.customer_name}"


class Review(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    customer_name = models.CharField(max_length=100)
    rating = models.IntegerField(default=0, help_text="Rating from 1 to 5")
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer_name} - {self.created_at}"
