"""Google Merchant API 클라이언트/인증 헬퍼.

- 서비스계정 JSON 키(``GOOGLE_MERCHANT_SA_JSON``)로 서버-서버 인증한다.
  경로가 비어 있으면 ADC(``GOOGLE_APPLICATION_CREDENTIALS``)로 폴백한다.
- google 라이브러리는 함수 내부에서 지연 임포트한다. 패키지 미설치 상태에서도
  Django 부팅과 ``--dry-run`` 검증이 가능하도록 하기 위함이다.

필요 패키지: ``google-shopping-merchant-products``, ``google-shopping-type``
Merchant Center 사용자 관리에서 서비스계정 이메일에 API 접근 권한을 부여해야 한다.
"""

import json
import os

from django.conf import settings

# https://developers.google.com/merchant/api/guides/authorization
SCOPES = ["https://www.googleapis.com/auth/content"]

# env 미설정 시 자동 탐색하는 기본 키 경로(레포에 gitignore된 SA 키).
DEFAULT_SA_FILENAME = "google-merchant.json"


def _credentials():
    """서비스계정 크리덴셜을 반환.

    우선순위:
      1) ``GOOGLE_MERCHANT_SA_INFO`` — SA JSON '내용' 문자열(배포 권장, 파일 불필요)
      2) ``GOOGLE_MERCHANT_SA_JSON`` — SA JSON 파일 경로
      3) ``BASE_DIR/google-merchant.json`` (로컬 편의)
      4) None(ADC, ``GOOGLE_APPLICATION_CREDENTIALS``)
    """
    from google.oauth2 import service_account

    # 1) env에 담긴 SA JSON 문자열 — Railway 등 배포 환경에서 파일 없이 사용
    info = (settings.GOOGLE_MERCHANT_SA_INFO or "").strip()
    if info:
        try:
            data = json.loads(info)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "GOOGLE_MERCHANT_SA_INFO 가 올바른 JSON이 아닙니다(SA 키 '내용' 전체를 넣으세요)."
            ) from e
        return service_account.Credentials.from_service_account_info(
            data, scopes=SCOPES
        )

    # 2) 파일 경로 env → 3) 기본 파일 위치(로컬)
    path = (settings.GOOGLE_MERCHANT_SA_JSON or "").strip()
    if not path:
        default_path = os.path.join(settings.BASE_DIR, DEFAULT_SA_FILENAME)
        if os.path.exists(default_path):
            path = default_path
    if not path:
        return None  # 4) ADC
    return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)


def missing_settings() -> list[str]:
    """푸시에 필요한 설정 중 누락된 항목명을 반환(모두 있으면 빈 리스트).

    google 라이브러리 임포트 없이 판단하므로 Celery 태스크가 미설정 환경에서
    ADC 폴백으로 크래시하기 전에 건너뛸 수 있다.
    """
    missing = []
    has_credentials = bool(
        (settings.GOOGLE_MERCHANT_SA_INFO or "").strip()
        or (settings.GOOGLE_MERCHANT_SA_JSON or "").strip()
        or os.path.exists(os.path.join(settings.BASE_DIR, DEFAULT_SA_FILENAME))
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if not has_credentials:
        missing.append("GOOGLE_MERCHANT_SA_INFO(또는 SA 키 파일)")
    if not (settings.GOOGLE_MERCHANT_ACCOUNT_ID or "").strip():
        missing.append("GOOGLE_MERCHANT_ACCOUNT_ID")
    if not (settings.GOOGLE_MERCHANT_DATASOURCE_ID or "").strip():
        missing.append("GOOGLE_MERCHANT_DATASOURCE_ID")
    return missing


def product_inputs_client():
    """``ProductInputsServiceClient`` 인스턴스를 생성한다."""
    from google.shopping import merchant_products_v1 as mp

    return mp.ProductInputsServiceClient(credentials=_credentials())


def account_name() -> str:
    """``accounts/{merchantId}`` 형식의 parent 리소스명."""
    acc = (settings.GOOGLE_MERCHANT_ACCOUNT_ID or "").strip()
    if not acc:
        raise RuntimeError("GOOGLE_MERCHANT_ACCOUNT_ID 가 설정되지 않았습니다.")
    return f"accounts/{acc}"


def datasource_name() -> str:
    """``accounts/{merchantId}/dataSources/{dataSourceId}`` 형식의 리소스명."""
    acc = (settings.GOOGLE_MERCHANT_ACCOUNT_ID or "").strip()
    ds = (settings.GOOGLE_MERCHANT_DATASOURCE_ID or "").strip()
    if not (acc and ds):
        raise RuntimeError(
            "GOOGLE_MERCHANT_ACCOUNT_ID / GOOGLE_MERCHANT_DATASOURCE_ID 가 "
            "설정되지 않았습니다."
        )
    return f"accounts/{acc}/dataSources/{ds}"
