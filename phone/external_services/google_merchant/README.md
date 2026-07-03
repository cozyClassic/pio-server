# Google Merchant API 상품 피드

활성 상품을 Google Merchant Center에 **API 데이터소스로 직접 푸시**한다.
구글이 랜딩 페이지에서 가격을 추측(정상가/월납 혼동)하는 대신, 우리가 지정한
**최저 완납가(final_price)**를 권위 소스로 넘겨 '가격 불일치'를 원천 차단한다.

가격은 랜딩 페이지 JSON-LD와 **동일한** `ProductDetailSerializer.get_best_options`
경로에서 파생하므로 피드값과 페이지값이 어긋나지 않는다.

## 1) Google 쪽 사전 설정 (콘솔/UI)

1. GCP 프로젝트에서 **Merchant API** 사용 설정.
2. **서비스 계정** 생성 → JSON 키 발급.
3. Merchant Center → 설정 → **사용자 및 액세스**에서 서비스계정 이메일 추가
   (API 접근 권한 부여).
4. Merchant Center **계정 ID(merchantId)** 확인.
5. Merchant Center → 데이터소스 → **"API" 유형 기본 데이터소스** 생성 →
   데이터소스 ID 확인. (feed label `KR`, 언어 `ko`)

## 2) 서버 환경변수

```bash
GOOGLE_MERCHANT_ACCOUNT_ID=<merchantId>
GOOGLE_MERCHANT_DATASOURCE_ID=<dataSourceId>
GOOGLE_MERCHANT_CONTENT_LANGUAGE=ko                      # 기본값
GOOGLE_MERCHANT_FEED_LABEL=KR                            # 기본값
```

서비스계정 인증 (우선순위 순, 하나만 있으면 됨):

```bash
# ① 배포(Railway 등) 권장 — SA JSON '내용' 전체를 이 한 변수에 붙여넣는다(파일 불필요)
GOOGLE_MERCHANT_SA_INFO={"type":"service_account","project_id":"phoneinone", ... }
# ② 파일 경로로 줄 수도 있음
GOOGLE_MERCHANT_SA_JSON=/path/to/google-merchant.json
# ③ 둘 다 비우면 BASE_DIR/google-merchant.json 자동 사용(로컬 편의) → 없으면 ADC
```

- **로컬**: `phoneinone_server/google-merchant.json` 파일만 두면 자동 인식(③).
- **배포**: 파일을 올리지 말고 **`GOOGLE_MERCHANT_SA_INFO`** 에 JSON 내용을 그대로 넣는다(①).
  값에 개행이 있어도 되고, 파싱은 `json.loads`가 처리한다.
- OAuth `client_secret.json` 은 **1회성 등록 커맨드 전용(로컬)** 이라 배포/서버 env에 넣을 필요 없음.

## 3) 패키지 설치

```bash
pip install -r requirements.txt   # google-shopping-merchant-products, google-shopping-type
```

## 4) 검증 → 전송

```bash
# (a) 크리덴셜/패키지 없이 페이로드만 검증 — offerId·가격·링크 확인
python manage.py push_google_merchant --dry-run --limit 3

# (b) 실제 전송(일부)
python manage.py push_google_merchant --limit 3

# (c) 전체 전송
python manage.py push_google_merchant
```

## 5) 주기 실행 (필수)

상품은 **최소 30일 내 refresh** 되지 않으면 만료된다. `settings.py`의
`CELERY_BEAT_SCHEDULE`에 있는 `push-google-merchant-hourly` 항목의 주석을 해제해
`phone.tasks.task_push_google_merchant`를 주기 실행한다.

## 매핑 규칙 / 주의

- **상품당 오퍼 1개**, `price = 전 통신사 최저 완납가`, `link = /mobile/detail/{id}/v2/mvno`.
  현재 배포된 랜딩 JSON-LD가 단일 최저가 Offer를 노출하기 때문이다.
  프론트를 **통신사별 AggregateOffer**로 배포하면, `product_builder`도 통신사별
  오퍼로 확장해야 정합이 유지된다.
- 무재고 상품은 전송하지 않는다(네이버 EP와 동일).
- proto 필드/enum 명칭은 공식 샘플 기준이다. 설치된 라이브러리 버전과 다를 수 있으니
  최초 도입 시 `--dry-run` → `--limit` 순으로 단계 검증할 것.
  https://developers.google.com/merchant/api/samples/insert-product-input
