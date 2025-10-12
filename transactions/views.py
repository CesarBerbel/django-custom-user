from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.contrib import messages

from .models import Transaction
from .forms import IncomeForm, ExpenseForm, TransferForm
from accounts.models import Account

# --- VIEWS DE LISTAGEM ---

class TransactionListView(LoginRequiredMixin, ListView):
    """View para listar TODAS as transações do usuário."""
    model = Transaction
    template_name = 'transactions/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 15

    def get_queryset(self):
        return Transaction.objects.filter(owner=self.request.user)

class TransactionTypeListView(TransactionListView):
    """View base para listar transações de um tipo específico."""
    transaction_type = None

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(type=self.transaction_type)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction_type'] = self.transaction_type
        return context

class IncomeListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.INCOME
    
class ExpenseListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.EXPENSE

class TransferListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.TRANSFER
    
class TransactionByAccountListView(TransactionListView):
    """View para listar transações de uma conta específica."""
    
    def get_queryset(self):
        account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=self.request.user)
        # Usamos models.Q para buscar transações onde a conta é origem OU destino
        from django.db.models import Q
        return Transaction.objects.filter(
            Q(owner=self.request.user),
            Q(origin_account=account) | Q(destination_account=account)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=self.request.user)
        return context

# --- VIEWS DE CRIAÇÃO ---

class TransactionCreateView(LoginRequiredMixin, CreateView):
    """View base para criar uma nova transação."""
    model = Transaction
    template_name = 'transactions/transaction_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f'{form.instance.get_type_display()} transaction created successfully.')
        return super().form_valid(form)

class IncomeCreateView(TransactionCreateView):
    form_class = IncomeForm
    success_url = reverse_lazy('transactions:income_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('transactions:income_list')
        return context    

class ExpenseCreateView(TransactionCreateView):
    form_class = ExpenseForm
    success_url = reverse_lazy('transactions:expense_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('transactions:expense_list')
        return context

class TransferCreateView(TransactionCreateView):
    form_class = TransferForm
    success_url = reverse_lazy('transactions:transfer_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('transactions:transfer_list')
        return context