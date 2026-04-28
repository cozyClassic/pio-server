# pio-web 영향 인벤토리 + Cutover 가이드

backend `partner-card-redesign` PR과 동시 머지·동시 배포되어야 하는 pio-web 변경 목록.

> **BREAKING**: `/phone/partner-cards` 응답 스키마가 전면 교체됩니다. pio-web PR 없이 backend만 단독 배포하면 상품 상세 페이지 화이트스크린이 즉시 발생합니다.

---

## 1. 영향 파일 인벤토리

### 1.1 핵심 변경 필수 (breaking 변경 직접 의존)

| 파일 | 라인 | 현재 참조 | 변경 이유 |
|------|------|-----------|-----------|
| `pio-web/lib/fetch-partner-cards.ts` | 5–7 | `PartnerCardBenefit.condition`, `benefitPrice`, `isOptional` | `CardBenefit` 구조 교체 → `kind`, `threshold_amount`, `amount` |
| `pio-web/lib/fetch-partner-cards.ts` | 12 | `PartnerCard.carrier` (단수 `CarrierValue`) | `carriers: CarrierValue[]` 배열로 교체 |
| `pio-web/lib/fetch-partner-cards.ts` | 13 | `PartnerCard.link` | 필드 삭제 |
| `pio-web/lib/fetch-partner-cards.ts` | 15 | `PartnerCard.contact` | 필드 삭제 |
| `pio-web/lib/fetch-partner-cards.ts` | 19–22 | `PartnerCardResBenefit.condition`, `benefit_price`, `is_optional` | API 응답 구조 교체 |
| `pio-web/lib/fetch-partner-cards.ts` | 25–34 | `PartnerCardRes.carrier`, `benefit_type`, `link`, `contact` | 필드 삭제; `issuer`, `carriers[]`, `discount_types[]` 등 신규 추가 |
| `pio-web/lib/fetch-partner-cards.ts` | 43–66 | `parseCardBenefits` — 단수 `card.carrier` 기준 단일 분기 | `card.carriers[]` 배열 순회 다대다 인덱싱으로 재작성 |
| `pio-web/lib/fetch-partner-cards.ts` | 53–57 | `card_benefits` 매핑 `condition/benefit_price/is_optional` | `kind/threshold_amount/amount` 매핑으로 교체 |
| `pio-web/components/productDetail/options/PartnerCardModal.tsx` | 44–47 | `BenefitItemProps.condition`, `benefitPrice` | 새 필드(`kind`, `thresholdAmount`, `amount`)로 교체 |
| `pio-web/components/productDetail/options/PartnerCardModal.tsx` | 49–63 | `BenefitItem` 렌더 (`condition`, `benefitPrice * 24`) | 새 렌더 로직 (`kind` 기반 기본/추가 구분 + `threshold_amount` 표시) |
| `pio-web/components/productDetail/options/PartnerCardModal.tsx` | 142–148 | `card.cardBenefits.map` → `benefit.condition`, `benefit.benefitPrice` | 새 benefit 구조로 갱신 |
| `pio-web/components/productDetail/options/PartnerCardModal.tsx` | 184 | `card.link` (Link href) | `link` 필드 삭제 — 대체 링크 전략 결정 필요 (카드사 공식 URL 등) |

### 1.2 타입 전파 (직접 변경 불필요하나 타입 갱신 후 자동 에러 발생)

| 파일 | 라인 | 현재 참조 | 비고 |
|------|------|-----------|------|
| `pio-web/components/productDetail/options/Main.tsx` | 30 | `import { PartnerCard } from "@/lib/fetch-partner-cards"` | `PartnerCard` 타입 변경 후 자동 전파 — `partnerCards: Map<CarrierValue, PartnerCard[]>` 구조는 유지 |
| `pio-web/components/productDetail/options/Main.tsx` | 375–378 | `getSelectedCarrierPartnerCards()` — `partnerCards.has(selectedCarrier)` | Map 키가 단수 carrier 이므로 `carriers[]` 배열 인덱싱 전략에 따라 수정 필요 |
| `pio-web/components/productDetail/options/Main.tsx` | 636 | `card={getSelectedCarrierPartnerCards()[currentCardIndex]}` | `PartnerCard` 타입 변경 후 prop 타입 불일치 발생 |
| `pio-web/app/mobile/detail/[id]/[carrier]/page.tsx` | 144 | `fetchPartnerCards()` 반환 타입 `Map<CarrierValue, PartnerCard[]>` | fetch 함수 시그니처 유지 가능, 반환 타입만 변경 |

