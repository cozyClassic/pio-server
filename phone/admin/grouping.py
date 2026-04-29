# pyright: reportAttributeAccessIssue=false
"""
Phone admin 사이드바 그룹화.

`admin.AdminSite.get_app_list` 를 monkeypatch 하여 phone 앱의 모델들을
의미적 그룹으로 묶어 표시한다. 모든 admin 클래스가 먼저 등록되어야 하므로
`phone/admin/__init__.py` 에서 이 모듈을 **가장 마지막에** import 해야 한다.
"""

from django.contrib import admin

from phone.models import *  # noqa: F401, F403

_ADMIN_GROUPS = {
    "단말기 · 요금제": [Plan, PlanPremiumChoices, Device, DeviceColor, DeviceVariant],
    "상품": [
        Product,
        ProductOption,
        ProductDetailImage,
        ProductSeries,
        DecoratorTag,
        PriceHistory,
    ],
    "주문": [Order, Order.history.model, DiagnosisInquiry],
    "콘텐츠 · 마케팅": [
        Review,
        FAQ,
        Notice,
        Banner,
        Event,
        PolicyDocument,
        CardIssuer,
        PartnerCard,
        CardAdditionalPromotion,
        CustomImage,
    ],
    "재고": [Inventory],
    "오픈마켓": [OpenMarket, OpenMarketProduct, OpenMarketProductOption],
    "기타": [Dealership, OfficialContractLink],
    "진단": [DiagnosisLog, CalculatorSession, CustomerIdentity],
}

_original_get_app_list = admin.AdminSite.get_app_list


def _grouped_get_app_list(self, request, app_label=None):
    app_list = _original_get_app_list(self, request, app_label)

    phone_models = {}
    other_apps = []

    for app in app_list:
        if app["app_label"] == "phone":
            for model in app["models"]:
                phone_models[model["object_name"]] = model
        else:
            other_apps.append(app)

    grouped_apps = []
    for group_name, model_classes in _ADMIN_GROUPS.items():
        models = [
            phone_models[m.__name__]
            for m in model_classes
            if m.__name__ in phone_models
        ]
        if models:
            grouped_apps.append(
                {
                    "name": group_name,
                    "app_label": f"phone__{group_name}",
                    "app_url": "/admin/phone/",
                    "has_module_perms": True,
                    "models": models,
                }
            )

    return grouped_apps + other_apps


admin.AdminSite.get_app_list = _grouped_get_app_list
