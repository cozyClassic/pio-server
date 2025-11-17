from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import path, re_path, include
from django.conf import settings
from drf_yasg import openapi, views
from rest_framework import permissions
from django.db import connection
import logging

schema_view = views.get_schema_view(
    openapi.Info(
        title="Swagger_Practise API",
        default_version="v1",
        description="Swagger Test를 위한 유저 API 문서",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@phoneinone.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


def health_check(request):
    return HttpResponse("ok")


def db_check(request):
    try:
        # DB 연결 테스트
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        return HttpResponse("ok")
    except Exception as e:
        logging.error(f"DB connection failed: {e}")
        return HttpResponse(f"DB Error: {str(e)}")


def env_check(request):
    from .settings import CSRF_TRUSTED_ORIGINS

    return JsonResponse({"CSRF_TRUSTED_ORIGINS": CSRF_TRUSTED_ORIGINS})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(("phone.urls", "api"))),
    path("phone/", include(("phone.urls", "phone"))),
    path("internet/", include(("internet.urls", "internet"))),
    path("db-check", db_check),
    path("env-check", env_check),
    path("", health_check),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^swagger(?P<format>\.json|\.yaml)$",
            schema_view.without_ui(cache_timeout=0),
            name="schema-json",
        ),
        re_path(
            r"^swagger/$",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
        re_path(
            r"^redoc/$",
            schema_view.with_ui("redoc", cache_timeout=0),
            name="schema-redoc",
        ),
    ]
