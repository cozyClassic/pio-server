from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db.models import Prefetch, Q, F, Subquery, OuterRef
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from phone.serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductOptionSimpleSerializer,
    ProductOptionSerializer,
    ProductSeriesSerializer,
)
from phone.models import (
    Product,
    ProductOption,
    DeviceVariant,
    DeviceColor,
    DevicesColorImage,
    ProductDetailImage,
    Review,
    Inventory,
    ProductSeries,
)
from phone.constants import CarrierChoices


class ProductViewSet(ReadOnlyModelViewSet):
    """
    Viewset for listing products with their best price options.
    """

    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(is_active=True).all()

    def get_queryset(self):
        return self.queryset

    _product_list_option_schema = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        description="통신사별 최저가 옵션 (SK/KT/LG 각 1개, 최대 3개)",
        properties={
            "id": openapi.Schema(
                type=openapi.TYPE_INTEGER, description="ProductOption ID"
            ),
            "final_price": openapi.Schema(
                type=openapi.TYPE_INTEGER, description="최종 단말기 가격 (원)"
            ),
            "carrier": openapi.Schema(
                type=openapi.TYPE_STRING, description="통신사", enum=["SK", "KT", "LG"]
            ),
            "contract_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="계약유형",
                enum=["번호이동", "기기변경", "신규"],
            ),
            "discount_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="할인유형",
                enum=["공시지원금", "선택약정"],
            ),
            "is_best": openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description="전체 통신사 중 최저가 여부 (true=최저가)",
            ),
            "device_price": openapi.Schema(
                type=openapi.TYPE_INTEGER, description="단말기 출고가 (원)"
            ),
            "device_name": openapi.Schema(
                type=openapi.TYPE_STRING, description="단말기 모델명"
            ),
            "monthly_payment": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="월 납부금 = (할부금 + 요금제) (원)",
            ),
            "plan_id": openapi.Schema(
                type=openapi.TYPE_INTEGER, description="요금제 ID"
            ),
        },
    )

    _product_list_item_schema = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="상품 ID"),
            "name": openapi.Schema(
                type=openapi.TYPE_STRING, description="상품명 (예: 갤럭시 S26)"
            ),
            "series": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="시리즈 정보 (null 가능)",
                properties={
                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                    "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "sort_order": openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            ),
            "is_featured": openapi.Schema(
                type=openapi.TYPE_BOOLEAN, description="추천 상품 여부"
            ),
            "options": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="통신사별(SK/KT/LG) 최저가 옵션 최대 3개.",
                items=_product_list_option_schema,
            ),
            "images": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING),
                description="상품 이미지 URL 목록 (CloudFront CDN)",
            ),
            "tags": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="상품 태그/뱃지 목록",
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "name": openapi.Schema(type=openapi.TYPE_STRING),
                        "text_color": openapi.Schema(type=openapi.TYPE_STRING),
                        "tag_color": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
        },
    )

    @swagger_auto_schema(
        operation_summary="상품 목록 조회",
        operation_description="통신사별 최저가 옵션을 포함한 상품 목록을 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                "brand",
                openapi.IN_QUERY,
                description="제조사",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "series",
                openapi.IN_QUERY,
                description="시리즈명",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "carrier",
                openapi.IN_QUERY,
                description="이전 통신사",
                type=openapi.TYPE_STRING,
                required=False,
                enum=["SK", "KT", "LG"],
            ),
            openapi.Parameter(
                "is_featured",
                openapi.IN_QUERY,
                description="추천 상품 여부",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="상품 목록",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY, items=_product_list_item_schema
                ),
            ),
            404: "결과 없음",
        },
        tags=["상품"],
    )
    def list(self, request: Request, *args, **kwargs):
        base_queryset = (
            self.get_queryset()
            .filter(best_price_option_id__isnull=False)
            .select_related("product_series")
            .prefetch_related("tags")
        )
        if brand_query := request.query_params.get("brand", None):
            base_queryset = base_queryset.filter(device__brand=brand_query)
        if series_query := request.query_params.get("series", None):
            base_queryset = base_queryset.filter(product_series__name=series_query)
        if (
            prev_carrier := request.query_params.get("carrier", None)
        ) in CarrierChoices.VALUES:
            pass
        if is_featured := request.query_params.get("is_featured", None):
            if is_featured.lower() == "true":
                base_queryset = base_queryset.filter(is_featured=True)
            elif is_featured.lower() == "false":
                base_queryset = base_queryset.filter(is_featured=False)

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        queryset = (
            base_queryset.select_related("device")
            .prefetch_related("images")
            .order_by("-sort_order")
        )

        if prev_carrier in CarrierChoices.VALUES:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.all()
                    .select_related("plan", "device_variant")
                    .filter(
                        Q(Q(contract_type="기기변경") & Q(plan__carrier=prev_carrier))
                        | Q(
                            Q(contract_type="번호이동") & ~Q(plan__carrier=prev_carrier)
                        )
                    ),
                )
            )
        else:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.all().select_related(
                        "plan", "device_variant"
                    ),
                )
            )

        device_ids = queryset.values_list("device_id", flat=True)
        in_stock_by_device = {}
        for inv in Inventory.objects.filter(
            device_variant__device_id__in=device_ids, count__gt=0
        ).select_related("dealership", "device_variant"):
            did = inv.device_variant.device_id
            if did not in in_stock_by_device:
                in_stock_by_device[did] = set()
            in_stock_by_device[did].add(
                (inv.dealership.carrier, inv.device_variant.storage_capacity)
            )

        serializer = ProductListSerializer(
            queryset, many=True, context={"in_stock_by_device": in_stock_by_device}
        )
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="상품 상세 조회",
        operation_description="상품 ID로 상세 정보를 조회합니다. 조회수 자동 +1 증가.",
        manual_parameters=[
            openapi.Parameter(
                "carrier",
                openapi.IN_QUERY,
                description="이전 통신사",
                type=openapi.TYPE_STRING,
                required=False,
                enum=["SK", "KT", "LG"],
            ),
        ],
        responses={200: "상품 상세", 404: "상품을 찾을 수 없음"},
        tags=["상품"],
    )
    def retrieve(self, request: Request, *args, **kwargs):
        base_queryset = self.get_queryset().filter(id=kwargs.get("pk"))

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        base_queryset.update(views=F("views") + 1)

        prev_carrier = request.query_params.get("carrier", None)
        if prev_carrier in CarrierChoices.VALUES:
            base_queryset = base_queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.all()
                    .select_related("plan", "device_variant")
                    .filter(
                        Q(Q(contract_type="기기변경") & Q(plan__carrier=prev_carrier))
                        | Q(
                            Q(contract_type="번호이동") & ~Q(plan__carrier=prev_carrier)
                        )
                    ),
                )
            )
        else:
            base_queryset = base_queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.all()
                    .exclude(additional_discount=0)
                    .select_related("plan", "device_variant", "official_contract_link"),
                )
            )

        instance = (
            base_queryset.select_related("device").prefetch_related(
                Prefetch("device__variants", queryset=DeviceVariant.objects.all()),
                Prefetch(
                    "device__colors",
                    queryset=DeviceColor.objects.all().order_by("sort_order"),
                ),
                Prefetch(
                    "device__colors__images", queryset=DevicesColorImage.objects.all()
                ),
                Prefetch("images", queryset=ProductDetailImage.objects.all()),
                Prefetch(
                    "reviews",
                    queryset=Review.objects.filter(is_public=True).order_by(
                        "-created_at"
                    )[:10],
                    to_attr="limited_reviews",
                ),
            )
        ).first()

        if instance is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        variant_ids = [v.id for v in instance.device.variants.all()]
        color_ids = [c.id for c in instance.device.colors.all()]
        inventories = Inventory.objects.filter(
            device_variant_id__in=variant_ids,
            device_color_id__in=color_ids,
        ).select_related("dealership", "device_variant", "device_color")

        related_products = []
        if instance.product_series:
            related_products = list(
                Product.objects.filter(
                    product_series=instance.product_series,
                    is_active=True,
                )
                .select_related("device")
                .prefetch_related(
                    Prefetch(
                        "device__colors",
                        queryset=DeviceColor.objects.all().order_by("sort_order"),
                    ),
                    Prefetch(
                        "device__colors__images",
                        queryset=DevicesColorImage.objects.all(),
                    ),
                )
            )

        serializer = ProductDetailSerializer(
            instance,
            context={
                "inventories": inventories,
                "related_products": related_products,
            },
        )
        return Response(serializer.data)


class ProductSeriesViewSet(ReadOnlyModelViewSet):
    """제품 시리즈 목록 API"""

    queryset = ProductSeries.objects.prefetch_related(
        "productseries", "productseries__device", "productseries__images"
    ).all()
    serializer_class = ProductSeriesSerializer

    @swagger_auto_schema(
        operation_summary="제품 시리즈 목록 조회",
        responses={200: ProductSeriesSerializer(many=True)},
        tags=["상품"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().order_by("name")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProductOptionViewSet(ReadOnlyModelViewSet):
    """상품옵션 목록 API"""

    serializer_class = ProductOptionSerializer
    queryset = ProductOption.objects.all()

    @swagger_auto_schema(
        operation_summary="상품옵션 목록 조회",
        manual_parameters=[
            openapi.Parameter(
                "dv_id",
                openapi.IN_QUERY,
                description="DeviceVariant ID",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: ProductOptionSerializer(many=True)},
        tags=["상품옵션"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if dv_id := request.query_params.get("dv_id", None):
            queryset = queryset.filter(device_variant_id=dv_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
