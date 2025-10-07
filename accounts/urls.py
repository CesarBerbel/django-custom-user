from django.urls import path
from .views import (
    RegisterView, EmailLoginView, EmailLogoutView,
    ProfileView, ProfileEditView, ProfilePasswordChangeView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", EmailLogoutView.as_view(), name="logout"),

    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/edit/", ProfileEditView.as_view(), name="profile_edit"),
    path("profile/password/", ProfilePasswordChangeView.as_view(), name="password_change"),
]
