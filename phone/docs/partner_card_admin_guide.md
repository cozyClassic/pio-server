# 제휴카드 운영자 재입력 가이드 (PartnerCard Redesign v2)

마이그레이션 0069 적용 후 기존 카드 데이터가 모두 삭제됩니다. 이 가이드에 따라 어드민에서 데이터를 재입력하고 0070 finalize 마이그레이션을 적용합니다.

---

## 1. 사전 확인

0069 마이그레이션이 적용되었는지 확인합니다:

```bash
cd /Users/pro/Desktop/Codings/phone_in_one/phoneinone_server
source ../pio/bin/activate
python manage.py showmigrations phone | grep 006
```

`[X] 0069_partner_card_redesign` 가 표시되어야 합니다.

---

## 2. 재입력 순서 개요

**반드시 아래 순서로 진행합니다. CardIssuer 없이 PartnerCard를 만들 수 없습니다.**

```
Step A — CardIssuer (카드사) 등록
    ↓
Step B — PartnerCard (제휴카드) 생성
    ↓
Step C — CardBenefit (카드혜택) inline 입력
    ↓
Step D — CardAdditionalPromotion (추가프로모션) inline 입력
    ↓
Step E — 검증 및 0070 finalize 적용
```

---

## 3. Step A — CardIssuer (카드사) 등록

어드민 URL: `/admin/phone/cardissuer/add/`

| 필드 | 설명 | 예시 |
|------|------|------|
| `name` | 카드사명 (unique) | `신한카드`, `KB국민카드`, `현대카드`, `삼성카드`, `롯데카드` |
| `sort_order` | 노출 순서 (낮을수록 앞) | `1`, `2`, `3` … |
| `is_active` | 활성화 여부 | 체크 (기본값) |

**주의**: 카드사명은 나중에 고객이 발급이력 필터로 선택하는 단위입니다. 정확한 공식 명칭을 사용하세요.

---

## 4. Step B — PartnerCard (제휴카드) 생성

어드민 URL: `/admin/phone/partnercard/add/`

### 4.1 기본 정보

| 필드 | 설명 |
|------|------|
| `issuer` | 위에서 등록한 CardIssuer 선택 (autocomplete) |
| `name` | 카드 상품명 (예: `신한카드 Deep Dream`) |
| `image` | 카드 이미지 업로드 (가로형 카드 이미지 권장) |
| `sort_order` | 노출 순서 |
| `is_active` | 활성화 여부 |

### 4.2 통신사 선택 (carriers) — 체크박스 다중 선택

카드가 적용되는 통신사를 **모두 체크**합니다. 하나도 체크하지 않으면 어떤 고객에게도 노출되지 않습니다.

- `SK`
- `KT`
- `LG`
- `알뜰폰`

### 4.3 할인 유형 선택 (discount_types) — 체크박스 다중 선택

이 카드가 차지할 수 있는 슬롯을 **모두 체크**합니다. (한 카드가 여러 슬롯 후보를 가질 수 있으나 동시에 한 슬롯만 점유)

- `할부` — 스마트폰 할부금 청구 슬롯
- `무선청구` — 이동통신 요금 청구 슬롯
- `유선청구` — 유선 인터넷/TV 청구 슬롯

### 4.4 가입 가능 기간

| 필드 | 설명 | 예시 |
|------|------|------|
| `signup_start_date` | 가입 시작일 (비어 있으면 기간 제한 없음) | `2026-01-01` |
| `signup_end_date` | 가입 종료일 (비어 있으면 기간 제한 없음) | `2026-04-30` |

### 4.5 추가할인 정보

| 필드 | 설명 | 예시 |
|------|------|------|
| `add_discount_months` | 발급 후 추가할인 적용 개월수 | `24` |
| `add_discount_condition` | 추가할인 조건 (자유 텍스트) | `카드 발급 후 24개월간 적용` |

### 4.6 기타 조건

