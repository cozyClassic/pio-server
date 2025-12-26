from django.db import models

# Create your models here.

"""
데이터 구조

- 업체
1. 업체명
2. 업체 웹사이트(HOST)

크롤링용 스크립트 
1. DB 대신 코드 레벨에 저장
2. 대신 업체명+id 는 DB와 코드를 매칭해서 저장해야 함

- 단말기 정보
1. 단말기 명
2. 용량
3. 가격

- 상품 정보
1. 크롤링한 날짜
2. 가입 유형 (번호이동, 신규가입, 기기변경))
3. 통신사 (총 데이터 개수: 3개)
4. 요금제 (총 데이터 개수: 최대 15개)
7. 할인금액 1 (공시지원금)
8. 할인금액 2 (추가지원금)
9. 할인금액 3 (현금지원금)
"""


class Carrier(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Plan(models.Model):
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.carrier.name} - {self.name}"


class Device(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class DeviceVariant(models.Model):
    device_model = models.ForeignKey(Device, on_delete=models.CASCADE)
    storage = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.device_model.name} - {self.storage}"


class Company(models.Model):
    name = models.CharField(max_length=100)
    website = models.URLField()

    def __str__(self):
        return self.name


class PriceLog(models.Model):
    batch_id = models.CharField(max_length=100)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    device_variant = models.ForeignKey(DeviceVariant, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    contract_type = models.CharField(max_length=50)  # 번호이동, 신규가입, 기기변경
    discount_type = models.CharField(max_length=50)  # 공시지원금, 선택약정
    subsidy_common = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # 공통지원금
    subsidy_add = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # 추가지원금
    subsidy_cash = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # 현금지원금
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
