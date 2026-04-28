# PartnerCard / CardBenefit 모델 재설계

phone/models/content 의 `PartnerCard` 와 `CardBenefit` 을 새 도메인 요구사항에 맞춰 정비하기 위한 설계 문서. 기존 데이터는 보존하지 않고 drop & recreate.

## 1. 배경 요구사항

### 카드 (PartnerCard) 입력값
- 카드사명 / 통신사명(다중) / 카드이름 / 카드 이미지
- 가입가능 기간 (예: 26년 1월 ~ 26년 4월) — 캘린더 기간
- 할인 유형 (할부, 무선청구, 유선청구)
- 추가할인 조건 (자유 텍스트) / 추가할인 기간 (발급 후 N개월)
- 전월실적 제외 항목 / 연회비

### 카드 제약
1. 카드는 여러 통신사 보유 가능 (하지만 카드의 통신사 집합과 사용자 가입 통신사가 일치해야 혜택)
2. 10년 후에도 row 1만개 미만
3. 고객이 카드사명을 골라 발급이력 유무를 체크할 수 있어야 함
4. 한 카드가 여러 할인 유형(슬롯 후보)을 가질 수 있음. 그러나 한 카드는 동시에 한 슬롯만 차지. 다른 슬롯끼리는 카드 1장씩 동시 적용 가능 (할부 + 무선청구 + 유선청구 = 최대 3장)
5. '라이트할부카드' — 스마트폰 할부 결제금액이 카드별 최소금액 이상일 때만 적용

### 카드혜택 (CardBenefit) 입력값
- 전월실적기준 (만원 단위 입력 / 원 단위 저장)
- 할인금액
- 종류: 기본할인 / 추가할인

### 카드혜택 제약
1. 같은 종류(기본 또는 추가) 안에서 낮은 실적구간 할인은 높은 구간과 중복 적용 X (실적 ≤ threshold 중 max threshold row 1개 선택)
2. 추가할인은 발급 후 `add_discount_months` 동안만 적용
3. 기본할인과 추가할인은 서로 합산됨

### 추가프로모션 (CardAdditionalPromotion) 입력값
- 조건: 대상단말 (시리즈 단위), 할부금액 N만원 이상
- 혜택: "N개월 뒤 10만원 캐시백", "커피전문점 5% 청구할인", "스타벅스 1만원 결제 시 5천원 할인" 등 — 표현이 다양해 정형화 어려움. 자유 텍스트 위주, 정량 일시금만 시뮬레이션 차감용으로 별도 필드.

## 2. 결정 요약

| # | 결정 항목 | 결론 | 핵심 이유 |
|---|----------|------|---------|
| Q1 | 카드사 모델링 | `CardIssuer` 별도 모델 (FK) | 발급이력 필터의 정규화 단위 |
| Q2 | 카드–통신사 관계 | `carriers = ArrayField(CharField, choices=CarrierChoices)` | 다른 모델과 단위 일관, M2M 정규화 가치 적음 |
| Q3 | 할인 유형 의미 | `discount_types = ArrayField` (슬롯 후보 집합) | 한 카드가 여러 슬롯 후보 보유, 동시엔 한 슬롯만 점유 |
| Q4 | CardBenefit이 슬롯별 차등인가? | 슬롯 무관, 카드 단위 동일 | 운영 단순화 |
| Q5 | 기본 + 추가 합산? | 합산 (kind별 독립 선택 후 더함) | 추가할인이 기본 위에 얹히는 인센티브 패턴 |
| Q6 | "추가할인 기간" 의미 | 발급 후 N개월 → `add_discount_months` IntegerField | 캘린더 시즌 아님 |
| Q7 | 추가할인 조건 표현 | 자유 TextField | 카드사별 문구 천차만별 |
| Q8 | 라이트할부카드 최소금액 | `min_installment_amount` 단일 IntegerField nullable | 카드별 단일 하한선 |
| Q9 | 전월실적 제외 항목 | 자유 TextField | 안내문구 성격, 시뮬레이션 미반영 |
| Q10 | 추가프로모션 종속 | 카드 FK 필수 | 폰인원 도메인은 카드 종속 패턴 |
| Q11 | 대상단말 단위 | `ProductSeries` M2M | 기존 모델 재활용, 신규 단말 자동 포함 |
| Q12 | 추가프로모션 모델명 | `CardAdditionalPromotion` | 일반 프로모션과 명시적 구분 |
| Q13 | 혜택 표현 | 자유 텍스트 + 옵션 `cashback_amount` | 정형 데이터화 어려움, 캐시백만 시뮬레이션 |
| Q14 | 발급이력 체크 | 프론트 사이드 필터 (DB 추가 없음) | 회원/계정 시스템 부재 |
| Q15 | threshold 단위 | 원 단위 저장 | 다른 가격 필드와 일관 |
| Q16 | 마이그레이션 | drop & recreate | 기존 데이터 보존 불요 |