### 1.3 변경 불필요 (참조만 하며 구조 의존 없음)

| 파일 | 라인 | 내용 |
|------|------|------|
| `pio-web/app/api/revalidate/route.ts` | 12 | `"partner-cards"` revalidation tag — 태그 이름 유지이므로 변경 불필요 |
| `pio-web/components/productDetail/options/CleanCondition.tsx` | 22, 30, 73 | `openPartnerCardModal` 콜백 — PartnerCard 데이터 구조와 무관 |
| `pio-web/lib/fetch-partner-cards.ts` | 69–82 | `apiFetch` 호출 경로 `/phone/partner-cards`, ISR tag `"partner-cards"` — 유지 |

---

## 2. API 응답 스키마 변경 매핑표

### 2.1 PartnerCardRes (백엔드 → 프론트 응답 DTO)

| 구 필드 | 신 필드 | 비고 |
|---------|---------|------|
| `carrier: string` | `carriers: string[]` | 단수→배열. `parseCardBenefits` 로직 전면 재작성 필요 |
| `benefit_type: string` | `discount_types: string[]` | 단수→배열 (`CardSlotChoices` 값) |
| `link: string` | *(삭제)* | 카드사 공식 URL 전략 별도 결정 (F4) |
| `contact: string` | *(삭제)* | |
| *(신규)* | `issuer: {id, name}` | `CardIssuer` 중첩 객체 |
| *(신규)* | `signup_start_date: string \| null` | |
| *(신규)* | `signup_end_date: string \| null` | |
| *(신규)* | `add_discount_months: number \| null` | |
| *(신규)* | `add_discount_condition: string` | |
| *(신규)* | `min_installment_amount: number \| null` | |
| *(신규)* | `installment_excluded_items: string` | |
| *(신규)* | `annual_fee: number` | |
| *(신규)* | `additional_promotions: CardAdditionalPromotionRes[]` | |

### 2.2 PartnerCardResBenefit (CardBenefit DTO)

| 구 필드 | 신 필드 | 비고 |
|---------|---------|------|
| `condition: string` | `kind: 'basic' \| 'additional'` | |
| `benefit_price: number` | `amount: number` | |
| `is_optional: boolean` | `threshold_amount: number` | 원 단위 (만원 단위 입력 → 원 단위 저장) |

### 2.3 신규 PartnerCardAdditionalPromotionRes

```typescript
interface CardAdditionalPromotionRes {
  id: number;
  title: string;
  description: string;
  image: string | null;
  target_series: number[];   // ProductSeries id 배열
  min_installment_amount: number | null;
  cashback_amount: number | null;
  sort_order: number;
  is_active: boolean;
}
```

---

## 3. pio-web PR 변경 가이드

### 3.1 `lib/fetch-partner-cards.ts` 전면 재작성

```typescript
// 신규 타입 정의
export interface CardIssuer {
  id: number;
  name: string;
}

export interface PartnerCardBenefit {
  kind: 'basic' | 'additional';
  threshold_amount: number;  // 원 단위
  amount: number;            // 원 단위
}

export interface CardAdditionalPromotion {
  id: number;
  title: string;
  description: string;
  image: string | null;
  target_series: number[];
  min_installment_amount: number | null;
  cashback_amount: number | null;
  sort_order: number;
  is_active: boolean;
}

export interface PartnerCard {
  id: number;
  issuer: CardIssuer;
  name: string;
  image: string;
  carriers: CarrierValue[];         // 배열 (구: 단수 carrier)
  discount_types: string[];          // CardSlotChoices 값 배열
  signup_start_date: string | null;
  signup_end_date: string | null;
  add_discount_months: number | null;
  add_discount_condition: string;
  min_installment_amount: number | null;
  installment_excluded_items: string;
  annual_fee: number;
  cardBenefits: PartnerCardBenefit[];
  additional_promotions: CardAdditionalPromotion[];
  sort_order: number;
  is_active: boolean;
}

// parseCardBenefits: carriers[] 배열 순회로 다대다 인덱싱
const parseCardBenefits = (cardsRes: PartnerCardRes[]): Map<CarrierValue, PartnerCard[]> => {
  const carrierMap = new Map<CarrierValue, PartnerCard[]>();
  cardsRes.forEach((card) => {
    const partnerCard: PartnerCard = {
      ...card,
      cardBenefits: card.card_benefits,
    };
    // 한 카드가 여러 통신사 보유 — 모든 통신사 키에 동일 카드 등록
    card.carriers.forEach((carrier) => {
      if (carrierMap.has(carrier)) {
        carrierMap.get(carrier)!.push(partnerCard);
      } else {
        carrierMap.set(carrier, [partnerCard]);
      }
    });
  });
  return carrierMap;
};
```