| 필드 | 설명 | 예시 |
|------|------|------|
| `min_installment_amount` | 최소 할부금 (원). 라이트할부카드 전용. 조건 없으면 빈칸 | `200000` |
| `installment_excluded_items` | 전월실적 제외 항목 (자유 텍스트) | `공과금, 아파트관리비` |
| `annual_fee` | 연회비 (원). 없으면 `0` | `10000` |

---

## 5. Step C — CardBenefit (카드혜택) inline 입력

PartnerCard 편집 페이지 하단의 **CardBenefit** inline 섹션에서 입력합니다.

> **중요**: 전월실적(`threshold_amount_manwon`)은 **만원 단위**로 입력합니다. DB에는 자동으로 원 단위로 변환되어 저장됩니다.

| 필드 | 설명 | 예시 |
|------|------|------|
| `kind` | 혜택 종류 | `기본할인` 또는 `추가할인` |
| `threshold_amount_manwon` | 전월실적 기준 **(만원 단위 입력)** | `30` (→ DB에 `300000`원으로 저장) |
| `amount` | 할인 금액 (원 단위 직접 입력) | `12000` |

### 5.1 입력 예시 (기본할인 2구간)

| kind | threshold_amount_manwon | amount |
|------|------------------------|--------|
| 기본할인 | `0` | `6000` |
| 기본할인 | `30` | `12000` |

위 예시의 의미: 전월실적 0원 이상이면 6,000원 할인, 30만원 이상이면 12,000원 할인 (중복 적용 X, 높은 구간 1개만 선택).

### 5.2 전월실적 0원 처리

"전월실적 무관" 혜택은 `threshold_amount_manwon = 0`으로 입력합니다.

### 5.3 DB 저장값 검증 방법

입력 후 저장 완료 시점에서 다음 명령으로 확인:

```bash
python manage.py shell -c "
from phone.models import CardBenefit
for b in CardBenefit.objects.order_by('card', 'kind', 'threshold_amount'):
    print(b.card.name, b.kind, b.threshold_amount, '원', b.amount, '원')
"
```

---

## 6. Step D — CardAdditionalPromotion (추가프로모션) inline 입력

PartnerCard 편집 페이지 하단의 **CardAdditionalPromotion** inline 섹션에서 입력합니다.

| 필드 | 설명 | 예시 |
|------|------|------|
| `title` | 프로모션 제목 | `갤럭시 S25 전용 캐시백` |
| `description` | 상세 설명 (자유 텍스트) | `구매 후 3개월 뒤 10만원 캐시백` |
| `image` | 프로모션 이미지 (선택) | |
| `target_series` | 대상 단말 시리즈 (복수 선택 가능) | `갤럭시 S25`, `갤럭시 S24` |
| `min_installment_amount` | 적용 최소 할부금 (원). 조건 없으면 빈칸 | `800000` |
| `cashback_amount` | 시뮬레이션 차감용 일시금 (원). 없으면 빈칸 | `100000` |
| `sort_order` | 노출 순서 | `1` |
| `is_active` | 활성화 여부 | 체크 |

**`cashback_amount`**: 시뮬레이션에서 실제 금액 차감에 사용됩니다. 가맹점 청구할인, 쿠폰 등 정형화하기 어려운 혜택은 빈칸으로 두고 `description`에 텍스트로 입력합니다.

---

## 7. Step E — 검증 및 0070 finalize 적용

### 7.1 어드민 재입력 완료 확인

모든 카드 재입력 후 아래 명령으로 데이터 정합성을 확인합니다:

```bash
python manage.py shell -c "
from phone.models import PartnerCard, CardBenefit, CardIssuer, CardAdditionalPromotion

print('=== 카드사 ===')
for ci in CardIssuer.objects.all():
    print(f'  {ci.name} (id={ci.pk}, active={ci.is_active})')

print()
print('=== 제휴카드 ===')
for pc in PartnerCard.objects.select_related('issuer'):
    benefits = pc.card_benefits.count()
    promos = pc.additional_promotions.count()
    print(f'  [{pc.issuer.name}] {pc.name} | carriers={pc.carriers} | benefits={benefits} | promos={promos} | active={pc.is_active}')

print()
print('=== 통계 ===')
print('CardIssuer:', CardIssuer.objects.count())
print('PartnerCard:', PartnerCard.objects.count())
print('CardBenefit:', CardBenefit.objects.count())
print('CardAdditionalPromotion:', CardAdditionalPromotion.objects.count())
"
```