## 3. 최종 모델 스케치

`phone/models/content.py` 에 다음과 같이 정의 (기존 `PartnerCard` / `CardBenefit` 교체).

```python
from django.contrib.postgres.fields import ArrayField

class CardIssuer(SoftDeleteModel):
    """카드사 (신한, KB, 현대, ...) — 발급이력 필터의 정규화 단위"""
    name = models.CharField(max_length=50, unique=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PartnerCard(SoftDeleteImageModel):
    issuer = models.ForeignKey(
        CardIssuer, on_delete=models.PROTECT, related_name='cards'
    )
    name = models.CharField(max_length=100)
    image = models.ImageField(
        upload_to=UniqueFilePathGenerator("partner_cards/"),
        null=True, blank=True,
    )

    # 통신사 다중 보유 (SK / KT / LG / 알뜰폰 부분집합)
    carriers = ArrayField(
        models.CharField(max_length=20, choices=CarrierChoices.CHOICES),
        default=list,
    )

    # 슬롯 후보 (할부 / 무선청구 / 유선청구)
    # 한 카드는 동시에 한 슬롯만 차지
    discount_types = ArrayField(
        models.CharField(max_length=20),  # DiscountTypeChoices 정의 필요
        default=list,
    )

    # 가입 가능 캘린더 기간
    signup_start_date = models.DateField(null=True, blank=True)
    signup_end_date = models.DateField(null=True, blank=True)

    # 발급 후 추가할인 적용 개월수 (24, 36 등)
    add_discount_months = models.IntegerField(null=True, blank=True)
    add_discount_condition = models.TextField(blank=True, default='')

    # 라이트할부카드 전용: 스마트폰 할부금이 이 금액 이상일 때만 적용
    min_installment_amount = models.IntegerField(null=True, blank=True)

    installment_excluded_items = models.TextField(blank=True, default='')
    annual_fee = models.IntegerField(default=0)

    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)


class CardBenefit(SoftDeleteModel):
    """카드 단위 동일. 슬롯과 무관."""
    KIND_CHOICES = [
        ('basic', '기본할인'),
        ('additional', '추가할인'),
    ]

    card = models.ForeignKey(
        PartnerCard, on_delete=models.CASCADE, related_name='card_benefits'
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    threshold_amount = models.IntegerField(help_text='전월실적 기준 (원)')
    amount = models.IntegerField(help_text='할인 금액 (원)')


class CardAdditionalPromotion(SoftDeleteImageModel):
    """N개월 뒤 캐시백, 가맹점 청구할인 등 — 자유 텍스트 위주."""
    card = models.ForeignKey(
        PartnerCard, on_delete=models.CASCADE,
        related_name='additional_promotions',
    )
    target_series = models.ManyToManyField('ProductSeries', blank=True)
    min_installment_amount = models.IntegerField(null=True, blank=True)

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    image = models.ImageField(
        upload_to=UniqueFilePathGenerator("card_promotions/"),
        null=True, blank=True,
    )

    # 시뮬레이션 차감용 일시금 (옵션). NULL 이면 표시용.
    cashback_amount = models.IntegerField(null=True, blank=True)

    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
```

`DiscountTypeChoices` 는 `phone/constants.py` 에 신규 정의:
```python
class DiscountTypeChoices:
    INSTALLMENT = '할부'
    WIRELESS_BILLING = '무선청구'
    WIRED_BILLING = '유선청구'
    CHOICES = [
        (INSTALLMENT, '할부'),
        (WIRELESS_BILLING, '무선청구'),
        (WIRED_BILLING, '유선청구'),
    ]
```

---