### 3.2 `components/productDetail/options/PartnerCardModal.tsx` 갱신 포인트

1. **`BenefitItemProps`** — `condition`/`benefitPrice` → `kind`/`thresholdAmount`/`amount`
2. **`BenefitItem` 렌더** — kind별 "기본할인" / "추가할인" 라벨 표시, `threshold_amount > 0` 시 "전월실적 N만원 이상" 문구 추가
3. **`card.cardBenefits.map`** — 새 benefit 구조로 매핑 갱신
4. **`card.link` (line 184)** — `link` 필드 삭제됨. 대체 전략:
   - `card.issuer.name` 기반 카드사 공식 URL 매핑 테이블 사용
   - 또는 링크 버튼 제거 후 "카드사 문의" 텍스트로 대체
   - pio-web PR에서 결정 필요

### 3.3 `components/productDetail/options/Main.tsx` 확인 사항

- `partnerCards: Map<CarrierValue, PartnerCard[]>` 타입 시그니처 유지 — `parseCardBenefits` 반환 타입과 동일하므로 타입 에러 없음
- `getSelectedCarrierPartnerCards()` 로직 변경 없음 — Map 키는 여전히 단수 carrier 값

---

## 4. Deploy Cutover 절차

### 4.1 전제 조건

- backend PR (이 repo) + pio-web PR 동시 머지 준비 완료
- staging에서 backend + frontend 동시 배포 후 E2E 검증 통과

### 4.2 Staging 검증 체크리스트

```bash
# 1. backend 응답 스키마 검증
curl -s $STAGING_URL/phone/partner-cards | jq '.results[0] | keys'
# 기대 키: ["add_discount_condition","add_discount_months","additional_promotions",
#           "annual_fee","card_benefits","carriers","discount_types","id","image",
#           "installment_excluded_items","is_active","issuer","min_installment_amount",
#           "name","signup_end_date","signup_start_date","sort_order"]

# 2. 사라진 구 필드 부재 확인
curl -s $STAGING_URL/phone/partner-cards | jq '.results[0] | has("carrier", "benefit_type", "link", "contact")'
# 기대: false (또는 모두 false)

# 3. card_benefits 새 구조 확인
curl -s $STAGING_URL/phone/partner-cards | jq '.results[0].card_benefits[0] | keys'
# 기대: ["amount","id","kind","threshold_amount"]
```

- Next.js staging: `/mobile/detail/{product_id}/{carrier}` → HTTP 200 + 카드 모달 정상 렌더
- 카드 모달에서 기본할인 / 추가할인 항목 표시 확인
- `PartnerCardModal` 내 `BenefitItem` 렌더 정상 확인

### 4.3 Production Deploy 순서

1. **backend deploy gate**: pio-web PR ready + staging 검증 통과 확인 후에만 진행
2. **동시 배포**: backend deploy와 pio-web deploy를 같은 deploy window에서 실행
3. **단독 배포 금지**: backend만 먼저 배포하면 `/mobile/detail/` 화이트스크린 즉시 발생

### 4.4 Rollback 계획

| 상황 | 조치 |
|------|------|
| backend만 배포됨 (pio-web 미배포) | pio-web 긴급 배포 또는 backend rollback |
| 양쪽 배포 후 카드 모달 이상 | pio-web rollback (Next.js ISR 캐시 `revalidate` 태그 `partner-cards` 유지) |
| DB 마이그레이션 0069 이상 발생 | `pg_dump` 백업본(Step 0 산출물) 사용 — 0068 reverse는 noop, 0067로만 완전 복원 가능 |

---

## 5. PR 연동 규칙

- backend PR description: `[BREAKING] PartnerCard redesign — requires pio-web PR #{번호} simultaneous merge`
- pio-web PR description: `depends on backend PR #{번호} — simultaneous deploy required`
- PR merge 직전 두 PR이 모두 approved + CI green 확인 후 동시 머지
- CHANGELOG에 `[BREAKING]` 항목 추가
- Channel Talk 팀 채널에 배포 전 사전 알림
