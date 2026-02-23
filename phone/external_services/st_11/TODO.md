# 해야할 작업 정리

## 가격변경 관련 작업

### 예상 입력

1. 현재 저장된 `phone.models.ProductOption` 테이블의 각종 할인 관련 데이터
2. 연결된 `device_variant`, `plan.carrier`, `plan_price` 등 참조 가능
3. `ProductOption.id`를 FK로 갖는 `OpenMarketProductOption`과,
   `OpenMarketProductOption.open_market_product`의 `om_product_id` 또는 `seller_code`로 수정 대상 상품 ID 확인 가능

### 기대 결과

1. 11번가 상품의 기본 판매가격 및 옵션 가격이 DB 기준 목표가로 반영됨

### 11번가 지원 API 목록

1. 상품 가격 변경 (단일상품)
2. 상품 옵션 내용 및 가격 변경 (단일상품)

---

## 작업 계획

### 0. 인프라 구성 (Railway)

Railway에 아래 서비스를 추가해야 함:

| 서비스        | 역할                           | 실행 커맨드                                  |
| ------------- | ------------------------------ | -------------------------------------------- |
| Redis         | Celery 브로커 + 결과 백엔드    | Railway Redis 플러그인                       |
| Celery Worker | Task 실행                      | `celery -A phoneinone_server worker -l info` |
| Celery Beat   | 주기적 Task 스케줄링 (필요 시) | `celery -A phoneinone_server beat -l info`   |

- Worker와 Beat는 동일한 Django 앱 이미지를 사용하되, 시작 커맨드만 다름
- 환경변수 `celery_broker` (Redis URL)을 Worker / Beat / Django 웹서버 모두에 주입

### 1. Django Celery 설정

- `phoneinone_server/celery.py` 생성
- `settings.py`에 추가:
  - `CELERY_BROKER_URL` (Redis)
  - `CELERY_RESULT_BACKEND` (Redis)
  - `CELERY_TASK_SERIALIZER = 'json'`
  - `CELERY_TASK_ACKS_LATE = True` (Task 실패 시 재처리 보장)
- Queue는 단일 FIFO Queue 사용 (같은 상품의 Task A→B→C 순서 보장)

### 2. 모델 추가/수정

`OpenMarketProduct` (또는 기존 모델)에 필드 추가:

- `registered_price` (IntegerField): DB에서 관리하는 현재 11번가 등록가
  - 최초 등록 시 수동 입력, 이후 Task 성공 시마다 자동 갱신
- `last_price_updated_at` (DateTimeField): 마지막 가격 갱신 시각

--- 여기까지 완료 ---

### 3. Celery Task 설계

> **공통 원칙**
>
> - 모든 Task는 단일 FIFO Queue에 상품별로 순서대로 적재 → 같은 상품의 A→B→C 순서 보장
> - 각 Task 성공 시 다음 Task를 Queue에 추가 (체이닝)
> - Task 실패 시 ChannelTalk 알림 발송 후 해당 상품 중단 (재시도 없음)
> - 11번가 API 호출 성공 직후 DB 업데이트를 하나의 세트로 처리

#### Task A: 옵션 정리

- 동작:
  1. 해당 상품의 기존 옵션 중 기본 옵션(가격 0원)만 남기고 나머지 전부 제거
  2. 11번가 옵션 변경 API 호출
- 성공 → Task B를 Queue에 추가
- 실패 → ChannelTalk 알림 발송

> 옵션 선택 가능한 상품은 옵션이 하나도 없으면 에러 발생하므로, 기본 옵션(가격 0원) 반드시 유지

#### Task B: 판매가 단계적 인하

- 입력값 (Task 파라미터에 포함 — DB N+1 방지):
  - `current_price`: 현재 11번가 등록가 (DB `registered_price` 기준, 트리거 시점에 읽어서 파라미터로 전달)
  - `target_price`: 목표가 (수수료 제외 1만원 남기는 최고가 요금제 기준, 트리거 시점에 계산)
- 동작:
  1. `current_price == target_price`이면 Task C로 진행
  2. `current_price > target_price`이면 1회 인하 가능한 최저가 계산:
     - `next_price = max(target_price, ceil(current_price * 0.2))` ← 최대 80% 인하
  3. 11번가 판매가 변경 API 호출 (`next_price`)
  4. API 성공 시 즉시 DB `registered_price` = `next_price` + `last_price_updated_at` 갱신
  5. `next_price > target_price`이면 Task B를 `current_price=next_price`로 다시 Queue에 추가
  6. `next_price == target_price`이면 Task C를 Queue에 추가
- 실패 → ChannelTalk 알림 발송

> **동기화 주의**: 트리거 시점의 DB `registered_price`가 실제 11번가 가격과 다를 수 있음
> (이전 작업 실패 등). 이 경우를 자동으로 감지하는 수단이 없으므로,
> Task 실패 시 ChannelTalk 메시지에 `current_price`와 `target_price`를 함께 포함시켜 수동 대응 가능하게 함

#### Task C: 옵션 추가

- 전제: 판매가 = 목표가 도달 상태
- 동작:
  1. 해당 상품의 하위 요금제 옵션 목록 조회
  2. 각 옵션의 가격 계산:
     - **수수료 포함** 마진 계산 (수수료 정산은 옵션가 아닌 상품 판매가 기준임을 반영)
     - option rate limit 확인: 상품 판매가 기준 **-50% ~ +300%** 범위 내인지 검증
  3. 범위 내 옵션만 11번가 옵션 추가 API 호출
  4. API 성공 시 DB 업데이트
  5. 범위 초과로 추가 불가한 옵션 → 스킵 + 별도 로깅 (해피콜 안내 대상)
- 실패 → ChannelTalk 알림 발송

### 4. 어드민 트리거

- 위치: Django Admin — `Product` 또는 통신사(Carrier) 기준 액션
- 액션명: `"OpenMarket 가격 업데이트"`
- 동작:
  1. 트리거 시점에 DB에서 전체 대상 옵션 테이블 **1회만** 조회
  2. 각 상품마다 `target_price` 계산 후, Task A 파라미터 구성
  3. 상품별로 Task A를 FIFO Queue에 추가 (Task A 성공 시 B, B 성공 시 C 체이닝)
  4. 어드민 화면에 `"N개 상품에 대한 업데이트 Task가 Queue에 추가되었습니다"` 메시지 표시

---

## 11번가 규칙 요약 (READ_ME.md 참조)

| 규칙                   | 내용                                                        |
| ---------------------- | ----------------------------------------------------------- |
| 판매가 변경 한도       | 현재 등록가 기준 1회 최대 80% 인하                          |
| 옵션가격 범위          | 상품 판매가 기준 -50% ~ +300%                               |
| 옵션 있을 때 가격 변경 | 옵션가격 범위를 위반하는 판매가 변경 불가                   |
| 수수료 정산 기준       | 옵션가격이 아닌 상품 판매가 기준                            |
| 목표 판매가 기준       | 최고가 요금제 기준, 수수료 제외 1만원 남기기                |
| 하위 요금제 처리       | option rate limit 내이면 옵션으로 추가, 초과 시 해피콜 안내 |
