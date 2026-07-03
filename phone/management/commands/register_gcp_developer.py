"""GCP 프로젝트를 Merchant Center 계정에 '개발자 등록'한다 (1회성).

⚠️ 이 단계는 **서비스계정으로 불가**하다("GCP registration is not allowed for
service accounts"). Merchant Center에 **Admin 권한이 있는 사람 계정**으로 OAuth
로그인해서 호출해야 하며, 등록되는 GCP 프로젝트 = **OAuth 클라이언트가 속한 프로젝트**다.
따라서 OAuth 클라이언트는 반드시 **서비스계정과 같은 프로젝트(phoneinone)**에서 만든다.

사전 준비 (GCP 콘솔, phoneinone 프로젝트):
  1) API 및 서비스 → OAuth 동의 화면 구성(테스트 모드면 본인 이메일을 테스트 사용자로 추가)
  2) API 및 서비스 → 사용자 인증 정보 → OAuth 클라이언트 ID 생성
     → 유형: **데스크톱 앱** → JSON 다운로드 후 `client_secret.json`으로 저장(이 폴더에)

실행:
  ../pio/bin/python manage.py register_gcp_developer --email nzlk112@gmail.com
  → 브라우저가 열리면 Admin 계정으로 로그인/동의 → 자동으로 registerGcp 호출

등록 후 ~5분 전파 대기. 초대 메일이 오면 14일 내 수락.
"""

import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CONTENT_SCOPE = ["https://www.googleapis.com/auth/content"]


class Command(BaseCommand):
    help = "GCP 프로젝트를 Merchant Center 계정에 개발자 등록한다(사람 OAuth 필요)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-secret",
            default="client_secret.json",
            help="OAuth 데스크톱 앱 클라이언트 JSON 경로(기본: client_secret.json).",
        )
        parser.add_argument(
            "--email",
            default="",
            help="developerEmail(선택). 비우면 프로젝트만 연결한다. "
            "Merchant Center Admin 권한 사람 이메일이어야 함(서비스계정 불가).",
        )

    def handle(self, *args, **options):
        account_id = (settings.GOOGLE_MERCHANT_ACCOUNT_ID or "").strip()
        if not account_id:
            raise CommandError("GOOGLE_MERCHANT_ACCOUNT_ID 가 설정되지 않았습니다.")

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise CommandError(
                "google-auth-oauthlib 가 필요합니다: "
                "../pio/bin/pip install google-auth-oauthlib"
            )

        self.stdout.write("브라우저에서 Admin 계정으로 로그인/동의하세요...")
        flow = InstalledAppFlow.from_client_secrets_file(
            options["client_secret"], scopes=CONTENT_SCOPE
        )
        creds = flow.run_local_server(port=0)

        url = (
            "https://merchantapi.googleapis.com/accounts/v1/accounts/"
            f"{account_id}/developerRegistration:registerGcp"
        )
        body = {}
        if options["email"]:
            body["developerEmail"] = options["email"]

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )

        self.stdout.write(f"HTTP {resp.status_code}")
        try:
            self.stdout.write(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        except ValueError:
            self.stdout.write(resp.text[:800])

        if resp.status_code == 200:
            self.stdout.write(
                self.style.SUCCESS(
                    "✓ 개발자 등록 성공. ~5분 후 서비스계정 API 호출이 가능합니다."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "✗ 등록 실패 — 위 응답과 권한(Admin)/프로젝트를 확인하세요."
                )
            )
