# users/forms_password.py
from __future__ import annotations
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from crispy_bootstrap5.bootstrap5 import FloatingField
from django.utils.translation import gettext_lazy as _

class CustomPasswordChangeForm(PasswordChangeForm):
    """Password change form with crispy layout and floating labels."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Labels + placeholders
        self.fields["old_password"].label = _("Current password")
        self.fields["new_password1"].label = _("New password")
        self.fields["new_password2"].label = _("Confirm new password")

        for name in ["old_password", "new_password1", "new_password2"]:
            self.fields[name].widget.attrs.update({"placeholder": self.fields[name].label})

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_tag = False  # form tag is in the template
        self.helper.layout = Layout(
            FloatingField("old_password"),
            FloatingField("new_password1"),
            FloatingField("new_password2"),
            Submit("submit", "Update password", css_class="btn btn-primary mt-2"),
        )

class CustomPasswordResetForm(PasswordResetForm):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            HTML('<h2 class="card-title text-center mb-2">Forgot Password?</h2>'),
            HTML('<p class="text-center text-muted mb-4">Enter your email and we will send you a link to reset your password.</p>'),
            
            FloatingField('email'),

            Submit('submit', 'Send Reset Link', css_class='btn-primary w-100 mt-3'),
            HTML('<div class="text-center mt-3"><a href="{% url \'users:login\' %}">Back to Sign in</a></div>')
        )