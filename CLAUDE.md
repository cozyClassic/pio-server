# CLAUDE.md

This file provides guidance to Claude Code when working with the phoneinone_server Django backend.

## Project Overview

PhoneInOne (폰인원) - 한국 휴대폰 및 인터넷 서비스 이커머스 플랫폼의 Django REST API 백엔드

## Quick Start

```bash
# 가상환경 활성화
source ../pio/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
python manage.py runserver

# 마이그레이션
python manage.py makemigrations
python manage.py migrate

# 테스트 실행
python manage.py test
```

## Project Structure

```
phoneinone_server/
├── phoneinone_server/              # Django 메인 설정
│   ├── settings.py                 # 환경설정 (DB, AWS, CORS, Celery 등)
│   ├── urls.py                     # 루트 URL 라우팅
│   └── wsgi.py / asgi.py
├── phone/                          # 핵심 휴대폰 판매 앱
│   ├── models.py                   # 35+ 모델 (Product, Order, Plan, Device, OpenMarket 등)
│   ├── views.py                    # REST API ViewSets (17개)
│   ├── serializers.py              # DRF Serializers (26개)
│   ├── admin.py                    # Django Admin 설정 (nested admin, excel import/export)
│   ├── signals.py                  # post_save/post_delete 시그널 (ProductOption → best_price 갱신)
│   ├── managers.py                 # SoftDeleteManager, SoftDeleteQuerySet
│   ├── constants.py                # CarrierChoices, DiscountType, ContractType, OpenMarketChoices
│   ├── utils.py                    # UniqueFilePathGenerator
│   ├── revalidate.py               # Next.js ISR 캐시 무효화
│   ├── tasks.py                    # Celery 비동기 태스크 (오픈마켓)
│   ├── forms.py                    # Django Forms
│   ├── external_services/          # 외부 서비스 연동
│   │   ├── channel_talk.py         # Channel Talk 주문 알림
│   │   ├── naver_compare/          # 네이버 가격비교 연동
│   │   ├── ssg/                    # SSG 오픈마켓 연동
│   │   └── st_11/                  # 11번가 오픈마켓 연동 (상품등록, 주문확인)
│   ├── inventory/                  # 재고 관리
│   │   ├── api_smartel.py          # Smartel API (DI 대리점 재고)
│   │   ├── kt_first/              # KT First 대리점 재고
│   │   └── lg_hunet/              # LG Hunet 대리점 재고
│   ├── product_option_update/      # Excel 임포트 스크립트 (통신사별 가격)
│   │   ├── excel_sk_smartel.py
│   │   ├── excel_kt_first.py
│   │   └── excel_lg_hutel.py
│   └── official_link_update/       # 공식 계약 링크 관리
├── internet/                       # 인터넷/TV 번들 서비스 앱
│   ├── models.py                   # InternetPlan, TVPlan, BundleCondition, BundleDiscount 등
│   ├── views.py                    # InternetCarrier, InternetPlan, Inquiry ViewSets
│   ├── serializers.py
│   └── urls.py
├── scraps/                         # 스크랩/부가 앱
│   └── models.py
├── templates/admin/                # 커스텀 Admin 템플릿
├── static/                         # 정적 파일 (admin, css, js, tinymce)
├── requirements.txt                # Python 의존성 (131개 패키지)
└── manage.py
```

## Core Patterns

### Soft Delete Pattern

모든 주요 모델은 `SoftDeleteModel`을 상속:

```python
class SoftDeleteModel(models.Model):
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    deleted_at = DateTimeField(null=True, blank=True)  # Soft delete
    objects = SoftDeleteManager()  # deleted_at IS NULL만 반환

    def delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])
```

- Hard delete 대신 `deleted_at` 필드 설정
- `SoftDeleteQuerySet.hard_delete()` 로 실제 삭제 가능
- `SoftDeleteQuerySet.deleted()` 로 삭제된 레코드 조회

### Price Calculation (ProductOption)

```python
final_price = device_price - additional_discount
if discount_type == '공시지원금':
    final_price -= subsidy_amount
    if contract_type == '번호이동':
        final_price -= subsidy_amount_mnp

# 월 할부금 (24개월, 할부이자 6.25%)
monthly_payment = (final_price * 1.0625 / 24) + plan_price
# 선택약정인 경우 plan_price *= 0.75
```

