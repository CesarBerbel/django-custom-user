# users/forms_auth.py
from __future__ import annotations
from django import forms
from django.contrib.auth.forms import AuthenticationForm

# NEW: crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from crispy_bootstrap5.bootstrap5 import FloatingField


class EmailAuthenticationForm(AuthenticationForm):
    """
    Custom auth form with clearer error messages and crispy layout.
    Field names remain 'username' and 'password' (Django default).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Align placeholders with our email-based login
        self.fields["username"].widget.attrs.update({"placeholder": "Email"})
        self.fields["password"].widget.attrs.update({"placeholder": "Password"})

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            FloatingField("username"),
            FloatingField("password"),
            Submit("submit", "Sign in", css_class="btn btn-primary"),
        )

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                "Your account is inactive. Please contact support.",
                code="inactive",
            )

    def get_invalid_login_error(self):
        return forms.ValidationError(
            "We couldn't sign you in. Check your email and password and try again.",
            code="invalid_login",
        )
