# accounts/forms_password.py
from __future__ import annotations
from django.contrib.auth.forms import PasswordChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
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
        self.helper.layout = Layout(
            FloatingField("old_password"),
            FloatingField("new_password1"),
            FloatingField("new_password2"),
            Submit("submit", "Update password", css_class="btn btn-primary mt-2"),
        )
