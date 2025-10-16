# users/forms.py
from __future__ import annotations
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User
from django.utils.translation import gettext_lazy as _

# NEW: crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from crispy_bootstrap5.bootstrap5 import FloatingField
from .models import User, UserPreferences
from crispy_forms.layout import Layout, Submit, Div
from accounts.models import Country

class CustomUserCreationForm(UserCreationForm):
    """User creation form that only asks for email and password."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Floating labels for all fields
       # Placeholders + nicer labels
        self.fields["email"].widget.attrs.update({"placeholder": "email@example.com", "autocomplete": "email"})
        self.fields["password1"].label = _("Password")
        self.fields["password2"].label = _("Confirm password")

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            FloatingField("email"),
            Row(
                Column(FloatingField("password1"), css_class="col-12 col-md-6"),
                Column(FloatingField("password2"), css_class="col-12 col-md-6"),
                css_class="g-2",
            ),
            Submit("submit", "Create account", css_class="btn btn-primary mt-2"),
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email


class CustomUserChangeForm(UserChangeForm):
    """User admin change form (admin site)."""
    class Meta:
        model = User
        fields = ("email",)
        field_classes = {}


class ProfileUpdateForm(forms.ModelForm):
    """Allow the logged-in user to update basic profile fields."""
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional placeholders (nice with floating fields)
        self.fields["first_name"].widget.attrs.update({"placeholder": "First name"})
        self.fields["last_name"].widget.attrs.update({"placeholder": "Last name"})

        self.helper = FormHelper()
        self.helper.form_method = "post"
        # self.helper.form_tag = False  # form tag is in the template
        self.helper.layout = Layout(
            FloatingField("email"),
            Row(
                Column(FloatingField("first_name"), css_class="col-12 col-md-6"),
                Column(FloatingField("last_name"), css_class="col-12 col-md-6"),
                css_class="g-2",
            ),
            Div(
                Submit("submit", "Save changes", css_class="btn btn-primary"),
                HTML('<a href="{% url \'users:profile\' %}" class="btn btn-outline-secondary ms-2">Cancel</a>'),
                css_class="mt-2",
            ),
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email

class UserPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ['preferred_currency']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_currency'].queryset = Country.objects.order_by('currency_code')
        self.fields['preferred_currency'].label = "Preferred currency for total balance"
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'preferred_currency',
            Div(
                Submit('submit', 'Save Preferences', css_class='btn btn-primary'),
                HTML('<a href="{% url \'core:home\' %}" class="btn btn-outline-secondary ms-2">Cancel</a>'),
                css_class="mt-3",
            )
        )