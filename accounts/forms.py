from __future__ import annotations
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """User creation form that only asks for email and password."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)  # keep it minimal for now

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email


class CustomUserChangeForm(UserChangeForm):
    """User admin change form."""

    class Meta:
        model = User
        fields = ("email",)
        field_classes = {}


class ProfileUpdateForm(forms.ModelForm):
    """Allow the logged-in user to update basic profile fields."""
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        # Ensure uniqueness excluding current user
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email