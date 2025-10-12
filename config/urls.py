from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("users/", include("users.urls", namespace="users")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path('appointments/', include('appointments.urls')),
]
