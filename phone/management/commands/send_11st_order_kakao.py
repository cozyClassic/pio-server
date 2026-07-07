import json

from django.core.management.base import BaseCommand, CommandError

from phone.external_services.st_11.check_order.get_order_list import (
    get_unhandled_order_list_today,
)
from phone.external_services.st_11.check_order.official_contract_kakao import (
    build_order_event,
    send_official_contract_kakao,
)


class Command(BaseCommand):
    help = (
        "11번가 주문의 공식신청서 알림톡 발송을 수동 실행/검증한다. "
        "--order-no로 실제 주문을 조회하거나, --name/--phone/--product-no/--plan으로 "
        "가상 주문을 구성해 테스트할 수 있다. --dry-run이면 매핑 결과만 출력."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--order-no",
            default=None,
            help="어제~오늘 11번가 주문 중 해당 주문번호를 찾아 발송",
        )
        parser.add_argument("--name", default=None, help="(가상 주문) 고객명")
        parser.add_argument(
            "--phone", default=None, help="(가상 주문) 고객 연락처, 예: 01012345678"
        )
        parser.add_argument(
            "--product-no", default=None, help="(가상 주문) 11번가 상품번호(prdNo)"
        )
        parser.add_argument(
            "--plan", default=None, help="(가상 주문) 요금제명, 예: '프리미어 시그니처'"
        )
        parser.add_argument(
            "--product-name", default="테스트 상품", help="(가상 주문) 상품명"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="채널톡 호출 없이 링크 매핑 결과와 이벤트 payload만 출력",
        )

    def handle(self, *args, **opts):
        order = self._resolve_order(opts)

        self.stdout.write(f"대상 주문: {json.dumps(order, ensure_ascii=False)}")

        event = build_order_event(order)
        self.stdout.write("\n----- 채널톡 이벤트 구성 -----")
        self.stdout.write(f"member_id: {event['member_id']}")
        self.stdout.write(f"mobile_number: {event['mobile_number']}")
        self.stdout.write(
            f"property: {json.dumps(event['property'], ensure_ascii=False, indent=2)}"
        )

        if opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS("\nDRY-RUN: 채널톡 호출 안 함"))
            return

        send_official_contract_kakao(order)
        self.stdout.write(
            self.style.SUCCESS("\n발송 완료 (채널톡 자동화가 알림톡을 발송합니다)")
        )

    def _resolve_order(self, opts) -> dict:
        if opts["order_no"]:
            orders = get_unhandled_order_list_today() or []
            matched = [o for o in orders if o["order_no"] == opts["order_no"]]
            if not matched:
                raise CommandError(
                    f"어제~오늘 주문에서 주문번호를 찾을 수 없습니다: {opts['order_no']}"
                )
            return matched[0]

        required = ("name", "phone", "product_no", "plan")
        missing = [key for key in required if not opts[key]]
        if missing:
            raise CommandError(
                "--order-no 없이 실행하려면 다음 옵션이 모두 필요합니다: "
                + ", ".join(f"--{key.replace('_', '-')}" for key in missing)
            )

        return {
            "order_no": "",
            "customer_name": opts["name"],
            "customer_phone": opts["phone"],
            "product_name": opts["product_name"],
            "product_no": opts["product_no"],
            "plan_name": f"요금제:{opts['plan']}-1개",
        }
