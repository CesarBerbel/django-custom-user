from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Field, Div, HTML
from crispy_bootstrap5.bootstrap5 import FloatingField
from .models import Transaction, Category, RecurringTransaction
from accounts.models import Account

class TransactionBaseForm(forms.ModelForm):
    # --- NOVOS CAMPOS PARA PARCELAMENTO ---
    is_installment = forms.BooleanField(required=False, label="Is this an installment transaction?")
    
    # Pegamos os campos do modelo RecurringTransaction para adicioná-los aqui
    installments_total = forms.IntegerField(
        required=False, 
        min_value=2,
        label="Total number of installments", 
        widget=forms.NumberInput(attrs={'placeholder': 'e.g., 12'})
    )
    frequency = forms.ChoiceField(
        required=False,
        choices=RecurringTransaction.Frequency.choices, 
        label="Frequency"
    )
    
    class Meta:
        model = Transaction
        # Não incluímos os campos de parcelamento aqui
        fields = ['value', 'date', 'description', 'status', 'category', 'origin_account', 'destination_account']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, user, *args, **kwargs):
        # ... (a lógica de __init__ para filtrar querysets permanece a mesma)
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['origin_account'].queryset = Account.objects.filter(owner=self.user, active=True)
        self.fields['destination_account'].queryset = Account.objects.filter(owner=self.user, active=True)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = True

    # --- NOVO MÉTODO DE VALIDAÇÃO ---
    def clean(self):
        cleaned_data = super().clean()
        is_installment = cleaned_data.get('is_installment')
        
        if is_installment:
            installments_total = cleaned_data.get('installments_total')
            frequency = cleaned_data.get('frequency')

            if not installments_total:
                self.add_error('installments_total', 'This field is required when creating installments.')
            if not frequency:
                self.add_error('frequency', 'This field is required when creating installments.')

        return cleaned_data

class IncomeForm(TransactionBaseForm):
    """Formulário específico para transações do tipo Receita."""
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(owner=self.user, type=Category.TransactionType.INCOME)
        self.fields['origin_account'].widget = forms.HiddenInput() # Esconde o campo

        self.helper.layout = Layout(
            FloatingField('value', wrapper_class='mb-2'), # Usaremos valor como 'valor por parcela'
            FloatingField('description', wrapper_class='mb-2'),
            Row(
                Column(FloatingField('date', label="Date of first installment"), css_class='col-md-6'),
                Column(FloatingField('destination_account', label="Account"), css_class='col-md-6'),
                css_class='g-2 mb-2'
            ),
            Row(
                Column(FloatingField('category'), css_class='col-md-6'),
                Column(FloatingField('status'), css_class='col-md-6'),
                css_class='g-2 mb-3'
            ),
            # Seção de Parcelamento
            Field('is_installment', css_class="form-check-input"),
            Div(
                Row(
                    Column(FloatingField('installments_total'), css_class='col-md-6'),
                    Column(FloatingField('frequency'), css_class='col-md-6'),
                    css_class='g-2 mt-2'
                ),
                # Este id é crucial para o JavaScript
                id="installment-fields", 
                css_class="d-none mt-3 p-3 border rounded bg-light"
            ),
            # --- BOTÕES RESTAURADOS ABAIXO ---
            Div(
                Submit('submit', 'Save Income', css_class='btn btn-primary'),
                css_class="mt-4 pt-3 border-top"
            )
        )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.type = Transaction.TransactionType.INCOME
        instance.owner = self.user
        if commit:
            instance.save()
        return instance

