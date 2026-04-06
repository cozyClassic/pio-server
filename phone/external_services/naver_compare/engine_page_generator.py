import boto3
from django.conf import settings
from phone.models import *
from phone.constants import OpenMarketChoices
from urllib.parse import urlencode
from django.utils import timezone
from phone.constants import *
from django.db.models import QuerySet


# .txt 파일, 컬럼은 탭으로 구분하기, 헤더는 총 74개
# 참조 - https://join.shopping.naver.com/misc/download/ep_guide.nhn


class NaverCompareEnginePageGenerator:
    HEADERS = [
        "id",
        "title",
        "price_pc",
        "benefit_price",
        "normal_price",
        "link",
        "mobile_link",
        "image_link",
        "add_image_link",
        "video_url",
        "category_name1",
        "category_name2",
        "",  # "category_name3",
        "",  # "category_name4",
        "naver_category",
        "naver_product_id",
        "",  # "product_option_id",
        "",  # "condition",
        "",  # "import_flag",
        "",  # "parallel_import",
        "",  # "order_made",
        "",  # "product_flag",
        "",  # "adult",
        "",  # "goods_type",
        "",  # "barcode",
        "manufacture_define_number",
        "brand",
        "",  # "brand_certification",
        "maker",
        "origin",
        "",  # "card_event",
        "",
        "",
        "",
        "",
        "",
        "",  # "rental_info",  # 선택약정이면 입력, 할부원금^24^^
        "search_tag",
        "",
        "",
        "",
        "",
        "",
        "",
        "shipping",  # 0
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "shipping_settings",  # 오늘출발^15:00^택배^우체국택배^N^Y^3000^6000^1^1^토요일|일요일|공휴일^
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",  # "color_code",
        "",
        "",
        "",
    ]

    def _get_queryset(self):
        return (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.N_COMP,
                deleted_at__isnull=True,
                device_variant__product_options__product__is_active=True,
                device_variant__product_options__product__deleted_at__isnull=True,
            )
            .select_related(
                "device_variant",
                "device_variant__device",
            )
            .prefetch_related(
                "device_variant__product_options",
                "device_variant__product_options__product",
                "device_variant__inventories__dealership",
                "device_variant__product_options__plan",
                "device_variant__device__colors",
                "device_variant__device__colors__images",
            )
            .distinct()
        )

    def _get_price_pc(self, omp: OpenMarketProduct):
        # 단말기 가격이 가장 낮은 옵션의 가격을 반환

        carrier = omp.get_carrier()
        contract_type = omp.get_contract_type()

        options = [
            opt
            for opt in omp.device_variant.product_options.all()
            if opt.plan.carrier == carrier
            and opt.contract_type == contract_type
            and opt.discount_type == DiscountTypeChoices.SUBSIDY
        ]

        if not options:
            raise ValueError(
                f"No options found for OpenMarketProduct with id {omp.id} matching carrier {carrier}, contract type {contract_type}, and subsidy discount type."
            )
        return str(max(min(opt.final_price for opt in options), 100))

    def _get_link(self, omp: OpenMarketProduct):
        product_id = omp.device_variant.product_options.all()[0].product_id
        if not product_id:
            raise ValueError(
                f"Product ID is missing for OpenMarketProduct with id {omp.id}"
            )
        prev_carrier = "mvno"

        contract_type = omp.get_contract_type()
        if contract_type == ContractTypeChoices.CHANGE:
            prev_carrier = omp.get_carrier()
        URL = f"https://www.phoneinone.com/mobile/detail/{product_id}/{prev_carrier}"

        # SearchParams- next_carrier, capacity, discount_type, is_best_device_price
        search_params = {
            "next_carrier": omp.get_carrier(),
            "capacity": str(omp.get_capacity()),
            "discount_type": DiscountTypeChoices.SUBSIDY,  # 이후에 상품 선택약정 상품 추가 고려
            "is_best_device_price": "true",
        }

        return f"{URL}?{urlencode(search_params)}"

    def _get_image_link(self, omp: OpenMarketProduct):
        # 이미 prefetch로 불러왔으니, first() 혹은 exist()를 사용해서 추가쿼리를 발생시키는 대신 이미 불러온 데이터에서 바로 접근
        colors = omp.device_variant.device.colors.all()
        if len(colors) == 0:
            raise ValueError(
                f"No colors found for device {omp.device_variant.device.name}"
            )
        images: QuerySet[DevicesColorImage] = colors[0].images.all()
        if len(images) == 0:
            raise ValueError(
                f"No images found for color {colors[0].name} of device {omp.device_variant.device.name}"
            )
        return images[0].image.url

    def _get_category_name1(self, omp: OpenMarketProduct):
        return omp.device_variant.device.brand

    def _get_category_name2(self, omp: OpenMarketProduct):
        return omp.device_variant.device.series

    def _get_naver_category(self, omp: OpenMarketProduct):
        """
        디지털/가전>휴대폰>KT        50000247
        디지털/가전>휴대폰>LG U+        50000248
        디지털/가전>휴대폰>MVNO        50000251
        디지털/가전>휴대폰>SKT        50000246
        """
        carrier = omp.get_carrier()
        if carrier == CarrierChoices.SK:
            return "50000246"
        elif carrier == CarrierChoices.KT:
            return "50000247"
        elif carrier == CarrierChoices.LG:
            return "50000248"
        return ""

    # def _get_product_flag(self, omp: OpenMarketProduct):
    #     if omp.get_discount_type() == DiscountTypeChoices.SELECTION:
    #         return "할부"  # 선택약정의 경우
    #     return ""  # 공시지원금은 blank

    def _get_search_tag(self, omp: OpenMarketProduct):
        tags = [
            omp.device_variant.device.brand,
            omp.device_variant.device.model_name,
            omp.get_capacity(),
            omp.get_carrier(),
            omp.get_contract_type(),
            "핸드폰",
            "휴대폰",
            "성지",
        ]
        return "|".join(tags)

    def _get_shipping_settings(self, omp: OpenMarketProduct):
        shipping_company = "우체국택배"
        if omp.get_carrier() == CarrierChoices.LG:
            shipping_company = "로젠택배"

        return f"오늘출발^15:00^택배^{shipping_company}^N^Y^3000^6000^1^1^토요일|일요일|공휴일^"

    def operation(self, header: str, omp: OpenMarketProduct):
        return {
            "id": omp.seller_code,
            "title": omp.name,
            "price_pc": self._get_price_pc(omp),
            "normal_price": str(omp.device_variant.device_price),
            "link": self._get_link(omp),
            "mobile_link": self._get_link(omp),
            "image_link": self._get_image_link(omp),
            "category_name1": self._get_category_name1(omp),
            "category_name2": self._get_category_name2(omp),
            "naver_category": self._get_naver_category(omp),
            "naver_product_id": str(omp.om_product_id),
            "manufacture_define_number": omp.device_variant.name_sk,
            "brand": omp.device_variant.device.brand,
            "maker": omp.device_variant.device.brand,
            "origin": (
                "베트남" if omp.device_variant.device.brand == "삼성전자" else "중국"
            ),
            "shipping": "0",
            "shipping_settings": "오늘출발^15:00^택배^우체국택배^N^Y^3000^6000^1^1^토요일|일요일|공휴일^",
        }.get(header, "")

    def _save_to_db(self, products: list[OpenMarketProduct]):
        OpenMarketProduct.objects.bulk_update(
            products,
            fields=["registered_price", "updated_at", "last_price_updated_at"],
        )

    def generate(self):
        if len(self.HEADERS) != 74:
            raise ValueError("헤더의 개수가 74개가 아닙니다.")
        self.queryset = self._get_queryset()
        # 혹시 모르니까 header deep copy
        result = [[header for header in self.HEADERS]]
        processed = []
        now = timezone.now()

        for om_product in self.queryset:
            carrier = om_product.get_carrier()
            total_inventory = sum(
                inv.count
                for inv in om_product.device_variant.inventories.all()
                if inv.dealership.carrier == carrier
            )
            if total_inventory == 0:
                continue

            omp = []
            for header in self.HEADERS:
                omp.append(self.operation(header, om_product))
                if header == "price_pc":
                    om_product.registered_price = int(omp[-1])
                    om_product.updated_at = now
                    om_product.last_price_updated_at = now
            result.append(omp)
            processed.append(om_product)

        self._save_to_db(processed)

        content = "\n".join(["\t".join(res) for res in result])
        self._upload_to_s3(content)
        return content

    def _upload_to_s3(self, content: str):
        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION_NAME,
        )
        s3.put_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key="naver/compare-engine-page.txt",
            Body=content.encode("utf-8-sig"),
            ContentType="text/plain; charset=utf-8",
        )
