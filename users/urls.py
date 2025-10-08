from django.urls import path, re_path
from .views import (
    RegisterView, EmailLoginView, EmailLogoutView,
    ProfileView, ProfileEditView, ProfilePasswordChangeView,
    PasswordResetRequestView, PasswordResetDoneCustomView,
    PasswordResetConfirmCustomView, PasswordResetCompleteCustomView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", EmailLogoutView.as_view(), name="logout"),

    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/edit/", ProfileEditView.as_view(), name="profile_edit"),
    path("profile/password/", ProfilePasswordChangeView.as_view(), name="password_change"),

    # Password reset flow
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset/done/", PasswordResetDoneCustomView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", PasswordResetConfirmCustomView.as_view(), name="password_reset_confirm"),
    path("reset/complete/", PasswordResetCompleteCustomView.as_view(), name="password_reset_complete"),
]
