from typing import Callable, Any
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class UniqueFilePathGenerator:
    def __init__(self, path: str):
        self.path = path.strip("/")

    # 이 메서드는 내부 상태(self.path)를 사용하여 경로를 생성합니다.
    def __call__(self, instance, filename: str) -> str:
        name, ext = filename.rsplit(".", 1)
        now = timezone.now()

        new_filename = f"{self.path}/{name}-{now.strftime('%Y%m%d%H%M%S%f')}.{ext}"
        return new_filename

    def deconstruct(self):
        # 1. name
        name = self.__class__.__name__
        # 2. module
        module = self.__class__.__module__
        # 3. 위치 인자 (args)
        args = (self.path,)
        # 4. 키워드 인자 (kwargs)
        kwargs = {}

        # 반드시 4개의 요소로 구성된 튜플을 반환해야 합니다.
        return (name, module, args, kwargs)
