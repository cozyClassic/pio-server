import logging
import requests

from phoneinone_server.settings import API_KEY_11st
from ..api import HOST_11st
from lxml import etree
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_ORDER_RESPONSE_SAMPLE = """<?xml version="1.0" encoding="EUC-KR" standalone="yes"?>
<ns2:orders xmlns:ns2="http://skt.tmall.business.openapi.spring.service.client.domain/">
    <ns2:order>
        <addPrdNo>0</addPrdNo>
        <addPrdYn>N</addPrdYn>
        <appmtDdDlvDy></appmtDdDlvDy>
        <appmtEltRefuseYn></appmtEltRefuseYn>
        <appmtselStockCd></appmtselStockCd>
        <bmDlvCst>0</bmDlvCst>
        <bmDlvCstType>03</bmDlvCstType>
        <bndlDlvSeq>0</bndlDlvSeq>
        <bndlDlvYN>N</bndlDlvYN>
        <clmReqRsnNm></clmReqRsnNm>
        <custGrdNm>일반고객</custGrdNm>
        <deferRefsRsnCdNm></deferRefsRsnCdNm>
        <delaySendDt></delaySendDt>
        <dlvCst>0</dlvCst>
        <dlvCstType>03</dlvCstType>
        <dlvEtprsCd></dlvEtprsCd>
        <dlvMthdCd>null</dlvMthdCd>
        <dlvNo>2678260704</dlvNo>
        <dlvSndDue>2026-02-25 00:00:00</dlvSndDue>
        <engNm></engNm>
        <freeGiftNo></freeGiftNo>
        <freeGiftQty></freeGiftQty>
        <gblDlvYn>N</gblDlvYn>
        <gifeser>0</gifeser>
        <giftCd></giftCd>
        <invcNo></invcNo>
        <lstDlvCst>0</lstDlvCst>
        <lstSellerDscPrc>0</lstSellerDscPrc>
        <lstTmallDscPrc>0</lstTmallDscPrc>
        <memID>S|19834600|ALx***</memID>
        <memNo>64016623</memNo>
        <ordAmt>4000</ordAmt>
        <ordBaseAddr>서울특별시 강남구 봉은사로51길 18 (논현동,그랑디오스아파트)</ordBaseAddr>
        <ordDlvReqCont></ordDlvReqCont>
        <ordDt>2026-02-25 11:46:06</ordDt>
        <ordDtlsAddr>103호</ordDtlsAddr>
        <ordMailNo>06103</ordMailNo>
        <ordNm>김민찬</ordNm>
        <ordNo>20260225044348982</ordNo>
        <ordOptWonStl>0</ordOptWonStl>
        <ordPayAmt>4000</ordPayAmt>
        <ordPayAmtPerSeq>4000</ordPayAmtPerSeq>
        <ordPrdSeq>1</ordPrdSeq>
        <ordPrdStat>202</ordPrdStat>
        <ordPrtblTel>010-9455-0192</ordPrtblTel>
        <ordQty>1</ordQty>
        <ordStlEndDt>2026-02-25 11:46:06</ordStlEndDt>
        <ordTlphnNo>02--</ordTlphnNo>
        <plcodrCnfDt>null</plcodrCnfDt>
        <prdNm>Apple 아이폰 에어 256GB LG 번호이동/공통지원/완납/제휴카드X/부가X</prdNm>
        <prdNo>9105055173</prdNo>
        <prdStckNo>44699820216</prdStckNo>
        <psnCscUniqNo></psnCscUniqNo>
        <rcvrBaseAddr>서울특별시 강남구 봉은사로51길 18 (논현동,그랑디오스아파트)</rcvrBaseAddr>
        <rcvrDtlsAddr>103호</rcvrDtlsAddr>
        <rcvrMailNo>06103</rcvrMailNo>
        <rcvrMailNoSeq></rcvrMailNoSeq>
        <rcvrNm>김우준</rcvrNm>
        <rcvrPrtblNo>010-9309-5263</rcvrPrtblNo>
        <rcvrTlphn></rcvrTlphn>
        <realStockYn></realStockYn>
        <referSeq></referSeq>
        <refsRsn></refsRsn>
        <refsRsnCdNm></refsRsnCdNm>
        <selPrc>4000</selPrc>
        <sellerDscPrc>0</sellerDscPrc>
        <sellerDscPrcPerSeq>0</sellerDscPrcPerSeq>
        <sellerPrdCd>IP17A_256_LG_MNP_11ST</sellerPrdCd>
        <sellerStockCd>CDESAD001</sellerStockCd>
        <sendClfCd>Y</sendClfCd>
        <sendGiftYn>N</sendGiftYn>
        <shopNo>0</shopNo>
        <slctPrdOptNm>요금제:프리미어 시그니처-1개</slctPrdOptNm>
        <sndEndDt></sndEndDt>
        <stlPlnAmt>3680</stlPlnAmt>
        <tmallApplyDscAmt>0</tmallApplyDscAmt>
        <tmallDscPrc>0</tmallDscPrc>
        <tmallDscPrcPerSeq>0</tmallDscPrcPerSeq>
        <totSelFee>320</totSelFee>
        <typeAdd>02</typeAdd>
        <typeBilNo>1168010800102680012007723</typeBilNo>
        <use11stRetailYn>N</use11stRetailYn>
        <visitDlvYn>N</visitDlvYn>
    </ns2:order>
</ns2:orders>
"""


def format_datetime_11st_style(t: datetime):
    return t.strftime("%Y%m%d%H%M")


def parse_datas(xml: etree._Element):
    return {
        "order_no": xml.findtext("ordNo"),
        "customer_name": xml.findtext("ordNm"),
        "customer_phone": xml.findtext("ordPrtblTel"),
        "product_name": xml.findtext("prdNm"),
        "plan_name": xml.findtext("slctPrdOptNm"),
        "sell_price": xml.findtext("selPrc"),
    }


def get_unhandled_order_list_today():
    """
    startTime, endTime 양식: YYYYMMDDhhmm. 날짜포맷 / 년(4) 월(2) 일(2) 시(2) 분(2)
    검색기간 최대 일주일
    """
    KST = timezone(timedelta(hours=9))
    today = datetime.today()
    yesterday = today - timedelta(days=1)

    yesterday_00_00 = format_datetime_11st_style(
        datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=KST)
    )

    today_23_59 = format_datetime_11st_style(
        datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=KST)
    )

    url = f"{HOST_11st}/ordservices/complete/{yesterday_00_00}/{today_23_59}"
    headers = {"openapikey": API_KEY_11st}

    logger.info("11번가 주문 조회 요청: %s", url)

    response = requests.request(
        method="GET",
        url=url,
        headers=headers,
    )

    logger.info("11번가 응답 status=%s, body=%s", response.status_code, response.text[:500])

    root = etree.fromstring(response.content)
    ns = {"ns2": "http://skt.tmall.business.openapi.spring.service.client.domain/"}
    orders = root.findall("ns2:order", ns)

    if len(orders) == 0:
        return

    return [parse_datas(o) for o in orders]
