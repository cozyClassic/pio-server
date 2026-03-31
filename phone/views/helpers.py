import re
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from phone.models import CustomImage


def clean_phone_num(phone_num: str) -> str:
    return re.sub(r"[^0-9]", "", phone_num)


def ping(request: HttpRequest) -> HttpResponse:
    """
    Ping view to check server status.
    """
    return HttpResponse("pong")


@csrf_exempt
def tinymce_upload(request):
    if request.method != "POST" or not request.FILES.get("file"):
        return JsonResponse({"error": "Invalid request"}, status=400)

    file_instance = CustomImage.objects.create(
        image=request.FILES["file"], name=request.FILES["file"].name
    )
    return JsonResponse({"location": file_instance.image.url})
