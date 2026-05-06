import re
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from phone.models import CustomImage

ALLOWED_TINYMCE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_TINYMCE_FILE_SIZE = 10 * 1024 * 1024


def clean_phone_num(phone_num: str) -> str:
    return re.sub(r"[^0-9]", "", phone_num)


def ping(request: HttpRequest) -> HttpResponse:
    """
    Ping view to check server status.
    """
    return HttpResponse("pong")


@csrf_exempt
def tinymce_upload(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "file required"}, status=400)
    if f.content_type not in ALLOWED_TINYMCE_MIME:
        return JsonResponse({"error": "unsupported content type"}, status=400)
    if f.size > MAX_TINYMCE_FILE_SIZE:
        return JsonResponse({"error": "file too large"}, status=400)

    file_instance = CustomImage.objects.create(image=f, name=f.name)
    return JsonResponse({"location": file_instance.image.url})