### Auto Best Option Update (signals.py)

`ProductOption` 저장/삭제 시 `Product.best_price_option` 자동 갱신:

```python
@receiver(post_save, sender=ProductOption)
def handle_product_option_save(sender, instance, **kwargs):
    ProductOption._add_pending_product(instance.product_id)
    transaction.on_commit(ProductOption._update_pending_products)
```

- Thread-local 변수로 pending product 관리 (bulk 연산 최적화)
- `post_save`와 `post_delete` 모두 등록

## Key Models

### phone 앱 - 핵심 모델

| Model                  | Description                                                                   |
| ---------------------- | ----------------------------------------------------------------------------- |
| `Device`               | 단말기 (model_name, brand, series)                                            |
| `DeviceVariant`        | 단말기 옵션 - 저장용량 (storage_capacity, device_price, 통신사별 name/price)  |
| `DeviceColor`          | 단말기 색상 (color, color_code, sort_order)                                   |
| `DevicesColorImage`    | 색상별 이미지 (device_color FK, image)                                        |
| `Plan`                 | 통신사 요금제 (carrier, price, data_allowance, membership_level)              |
| `ProductOption`        | **핵심** 상품옵션 = 단말기변형 + 요금제 + 할인 (final_price, monthly_payment) |
| `Product`              | 판매 상품 (device, best_price_option, is_featured, is_active, views)          |
| `ProductDetailImage`   | 상품 상세 이미지 (type: pc/mobile/detail)                                     |
| `ProductSeries`        | 제품 시리즈 그룹 (name, sort_order)                                           |
| `Order`                | 주문 (customer info, status, shipping, simple_history 추적)                   |
| `CreditCheckAgreement` | 신용조회 동의서 이미지 (order FK)                                             |

### phone 앱 - 콘텐츠/마케팅 모델

| Model            | Description                                                |
| ---------------- | ---------------------------------------------------------- |
| `Review`         | 상품 리뷰 (rating 1-5, comment, image, is_public)          |
| `FAQ`            | FAQ (category, question, answer)                           |
| `Notice`         | 공지사항 (type: caution/event/general, TinyMCE HTML)       |
| `Banner`         | 배너 (image_pc, image_mobile, location, is_active)         |
| `Event`          | 이벤트 (thumbnail, description HTML, start_date, end_date) |
| `DecoratorTag`   | 상품 태그/뱃지 (name, text_color, tag_color, product M2M)  |
| `PartnerCard`    | 제휴 카드 할인 (carrier, benefit_type, name)               |
| `CardBenefit`    | 카드 혜택 상세 (condition, benefit_price, is_optional)     |
| `PolicyDocument` | 약관/개인정보처리방침 (document_type, content file)        |

### phone 앱 - 가격/재고/오픈마켓 모델

| Model                      | Description                                                     |
| -------------------------- | --------------------------------------------------------------- |
| `PriceHistory`             | 가격 추적 (product, carrier, plan, final_price, price_at)       |
| `PriceNotificationRequest` | 가격 알림 요청 (product, customer_phone, target_price)          |
| `Dealership`               | 대리점 정보 (name, carrier, contact_number, manager)            |
| `OfficialContractLink`     | 공식 계약 링크 (dealer + device_variant + contract_type unique) |
| `Inventory`                | 대리점 재고 (device_variant + device_color + dealership unique) |
| `OpenMarket`               | 오픈마켓 설정 (source, commission_rate, api_key)                |
| `OpenMarketProduct`        | 오픈마켓 상품 (om_product_id, registered_price)                 |
| `OpenMarketProductOption`  | 오픈마켓 옵션 가격 (om_id, option_name, price)                  |
| `OpenMarketOrder`          | 오픈마켓 주문 중복방지 (source, external_order_id)              |

### phone 앱 - 진단 모델

| Model              | Description      |
| ------------------ | ---------------- |
| `DiagnosisLog`     | 단말기 진단 로그 |
| `DiagnosisInquiry` | 단말기 진단 문의 |

### internet 앱 모델

