import requests

from phoneinone_server.settings import API_KEY_11st
from ..api import HOST_11st
from lxml import etree
from datetime import datetime, timezone, timedelta

_SETTLEMENT_RESPONSE_SAMPLE = """<?xml version="1.0" encoding="euc-kr" standalone="yes"?>
<ns2:seStlDtlList>
  <clmReqSeq/>
  <feeTypeNm>동의</feeTypeNm>
  <memId>S|19834600|ALx***</memId>
  <memNm>김민찬</memNm>
  <optAmt>0</optAmt>
  <ordNo>20260225044348982</ordNo>
  <ordPrdSeq>1</ordPrdSeq>
  <ordQty>1</ordQty>
  <ordStlEndDt>20260225</ordStlEndDt>
  <pocnfrmDt>20260302</pocnfrmDt>
  <prdNm>Apple 아이폰 에어 256GB LG 번호이동/공통지원/완납/제휴카드X/부가X</prdNm>
  <prdNo>9105055173</prdNo>
  <selFee>320</selFee>
  <selPrc>4000</selPrc>
  <selPrcAmt>4000</selPrcAmt>
  <slctPrdOptNm>요금제:프리미어 시그니처-1개</slctPrdOptNm>
  <stlAmt>3680</stlAmt>
  <stlDy>2026/03/04</stlDy>
  <stlPlnDy>2026/03/06</stlPlnDy>
  <totalCount>1</totalCount>
</ns2:seStlDtlList>
"""

# 정산내역조회 API는 최대 31일까지 조회 가능. 전일자 구매확정 기준으로 데이터가
# 갱신되므로, 넉넉히 최근 N일을 조회하고 DB(OpenMarketSettlement)로 중복을 거른다.
SETTLEMENT_LOOKBACK_DAYS = 14

# 조회 결과 없음 — 에러가 아니라 빈 목록으로 처리한다.
RESULT_CODE_NO_DATA = "0"


def format_date_11st_style(t: datetime) -> str:
    return t.strftime("%Y%m%d")


def _localname(element: etree._Element) -> str:
    tag = element.tag
    return tag if not isinstance(tag, str) else etree.QName(tag).localname


def _to_int(value: str) -> int:
    try:
        return int(value.replace(",", ""))
    except (ValueError, AttributeError):
        return 0


def _parse_settlement(xml: etree._Element) -> dict:
    def text(tag: str) -> str:
        for child in xml:
            if _localname(child) == tag:
                return (child.text or "").strip()
        return ""

    return {
        "order_no": text("ordNo"),
        "ord_prd_seq": text("ordPrdSeq"),
        "claim_req_seq": text("clmReqSeq"),
        "product_name": text("prdNm"),
        "product_no": text("prdNo"),
        "option_name": text("slctPrdOptNm"),
        "sell_price": text("selPrc"),
        "fee": text("selFee"),
        "settlement_amount": _to_int(text("stlAmt")),
        "confirm_date": text("pocnfrmDt"),
        "settlement_day": text("stlDy"),
        "remittance_plan_day": text("stlPlnDy"),
    }


def _raise_if_error(root: etree._Element):
    """에러 응답(ns2:orders > result_code) 검사. 조회결과 없음(0)은 정상 처리."""
    result_codes = [e for e in root.iter() if _localname(e) == "result_code"]
    if not result_codes:
        return

    code = (result_codes[0].text or "").strip()
    if code == RESULT_CODE_NO_DATA:
        raise _NoDataResponse()

    result_texts = [e for e in root.iter() if _localname(e) == "result_text"]
    text = (result_texts[0].text or "").strip() if result_texts else ""
    raise Exception(f"11번가 정산내역조회 실패 (result_code={code}): {text}")


class _NoDataResponse(Exception):
    pass


def get_settlement_list(start: datetime, end: datetime) -> list[dict]:
    """기간별 정산내역 조회. 날짜포맷 YYYYMMDD, 조회기간 최대 31일."""
    url = (
        f"{HOST_11st}/settlement/settlementList"
        f"/{format_date_11st_style(start)}/{format_date_11st_style(end)}"
    )
    headers = {"openapikey": API_KEY_11st}

    response = requests.request(method="GET", url=url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"11번가 정산내역조회 HTTP {response.status_code}: {response.text[:300]}"
        )

    root = etree.fromstring(response.content)

    try:
        _raise_if_error(root)
    except _NoDataResponse:
        return []

    # 문서상 각 정산 row는 seStlDtlList 요소. 단건이면 루트 자체가 row일 수 있어
    # 네임스페이스 무시하고 로컬명으로 전부 수집한다.
    rows = [e for e in root.iter() if _localname(e) == "seStlDtlList"]

    settlements = [_parse_settlement(r) for r in rows]
    # totalCount만 있는 wrapper 등 주문번호 없는 row는 정산 건이 아니므로 제외
    return [s for s in settlements if s["order_no"]]


def get_recent_settlement_list() -> list[dict]:
    """최근 SETTLEMENT_LOOKBACK_DAYS일 정산내역 조회 (KST 기준)."""
    KST = timezone(timedelta(hours=9))
    today = datetime.now(KST)
    start = today - timedelta(days=SETTLEMENT_LOOKBACK_DAYS)
    return get_settlement_list(start, today)
