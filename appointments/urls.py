from django.urls import path
from . import views

app_name = "appointments"

urlpatterns = [
    path("connect/", views.google_connect_view, name="connect"),
    path("oauth2callback/", views.google_oauth2_callback_view, name="oauth2callback"),
    path("disconnect/", views.google_disconnect_view, name="disconnect"),
]