class ExpenseForm(TransactionBaseForm):
    """Formulário específico para transações do tipo Despesa."""
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(owner=self.user, type=Category.TransactionType.EXPENSE)
        self.fields['destination_account'].widget = forms.HiddenInput()

        self.helper.layout = Layout(
            FloatingField('value', wrapper_class='mb-2'), # Usaremos valor como 'valor por parcela'
            FloatingField('description', wrapper_class='mb-2'),
            Row(
                Column(FloatingField('date', label="Date of first installment"), css_class='col-md-6'),
                Column(FloatingField('origin_account', label="Account"), css_class='col-md-6'),
                css_class='g-2 mb-2'
            ),
            Row(
                Column(FloatingField('category'), css_class='col-md-6'),
                Column(FloatingField('status'), css_class='col-md-6'),
                css_class='g-2 mb-3'
            ),
            # Seção de Parcelamento
            Field('is_installment', css_class="form-check-input"),
            Div(
                Row(
                    Column(FloatingField('installments_total'), css_class='col-md-6'),
                    Column(FloatingField('frequency'), css_class='col-md-6'),
                    css_class='g-2 mt-2'
                ),
                # Este id é crucial para o JavaScript
                id="installment-fields", 
                css_class="d-none mt-3 p-3 border rounded bg-light"
            ),
            # --- BOTÕES RESTAURADOS ABAIXO ---
            Div(
                Submit('submit', 'Save Expense', css_class='btn btn-primary'),
                css_class="mt-4 pt-3 border-top"
            )
        )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.type = Transaction.TransactionType.EXPENSE
        instance.owner = self.user
        if commit:
            instance.save()
        return instance
        
class TransferForm(TransactionBaseForm):
    """Formulário específico para transações do tipo Transferência."""
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['category'].widget = forms.HiddenInput()
        
        self.helper.layout = Layout(
            FloatingField('value'),
            FloatingField('description'),
            Row(
                Column(FloatingField('origin_account', label="From Account"), css_class='col-md-6'),
                Column(FloatingField('destination_account', label="To Account"), css_class='col-md-6'),
                css_class='g-2'
            ),
            Row(
                Column(FloatingField('date'), css_class='col-md-6'),
                Column(FloatingField('status'), css_class='col-md-6'),
                css_class='g-2'
            ),
            # --- BOTÕES RESTAURADOS ABAIXO ---
            Div(
                Submit('submit', 'Save Transfer', css_class='btn btn-primary'),
                css_class="mt-4 pt-3 border-top"
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        origin_account = cleaned_data.get('origin_account')
        destination_account = cleaned_data.get('destination_account')

        if origin_account and destination_account and origin_account == destination_account:
            raise ValidationError("Origin and destination accounts cannot be the same.")
        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.type = Transaction.TransactionType.TRANSFER
        instance.owner = self.user
        if commit:
            instance.save()
        return instance
    
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon', 'color']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}), # Usa o seletor de cores do HTML5
        }

    def __init__(self, *args, **kwargs):
        # 1. Remova o argumento 'user' de kwargs antes de qualquer outra coisa
        user = kwargs.pop('user', None)

        # 2. Chame o método pai __init__ com kwargs limpo
        super().__init__(*args, **kwargs)

        # 3. Agora podemos usar self.user com segurança
        if user is None:
            raise ValueError("CategoryForm requires a 'user' argument.")
        self.user = user
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            FloatingField('name'),
            FloatingField('type'),
            Row(
                Column(FloatingField('icon'), css_class='col-md-6'),
                Column('color', css_class='col-md-6 d-flex align-items-center'), # Classe customizada para alinhar
                css_class='g-2'
            )
        )

    def clean_name(self):
        # Normaliza o nome para evitar duplicatas como "Comida" e "comida"
        return self.cleaned_data['name'].capitalize()    
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        type = cleaned_data.get('type')

        if name and type:
            query = Category.objects.filter(
                owner=self.user,
                name__iexact=name.strip(),
                type=type
            )
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise ValidationError("A category with this name and type already exists.")
        return cleaned_data    
    
class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = [
            'description', 'value', 'installments_total', 'installments_paid', 'start_date', 'frequency', 
            'transaction_type', 'origin_account', 'destination_account', 'category'
        ]
        widgets = {'start_date': forms.DateInput(attrs={'type': 'date'})}
        labels = {
            'installments_total': 'Total Number of Installments',
            'installments_paid': 'Starting Installment Number',
            'value': 'Value per Installment'
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Filtra os querysets
        self.fields['origin_account'].queryset = Account.objects.filter(owner=user, active=True)
        self.fields['destination_account'].queryset = Account.objects.filter(owner=user, active=True)
        
        # Deixaremos o usuário escolher qualquer categoria por enquanto, mas podemos filtrar
        self.fields['category'].queryset = Category.objects.filter(owner=user)    