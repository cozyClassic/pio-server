from django.db import models
from simple_history.models import HistoricalRecords

from phone.constants import DiscountTypeChoices, ContractTypeChoices, CarrierChoices
from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel
from .product import Product
from .plan import Plan


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
        choices=DiscountTypeChoices.CHOICES,
        default=DiscountTypeChoices.SUBSIDY,
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