| Model                | Description                                     |
| -------------------- | ----------------------------------------------- |
| `InternetCarrier`    | ISP 제공자 (KT, SK, LG)                         |
| `InternetPlan`       | 인터넷 요금제 (speed, internet_price_per_month) |
| `TVPlan`             | TV 요금제 (channel_count, tv_price_per_month)   |
| `WifiOption`         | WiFi 임대 옵션                                  |
| `SettopBoxOption`    | 셋톱박스 임대 옵션                              |
| `BundleCondition`    | 인터넷+TV+WiFi 결합 조건                        |
| `BundleDiscount`     | 결합 할인                                       |
| `BundlePromotion`    | 결합 프로모션 (쿠폰, 현금)                      |
| `InstallationOption` | 설치비 (유형별: I/T/AI/AT)                      |
| `Inquiry`            | 고객 문의                                       |

## Constants (phone/constants.py)

```python
CarrierChoices:      "SK", "KT", "LG", "알뜰폰"
DiscountTypeChoices: "공시지원금", "선택약정"
ContractTypeChoices: "신규", "번호이동", "기기변경"
OpenMarketChoices:   "11번가", "G마켓 옥션", "SSG", "롯데ON", "네이버 가격비교"
```

## API Endpoints

### Phone API (`/api/` 또는 `/phone/`)

| Endpoint                       | Methods           | Description                                             |
| ------------------------------ | ----------------- | ------------------------------------------------------- |
| `/products`                    | GET               | 상품 목록 (filter: brand, series, carrier, is_featured) |
| `/products/<id>`               | GET               | 상품 상세 (조회수 증가, 재고/옵션 포함)                 |
| `/product-series`              | GET               | 제품 시리즈 목록                                        |
| `/orders`                      | GET, POST         | 주문 조회(name+phone 필수)/생성 (→ Channel Talk 알림)   |
| `/orders/<id>`                 | GET               | 주문 상세                                               |
| `/orders/<id>/credit-check`    | POST              | 신용조회 동의서 업로드                                  |
| `/faqs`                        | GET               | FAQ 목록                                                |
| `/notices`                     | GET               | 공지사항 (filter: type)                                 |
| `/notices/<id>`                | GET               | 공지사항 상세                                           |
| `/banners`                     | GET               | 활성 배너 목록                                          |
| `/reviews`                     | GET, POST         | 리뷰 목록/생성 (multipart)                              |
| `/events`                      | GET               | 이벤트 목록                                             |
| `/events/<id>`                 | GET               | 이벤트 상세                                             |
| `/partner-cards`               | GET               | 파트너 카드 목록                                        |
| `/policies`                    | GET               | 약관/개인정보처리방침                                   |
| `/devices`                     | GET               | 단말기 목록 (variants, 이미지 포함)                     |
| `/plans`                       | GET               | 요금제 목록                                             |
| `/product-options`             | GET               | 상품옵션 목록 (filter: dv_id)                           |
| `/price-notification-requests` | GET, POST, DELETE | 가격 알림 CRUD                                          |
| `/price-history-chart`         | GET               | 가격 변동 차트 데이터                                   |
| `/diagnosis-logs`              | POST              | 진단 로그 생성                                          |
| `/diagnosis-inquiries`         | POST              | 진단 문의 생성                                          |

### Internet API (`/internet/`)

| Endpoint     | Methods | Description                                  |
| ------------ | ------- | -------------------------------------------- |
| `/carriers`  | GET     | 인터넷 제공자 목록                           |
| `/plans`     | GET     | 인터넷 요금제 + 번들/할인/프로모션 중첩 구조 |
| `/inquiries` | POST    | 고객 문의 생성                               |

### System Endpoints

| Endpoint     | Description           |
| ------------ | --------------------- |
| `/`          | Health check          |
| `/db-check`  | DB 연결 확인          |
| `/env-check` | 환경변수 확인         |
| `/swagger/`  | API 문서 (DEBUG=True) |

## External Services

### AWS S3 + CloudFront

- 이미지 저장: S3 → CloudFront CDN URL 변환

### Channel Talk

- 주문 생성 시 팀 채널에 알림 (`external_services/channel_talk.py`)

### 오픈마켓 연동