> **명칭 동기화 (구현 v2)**: 본 문서가 `DiscountTypeChoices` 명칭으로 정의한 슬롯 enum은, 기존 `phone/constants.py`의 `DiscountTypeChoices`(공시지원금/선택약정 — `ProductOption.discount_type`에서 사용 중)와 충돌을 회피하기 위해 코드상 클래스명을 `CardSlotChoices`로 채택했다. 도메인 의미는 동일하다 (한 카드는 동시에 한 슬롯만 점유).

## 4. 시뮬레이션 적용 룰

### 카드별 적용 가능 판정
1. 사용자의 가입 통신사가 `card.carriers` 에 포함되는가?
2. `card.signup_end_date` 가 오늘 이후인가? (signup_start_date 도 오늘 이전)
3. `card.min_installment_amount` 가 NULL 이거나, ProductOption 의 스마트폰 할부금 ≥ 이 값인가?
4. 사용자가 발급이력으로 제외한 `issuer` 가 아닌가?

위 4개를 모두 만족할 때 후보 카드.

### CardBenefit (월 청구할인) 계산
1. 사용자 전월실적(원) → `kind='basic'` 그룹에서 `threshold_amount ≤ 실적` 중 max threshold row 1개 선택 → `amount`(기본할인)
2. `kind='additional'` 그룹에서도 동일 방식으로 1개 선택 → `amount`(추가할인). 단, 추가할인은 발급 후 `add_discount_months` 동안만 유효
3. monthly 기준 차감액 = 기본할인 + 추가할인 (합산)

### CardAdditionalPromotion (일시금/표시)
- `cashback_amount` 가 있으면 `final_price` 또는 총결제액에서 차감
- 없으면 표시 전용 (가맹점 청구할인, 쿠폰 등)

### 슬롯 동시 적용
- 사용자는 후보 카드 중 슬롯별로 1장씩 선택 (할부 / 무선청구 / 유선청구) — 최대 3장
- 한 카드는 한 슬롯만 점유 (UI 측에서 한 카드 중복 선택 차단)

## 5. 마이그레이션 절차

기존 데이터 보존 불요 → drop & recreate.

1. 기존 `PartnerCard` / `CardBenefit` row 전부 삭제하는 마이그레이션 step 추가 (RunSQL or `Model.objects.all().delete()` in RunPython)
2. 컬럼 변경: `PartnerCard.carrier` (CharField, single) → `carriers` (ArrayField). `benefit_type` / `contact` / `link` 제거 (요구사항에 없음 — 필요 시 보존 검토)
3. `CardIssuer` 신규 모델 + FK 추가 (필수 FK 라 default issuer 필요 → migration 안에서 placeholder issuer 생성 후 모든 카드 연결, 이후 데이터 재입력)
4. 신규 필드 추가 (`signup_start_date`, `add_discount_months`, `min_installment_amount` 등)
5. `CardBenefit` 변경: `condition` (CharField), `is_optional` 제거. `kind` / `threshold_amount` 신설
6. `CardAdditionalPromotion` 신규 모델 추가
7. `phone/constants.py` 에 `DiscountTypeChoices` 추가
8. 어드민(`content_admin.py`) 재구성:
   - `CardIssuerAdmin` 추가
   - `CardBenefitInline` 필드 갱신
   - `CardAdditionalPromotionInline` 추가
9. 시리얼라이저 / 뷰 갱신:
   - `PartnerCardSerializer` 의 `card_benefits` 직렬화 형태 변경
   - 신규 `CardAdditionalPromotionSerializer`, `CardIssuerSerializer`
   - `PartnerCardViewSet` 의 prefetch 갱신
10. 어드민에서 카드 데이터 재입력

## 6. 미해결 / 향후 검토

- 시뮬레이션 화면에서 `add_discount_months` 가 24, 36 등으로 다양할 때, 24개월 할부와 어떻게 평균/표시할지 (UI 디자인 결정 필요)
- 추가할인 시즌(캘린더 기간)이 동일 카드에 여러 번 갱신될 경우의 운영 — 현재는 카드 단일 기간만 보유. 필요 시 `AdditionalDiscountSeason` 별도 모델로 확장
- 발급이력 정확도가 중요해지면(향후 회원 시스템 도입) `CardIssuanceHistory(user, issuer, issued_at)` 모델 추가
