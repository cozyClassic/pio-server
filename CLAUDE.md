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
├── phoneinone_server/          # Django 메인 설정
│   ├── settings.py             # 환경설정 (DB, AWS, CORS 등)
│   ├── urls.py                 # 루트 URL 라우팅
│   └── wsgi.py / asgi.py
├── phone/                       # 핵심 휴대폰 판매 앱
│   ├── models.py               # Product, Order, Plan, Device 등
│   ├── views.py                # REST API ViewSets
│   ├── serializers.py          # DRF Serializers
│   ├── admin.py                # Django Admin 설정
│   ├── signals.py              # post_save 시그널
│   ├── managers.py             # SoftDeleteManager
│   ├── constants.py            # CarrierChoices (SK, KT, LG)
│   ├── utils.py                # UniqueFilePathGenerator
│   ├── revalidate.py           # Next.js ISR 캐시 무효화
│   ├── external_services/      # Channel Talk 연동
│   └── product_option_update/  # Excel 임포트 스크립트
├── internet/                    # 인터넷/TV 번들 서비스 앱
│   ├── models.py               # InternetPlan, BundleDiscount 등
│   ├── views.py
│   └── serializers.py
├── requirements.txt
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
- 모든 쿼리는 자동으로 삭제된 레코드 제외

### Price Calculation (ProductOption)

```python
final_price = device_price - additional_discount
if discount_type == '공시지원금':
    final_price -= subsidy_amount
    if contract_type == '번호이동':
        final_price -= subsidy_amount_mnp

# 월 할부금
monthly_payment = (final_price * 1.0625 / 24) + plan_price
# 선택약정인 경우 plan_price *= 0.75
```

### Auto Best Option Update

`ProductOption` 저장 시 `Product.best_price_option` 자동 갱신 (signals.py):

```python
@receiver(post_save, sender=ProductOption)
def handle_product_option_save(sender, instance, **kwargs):
    ProductOption._add_pending_product(instance.product_id)
    transaction.on_commit(ProductOption._update_pending_products)
```

## Key Models (phone app)

| Model | Description |
|-------|-------------|
| `Device` | 단말기 (model_name, brand, series) |
| `DeviceVariant` | 단말기 옵션 - 저장용량 (storage_capacity, device_price) |
| `DeviceColor` | 단말기 색상 (color, color_code) |
| `Plan` | 통신사 요금제 (carrier, price, data_allowance) |
| `ProductOption` | 상품옵션 = 단말기 + 요금제 (final_price, monthly_payment) |
| `Product` | 판매 상품 (device, best_price_option, is_featured) |
| `Order` | 주문 (customer info, status, shipping) |
| `Review` | 상품 리뷰 (rating 1-5, comment, image) |
| `FAQ` | FAQ (category, question, answer) |
| `Notice` | 공지사항 (type: caution/event/general, HTML content) |
| `Banner` | 배너 (image_pc, image_mobile, location) |
| `Event` | 이벤트 (thumbnail, description HTML) |
| `PartnerCard` | 제휴 카드 할인 정보 |

## API Endpoints

### Phone API (`/api/` or `/phone/`)

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/products` | GET | 상품 목록 (filter: brand, series, carrier, is_featured) |
| `/products/<id>` | GET | 상품 상세 (조회수 증가) |
| `/product-series` | GET | 제품 시리즈 목록 |
| `/orders` | GET, POST | 주문 조회/생성 |
| `/faqs` | GET | FAQ 목록 |
| `/notices` | GET | 공지사항 목록 (filter: type) |
| `/banners` | GET | 배너 목록 |
| `/reviews` | GET, POST | 리뷰 목록/생성 (multipart) |
| `/events` | GET | 이벤트 목록 |
| `/partner-cards` | GET | 파트너 카드 목록 |
| `/devices` | GET | 단말기 목록 |
| `/plans` | GET | 요금제 목록 |
| `/product-options` | GET | 상품옵션 목록 (filter: dv_id) |

### Internet API (`/internet/`)

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/carriers` | GET | 인터넷 제공자 목록 |
| `/plans` | GET | 인터넷 요금제 및 번들 조건 |
| `/inquiries` | POST | 고객 문의 생성 |

### System Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Health check |
| `/db-check` | 데이터베이스 연결 확인 |
| `/swagger/` | API 문서 (DEBUG=True) |

## External Services

### AWS S3 + CloudFront

- 이미지 저장: S3
- 배포: CloudFront CDN
- 이미지 URL은 CloudFront 도메인으로 변환됨

```python
# settings.py
STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'cloudfront_domain': AWS_CLOUDFRONT_DOMAIN,
    }
}
```

### Channel Talk

주문 생성 시 팀 채널에 알림 발송 (`external_services/channel_talk.py`):

```python
def send_order_alert(order_id, customer_name, customer_phone):
    # Channel Talk API로 메시지 전송
```

### Next.js ISR Revalidation

Admin에서 Product/Banner 수정 시 프론트엔드 캐시 자동 무효화 (`revalidate.py`):

```python
class RevalidateTag(str, Enum):
    PRODUCTS = 'products'
    PRODUCT_DETAIL = 'product-detail'
    BANNERS = 'banners'
    REVIEWS = 'reviews'
    # ...

def revalidate_cache(tags, async_call=True):
    requests.post(f"{FRONTEND_URL}/api/revalidate", json={"tag": tags})
```

## Admin Customization

- `nested_admin`: Device > Color > ColorImage 계층 관리
- `simple_history`: Order 변경 이력 추적
- `tinymce`: Notice, Event에 HTML 편집기 제공

## Environment Variables

```bash
# Database (PostgreSQL)
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

# AWS
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME
AWS_CLOUDFRONT_DOMAIN
AWS_S3_REGION_NAME

# Channel Talk
CHANENLTALK_ACCESS_KEY
CHANENLTALK_ACCESS_SECRET

# Next.js Revalidation
FRONTEND_URL  # default: https://www.phoneinone.com
REVALIDATE_SECRET_TOKEN
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| Django 5.2.5 | Web framework |
| djangorestframework 3.16.1 | REST API |
| drf-yasg | Swagger/OpenAPI |
| psycopg 3.2.9 | PostgreSQL driver |
| boto3, django-storages | AWS S3 |
| django-tinymce | Rich text editor |
| django-cors-headers | CORS |
| django-nested-admin | Hierarchical admin |
| django-simple-history | Model history |
| pillow | Image processing |
| openpyxl, pandas | Excel import |

## Development Notes

1. **ProductOption 수정 시** `Product.best_price_option`이 자동 갱신됨
2. **이미지 필드**는 S3에 업로드되며 URL은 CloudFront 도메인 사용
3. **Soft delete** - `deleted_at` 필드로 관리, hard delete 피할 것
4. **Order**는 `simple_history`로 추적됨
5. **API 권한**: 대부분 `AllowAny` (조회/생성 공개)
6. **페이지네이션**: LimitOffsetPagination, 기본 20개

## Deployment

```bash
# main 브랜치 push로 배포
git push origin main
```

- **서버**: AWS Elastic Beanstalk (Gunicorn)
- **DB**: AWS RDS PostgreSQL
- **파일**: AWS S3 + CloudFront
