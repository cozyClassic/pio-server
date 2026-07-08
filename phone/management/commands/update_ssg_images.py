"""등록된 SSG 상품의 대표이미지를 로컬 이미지 파일로 교체한다.

이미지는 1200x1200 정사각 JPG로 정규화(비율 유지, 흰 배경 패딩) 후
S3(ssg_item_images/)에 업로드하고, SSG itemDescription API로 교체한다.

사용 예:
  # 파일 나열 (나열 순서 = dataSeq 노출 순서)
  python manage.py update_ssg_images --ssg-id 908 --images a.png b.png

  # 디렉토리 통째로 (파일명 정렬 순서)
  python manage.py update_ssg_images --ssg-id 908 --dir ./zflip7_images/
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from phone.constants import OpenMarketChoices
from phone.external_services.ssg.put_product.image_conversion import IMAGE_EXTS
from phone.models import OpenMarketProduct


class Command(BaseCommand):
    help = "SSG 상품 대표이미지 교체 (1200x1200 정규화 + S3 업로드)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ssg-id", type=int, required=True,
            help="SSG OpenMarketProduct 내부 ID (register_ssg_product 생성분)",
        )
        parser.add_argument("--images", nargs="*", default=[], help="이미지 파일 경로들")
        parser.add_argument("--dir", help="이미지 디렉토리 (파일명 정렬 순)")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="S3 업로드까지만 하고 SSG 교체는 안 함",
        )

    def handle(self, *args, **options):
        from phone.external_services.ssg.put_product.image_conversion import (
            prepare_square_jpg,
            upload_ssg_image,
        )
        from phone.external_services.ssg.put_product.update_images import (
            update_item_main_images,
        )

        ssg_product = (
            OpenMarketProduct.objects.filter(
                id=options["ssg_id"], open_market__source=OpenMarketChoices.SSG
            ).first()
        )
        if ssg_product is None or not ssg_product.om_product_id:
            self.stderr.write(f"SSG 상품이 없습니다 - 내부 ID: {options['ssg_id']}")
            return

        paths = [Path(p) for p in options["images"]]
        if options["dir"]:
            paths += sorted(
                p for p in Path(options["dir"]).iterdir()
                if p.suffix.lower() in IMAGE_EXTS
            )
        paths = [p for p in paths if p.is_file()]
        if not paths:
            self.stderr.write("이미지 파일이 없습니다. --images 또는 --dir 확인.")
            return
        if len(paths) > 10:
            self.stdout.write(f"이미지 {len(paths)}장 중 앞 10장만 사용합니다.")
            paths = paths[:10]

        # 기기 단위로 유일한 파일명 prefix — 여러 통신사/계약 상품이 같은 기기
        # 이미지를 공유해도 S3 경로가 결정적이고 기기 간 충돌이 없다.
        device_id = (
            ssg_product.device_variant.device_id
            if ssg_product.device_variant
            else ssg_product.id
        )

        urls = []
        for i, p in enumerate(paths):
            content = prepare_square_jpg(p.read_bytes())
            url = upload_ssg_image(content, f"dev{device_id}_{i:02d}_{p.name}")
            urls.append(url)
            self.stdout.write(f"  업로드: {p.name} -> {url}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("dry-run — SSG 교체는 생략"))
            return

        update_item_main_images(ssg_product.om_product_id, urls)
        self.stdout.write(
            self.style.SUCCESS(
                f"대표이미지 {len(urls)}장 교체 완료 - itemId: {ssg_product.om_product_id}"
            )
        )
