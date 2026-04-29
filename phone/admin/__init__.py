from phone.admin.base import *  # noqa: F401, F403
from phone.admin.device_admin import *  # noqa: F401, F403
from phone.admin.product_admin import *  # noqa: F401, F403
from phone.admin.order_admin import *  # noqa: F401, F403
from phone.admin.content_admin import *  # noqa: F401, F403
from phone.admin.calculator_admin import *  # noqa: F401, F403

# 사이드바 그룹화 — 모든 admin 클래스 등록 후 마지막에 import.
from phone.admin.grouping import *  # noqa: F401, F403, E402
