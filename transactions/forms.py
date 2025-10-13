from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from crispy_bootstrap5.bootstrap5 import FloatingField

from .models import Transaction, Category
from accounts.models import Account

class TransactionBaseForm(forms.ModelForm):
    """
    Formulário base que define os campos comuns a todas as transações.
    Os campos de conta e categoria são filtrados para o usuário logado.
    """
    class Meta:
        model = Transaction
        fields = ['value', 'date', 'description', 'status', 'category', 'origin_account', 'destination_account']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Filtra os querysets para mostrar apenas o que pertence ao usuário
        self.fields['origin_account'].queryset = Account.objects.filter(owner=self.user, active=True)
        self.fields['destination_account'].queryset = Account.objects.filter(owner=self.user, active=True)
        
        # O queryset da categoria será definido nos formulários filhos

        # Configuração Crispy Forms
        self.helper = FormHelper()
        self.helper.form_method = 'post'

class IncomeForm(TransactionBaseForm):
    """Formulário específico para transações do tipo Receita."""
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(owner=self.user, type=Category.TransactionType.INCOME)
        self.fields['origin_account'].widget = forms.HiddenInput() # Esconde o campo

        self.helper.layout = Layout(
            FloatingField('value'),
            FloatingField('description'),
            Row(
                Column(FloatingField('date'), css_class='col-md-6'),
                Column(FloatingField('destination_account', label="Account"), css_class='col-md-6'),
                css_class='g-2'
            ),
            Row(
                Column(FloatingField('category'), css_class='col-md-6'),
                Column(FloatingField('status'), css_class='col-md-6'),
                css_class='g-2'
            ),
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
            FloatingField('value'),
            FloatingField('description'),
            Row(
                Column(FloatingField('date'), css_class='col-md-6'),
                Column(FloatingField('origin_account', label="Account"), css_class='col-md-6'),
                css_class='g-2'
            ),
            Row(
                Column(FloatingField('category'), css_class='col-md-6'),
                Column(FloatingField('status'), css_class='col-md-6'),
                css_class='g-2'
            ),
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