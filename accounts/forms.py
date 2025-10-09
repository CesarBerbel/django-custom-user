from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from crispy_bootstrap5.bootstrap5 import FloatingField
from .models import Account

class AccountCreateForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ("bank", "type", "country", "initial_balance")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            FloatingField("bank"),
            Row(
                Column(FloatingField("type"), css_class="col-12 col-md-6"),
                Column(FloatingField("country"), css_class="col-12 col-md-6"),
                css_class="g-2",
            ),
            FloatingField("initial_balance"),
            Submit("submit", "Save", css_class="btn btn-primary"),
        )

class AccountUpdateForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ("bank", "type", "country")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            FloatingField("bank"),
            Row(
                Column(FloatingField("type"), css_class="col-12 col-md-6"),
                Column(FloatingField("country"), css_class="col-12 col-md-6"),
                css_class="g-2",
            ),
            Submit("submit", "Save", css_class="btn btn-primary"),
        )        
