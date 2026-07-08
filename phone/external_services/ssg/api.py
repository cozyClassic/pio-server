import requests

from phoneinone_server.settings import SSG_API_KEY

HOST_SSG = "https://eapi.ssgadm.com"

# 등록/수정 API 연속 호출 시 최소 3초 간격 필요 (문서 명시)
SSG_CALL_INTERVAL_SEC = 3


def _headers() -> dict:
    if not SSG_API_KEY:
        raise Exception("SSG_API_KEY 환경변수가 설정되지 않았습니다.")
    return {"Authorization": SSG_API_KEY, "Accept": "application/json"}


def _check_result(response: requests.Response, action: str) -> dict:
    if response.status_code != 200:
        raise Exception(
            f"SSG {action} HTTP {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    result = data.get("result", {})
    if str(result.get("resultCode")) != "00":
        raise Exception(
            f"SSG {action} 실패 (resultCode={result.get('resultCode')}): "
            f"{result.get('resultMessage')} / {result.get('resultDesc')}"
        )
    return data


def ssg_get(path: str, params: dict | None = None, action: str = "조회") -> dict:
    response = requests.get(
        f"{HOST_SSG}{path}", params=params, headers=_headers(), timeout=30
    )
    return _check_result(response, action)


def ssg_post(path: str, json_body: dict, action: str = "요청") -> dict:
    response = requests.post(
        f"{HOST_SSG}{path}", json=json_body, headers=_headers(), timeout=60
    )
    return _check_result(response, action)
