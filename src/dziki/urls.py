from django.urls import path
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('api/health/', health_check),
]
