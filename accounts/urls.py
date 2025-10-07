from django.urls import path
from .views import RegisterView, EmailLoginView, EmailLogoutView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", EmailLogoutView.as_view(), name="logout"),
]
