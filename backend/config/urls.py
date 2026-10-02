from django.contrib import admin
from django.urls import include, path
from django.views.decorators.http import require_GET
from django.http import JsonResponse


@require_GET
def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/trips/", include("trips.urls")),
]

