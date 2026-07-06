"""Google Merchant 설정 감지/태스크 skip 회귀 테스트.

프로덕션에 GOOGLE_MERCHANT_* env 미설정 시 매시간 ADC 크래시 + 채널톡 스팸이
발생했던 버그(2026-07)의 재발 방지. DB 불필요(SimpleTestCase).
"""

from unittest import mock

from django.test import SimpleTestCase, override_settings


@override_settings(
    GOOGLE_MERCHANT_SA_INFO="",
    GOOGLE_MERCHANT_SA_JSON="",
    GOOGLE_MERCHANT_ACCOUNT_ID="",
    GOOGLE_MERCHANT_DATASOURCE_ID="",
)
class MissingSettingsTests(SimpleTestCase):
    def _patch_no_local_credentials(self):
        """로컬 개발 머신의 google-merchant.json / ADC env 영향 제거."""
        return (
            mock.patch(
                "phone.external_services.google_merchant.client.os.path.exists",
                return_value=False,
            ),
            mock.patch.dict(
                "os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": ""}, clear=False
            ),
        )

    def test_all_missing(self):
        from phone.external_services.google_merchant.client import missing_settings

        p1, p2 = self._patch_no_local_credentials()
        with p1, p2:
            missing = missing_settings()
        self.assertEqual(
            missing,
            [
                "GOOGLE_MERCHANT_SA_INFO(또는 SA 키 파일)",
                "GOOGLE_MERCHANT_ACCOUNT_ID",
                "GOOGLE_MERCHANT_DATASOURCE_ID",
            ],
        )

    @override_settings(
        GOOGLE_MERCHANT_SA_INFO='{"type": "service_account"}',
        GOOGLE_MERCHANT_ACCOUNT_ID="123",
        GOOGLE_MERCHANT_DATASOURCE_ID="456",
    )
    def test_fully_configured(self):
        from phone.external_services.google_merchant.client import missing_settings

        p1, p2 = self._patch_no_local_credentials()
        with p1, p2:
            self.assertEqual(missing_settings(), [])

    def test_task_skips_without_alert_when_unconfigured(self):
        """미설정 환경에서는 push도 채널톡 알림도 호출되지 않아야 한다."""
        from phone import tasks

        p1, p2 = self._patch_no_local_credentials()
        with (
            p1,
            p2,
            mock.patch(
                "phone.external_services.google_merchant.sync.push"
            ) as mock_push,
            mock.patch.object(
                tasks, "send_open_market_update_failure_alert"
            ) as mock_alert,
        ):
            tasks.task_push_google_merchant()

        mock_push.assert_not_called()
        mock_alert.assert_not_called()


class FailureAlertFormatTests(SimpleTestCase):
    def test_market_prefix_and_omitted_id_line(self):
        """전체 태스크 실패(om_product_id=0)는 ID 줄 없이, market 접두어로 표기."""
        from phone.external_services import channel_talk

        with mock.patch.object(channel_talk.ChannelTalkAPI, "post") as mock_post:
            channel_talk.send_open_market_update_failure_alert(
                "푸시", 0, "some error", market="Google Merchant"
            )

        value = mock_post.call_args.kwargs["json"]["blocks"][0]["value"]
        self.assertIn("[Google Merchant 푸시 실패]", value)
        self.assertNotIn("내부 ID", value)
        self.assertNotIn("11번가", value)

    def test_default_market_keeps_11st_prefix(self):
        from phone.external_services import channel_talk

        with mock.patch.object(channel_talk.ChannelTalkAPI, "post") as mock_post:
            channel_talk.send_open_market_update_failure_alert(
                "가격 업데이트", 42, "boom"
            )

        value = mock_post.call_args.kwargs["json"]["blocks"][0]["value"]
        self.assertIn("[11번가 가격 업데이트 실패]", value)
        self.assertIn("내부 ID: 42", value)
