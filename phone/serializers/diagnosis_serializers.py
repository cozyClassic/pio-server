from rest_framework import serializers

from phone.models import DiagnosisLog, DiagnosisInquiry


class DiagnosisLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisLog
        fields = [
            "prev_carrier",
            "keep_carrier",
            "device_name",
            "data_usage",
            "internet",
            "family_bundle",
            "gift",
            "card",
            "internet_new",
            "selfbuy_total",
            "pio_total",
            "total_saving",
        ]


class DiagnosisInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisInquiry
        fields = [
            "name",
            "contact",
            "prev_carrier",
            "keep_carrier",
            "device_name",
            "data_usage",
            "internet",
            "family_bundle",
            "gift",
            "card",
            "internet_new",
            "selfbuy_total",
            "pio_total",
            "total_saving",
        ]
