from typing import TYPE_CHECKING
from threading import local

from django.db import models
from django.db.models import QuerySet

from phone.constants import DiscountTypeChoices, ContractTypeChoices
from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel, SoftDeleteImageModel, get_int_or_zero
from .device import DeviceVariant, Device
from .plan import Plan

# Thread-local storage for tracking products that need updates
_thread_locals = local()


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
        choices=DiscountTypeChoices.CHOICES,
        default=DiscountTypeChoices.SUBSIDY,
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
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class Product(SoftDeleteModel):
    if TYPE_CHECKING:
        options: QuerySet[ProductOption]

    name = models.CharField(max_length=100)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="products",
    )
    best_price_option = models.ForeignKey(
        ProductOption,
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
            self.options.all()
            .select_related("plan")
            .order_by("final_price", "plan__price")
            .first()
        )

        self.best_price_option = best_option
        self.save()


class DecoratorTag(SoftDeleteModel):
    name = models.CharField(max_length=100)
    text_color = models.CharField(max_length=7)
    tag_color = models.CharField(max_length=7)
    product = models.ManyToManyField(Product, related_name="tags", blank=True)

    def __str__(self):
        return f"{self.name} {self.text_color} {self.tag_color}"