### 7.2 issuer 누락 카드 확인 (0070 적용 전 필수)

0070 마이그레이션은 `issuer FK`를 `null=False`로 좁힙니다. issuer가 없는 카드가 있으면 실패합니다.

```bash
python manage.py shell -c "
from phone.models import PartnerCard
no_issuer = PartnerCard.objects.filter(issuer__isnull=True)
if no_issuer.exists():
    print('경고: issuer 미설정 카드가 있습니다 —', list(no_issuer.values_list('id', 'name')))
else:
    print('OK: 모든 카드에 issuer가 설정되어 있습니다')
"
```

issuer 누락 카드가 있으면 어드민에서 issuer를 지정한 후 0070을 적용합니다.

### 7.3 0070 finalize 마이그레이션 적용

```bash
cd /Users/pro/Desktop/Codings/phone_in_one/phoneinone_server
source ../pio/bin/activate
python manage.py migrate phone 0070
```

예상 출력:
```
Operations to perform:
  Target specific migration: 0070_partner_card_finalize, from phone
Running migrations:
  Applying phone.0070_partner_card_finalize... OK
```

### 7.4 API 응답 sanity 확인

```bash
# 개발 서버 실행 중일 때
curl -s http://localhost:8000/phone/partner-cards | python -m json.tool | head -60

# 새 스키마 키 확인
curl -s http://localhost:8000/phone/partner-cards | python -c "
import sys, json
data = json.load(sys.stdin)
if data.get('results'):
    print('응답 키:', sorted(data['results'][0].keys()))
    print('card_benefits 키:', sorted(data['results'][0]['card_benefits'][0].keys()) if data['results'][0]['card_benefits'] else '없음')
else:
    print('카드 데이터 없음 — 재입력 필요')
"
```

기대 응답 키:
```
응답 키: ['add_discount_condition', 'add_discount_months', 'additional_promotions',
          'annual_fee', 'card_benefits', 'carriers', 'discount_types', 'id', 'image',
          'installment_excluded_items', 'is_active', 'issuer', 'min_installment_amount',
          'name', 'signup_end_date', 'signup_start_date', 'sort_order']
card_benefits 키: ['amount', 'id', 'kind', 'threshold_amount']
```

**사라진 구 필드 확인** (아래 키가 없어야 정상):
- `carrier` (단수) → `carriers` (배열)로 교체
- `benefit_type`
- `link`
- `contact`

---

## 8. S3 Orphan 이미지 정리 (F8 Follow-up)

0068 마이그레이션으로 삭제된 구 PartnerCard 이미지 파일이 S3에 잔류합니다. Step 0에서 저장한 `partner_card_image_keys_*.txt` 파일을 기준으로 재입력 완료 후 **1주일 grace period** 이후 정리합니다. 이 작업은 별도 운영 작업으로 분리됩니다.

---

## 9. 문제 발생 시

| 증상 | 원인 | 조치 |
|------|------|------|
| `0070` 적용 실패 `IntegrityError` | issuer NULL 카드 존재 | 7.2 확인 후 issuer 입력 완료 후 재시도 |
| 어드민 저장 시 carriers 오류 | 통신사 미선택 | carriers 체크박스에서 1개 이상 선택 |
| `threshold_amount`가 0으로 저장됨 | `threshold_amount_manwon` 미입력 | inline에서 만원 단위 값 입력 확인 |
| API 응답에 구 필드(`carrier`, `link`) 여전히 존재 | serializer 갱신 미배포 | backend 배포 상태 확인 |
| `/mobile/detail/` 화이트스크린 | pio-web 미배포 상태에서 backend만 배포됨 | pio-web 긴급 배포 또는 backend rollback |