- **11번가** (`external_services/st_11/`): 상품 등록, 가격 업데이트, 주문 확인
- **SSG** (`external_services/ssg/`): SSG 오픈마켓 연동
- **네이버 가격비교** (`external_services/naver_compare/`): 가격비교 플랫폼 연동

### 대리점 재고 관리

- **Smartel API** (`inventory/api_smartel.py`): DI 대리점 재고 조회
- **KT First** (`inventory/kt_first/`): KT 대리점 재고
- **LG Hunet** (`inventory/lg_hunet/`): LG 대리점 재고

### Next.js ISR Revalidation

- Admin에서 Product/Banner 수정 시 프론트엔드 캐시 자동 무효화 (`revalidate.py`)
- RevalidateTag enum으로 태그 관리

### Celery (비동기 태스크)

- Redis broker 사용
- django-celery-beat으로 주기적 태스크 관리
- 오픈마켓 가격 업데이트 등 비동기 처리

## Admin Customization

- `nested_admin`: Device > Color > ColorImage 계층 관리
- `simple_history`: Order 변경 이력 추적
- `tinymce`: Notice, Event에 HTML 편집기 제공
- **Excel import/export**: 통신사별 가격 일괄 업로드/다운로드
- **ISR revalidation**: Admin에서 직접 캐시 무효화 액션
- **Price history**: 현재 가격 스냅샷 저장 액션
- N+1 최적화: `select_related`/`prefetch_related` 적용

## Environment Variables

```bash
# Database (PostgreSQL)
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

# AWS
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME, AWS_CLOUDFRONT_DOMAIN, AWS_S3_REGION_NAME

# Channel Talk
CHANENLTALK_ACCESS_KEY, CHANENLTALK_ACCESS_SECRET

# Next.js Revalidation
FRONTEND_URL  # default: https://www.phoneinone.com
REVALIDATE_SECRET_TOKEN

# 외부 서비스
SMARTEL_INVENTORY_API_KEY    # Smartel 재고 API
GEMINI_API_KEY               # Google Gemini AI
API_KEY_11st                 # 11번가 API

# Celery
celery_broker                # Redis URL
```

## Key Dependencies

| Package                                     | Purpose                  |
| ------------------------------------------- | ------------------------ |
| Django 5.2.5                                | Web framework            |
| djangorestframework 3.16.1                  | REST API                 |
| drf-yasg                                    | Swagger/OpenAPI          |
| psycopg 3.2.9                               | PostgreSQL driver        |
| boto3, django-storages                      | AWS S3                   |
| django-tinymce                              | Rich text editor         |
| django-cors-headers                         | CORS                     |
| django-nested-admin                         | Hierarchical admin       |
| django-simple-history                       | Model history tracking   |
| celery, django-celery-beat                  | 비동기 태스크 + 스케줄링 |
| redis                                       | Celery broker            |
| pillow                                      | Image processing         |
| openpyxl, pandas                            | Excel import/export      |
| google-genai                                | Google Gemini AI         |
| rembg, scikit-image, opencv-python-headless | 이미지 배경 제거         |
| requests                                    | HTTP 클라이언트          |

## Development Notes

1. **ProductOption 수정 시** `Product.best_price_option`이 signals로 자동 갱신됨
2. **이미지 필드**는 S3에 업로드되며 URL은 CloudFront 도메인 사용
3. **Soft delete** - `deleted_at` 필드로 관리, hard delete 피할 것
4. **Order**는 `simple_history`로 모든 변경 추적
5. **API 권한**: 대부분 `AllowAny` (조회/생성 공개)
6. **페이지네이션**: LimitOffsetPagination, 기본 20개
7. **DeviceVariant**에 통신사별 이름/가격 필드 존재 (name_sk, price_sk 등)
8. **Inventory**는 대리점별 재고로 device_variant + device_color + dealership unique
9. **OpenMarket** 모델들은 외부 마켓플레이스 연동용 (11번가, SSG, 네이버 등)
10. **Celery**는 오픈마켓 가격 업데이트 등 비동기 작업에 사용

## Deployment

```bash
# main 브랜치 push로 배포
git push origin main
```

- **서버**: AWS Elastic Beanstalk (Gunicorn)
- **DB**: AWS RDS PostgreSQL
- **파일**: AWS S3 + CloudFront
- **비동기**: Celery + Redis

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
