from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Q
from django.utils import timezone
from users.models import UserPreferences

from .models import Transaction, Category
from .forms import IncomeForm, ExpenseForm, TransferForm, CategoryForm
from accounts.models import Account


# --- VIEWS DE LISTAGEM (ARQUITETURA FINAL) ---
class BaseTransactionListView(LoginRequiredMixin, ListView):
    """
    Classe base para todas as listagens de transações. Lida com a lógica de
    data e contexto comum de forma robusta usando o método dispatch.
    """
    model = Transaction
    template_name = 'transactions/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 30
    report_date = None # Será definido no dispatch

    def dispatch(self, request, *args, **kwargs):
        """Define a data do relatório antes de qualquer outro método ser chamado."""
        year = self.kwargs.get('year', timezone.now().year)
        month = self.kwargs.get('month', timezone.now().month)
        self.report_date = datetime.date(year, month, 1)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset_base(self):
        """
        Retorna o queryset base redefinido para o regime de caixa.
        - Transações completas são filtradas por `completion_date`.
        - Transações pendentes/vencidas são filtradas por `date`.
        """
        user = self.request.user
        start_of_month = self.report_date
        end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)
        
        # Filtro para transações EFETIVADAS no mês
        completed_in_month_q = Q(
            status=Transaction.Status.COMPLETED,
            completion_date__range=[start_of_month, end_of_month]
        )
        
        # Filtro para transações PENDENTES no mês (pela data de vencimento)
        pending_in_month_q = Q(
            status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE],
            date__range=[start_of_month, end_of_month]
        )
        
        return Transaction.objects.filter(
            owner=user
        ).filter(
            completed_in_month_q | pending_in_month_q
        ).select_related('category', 'origin_account__country', 'destination_account__country')

    def get_context_data(self, **kwargs):
        """Prepara o contexto comum (navegação, moeda, etc.)."""
        context = super().get_context_data(**kwargs)
        user_prefs, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        context['preferred_currency'] = user_prefs.preferred_currency
        context['current_month'] = self.report_date
        context['previous_month'] = self.report_date - relativedelta(months=1)
        context['next_month'] = self.report_date + relativedelta(months=1)
        context['base_url_name'] = self.request.resolver_match.url_name.replace('_specific', '')
        return context

class TransactionTypeListView(BaseTransactionListView):
    """View para listar transações por tipo (Receita, Despesa)."""
    transaction_type = None

    def get_queryset(self):
        return self.get_queryset_base().filter(type=self.transaction_type)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_transactions_for_month = self.get_queryset() # Queryset completo para cálculos
        
        completed = all_transactions_for_month.filter(status=Transaction.Status.COMPLETED).aggregate(total=Sum('value'))['total'] or 0
        forecasted = all_transactions_for_month.filter(status__in=[
            Transaction.Status.COMPLETED, Transaction.Status.PENDING, Transaction.Status.OVERDUE
        ]).aggregate(total=Sum('value'))['total'] or 0
        
        context['summary'] = {'completed': completed, 'forecasted': forecasted}
        context['transaction_type'] = self.transaction_type
        return context

class IncomeListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.INCOME
    
class ExpenseListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.EXPENSE

class TransferListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.TRANSFER

class TransactionByAccountListView(BaseTransactionListView):
    """View para exibir o extrato de uma conta específica."""
    def get_queryset(self):
        user = self.request.user
        start_of_month = self.report_date
        end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)
        
        completed_q = Q(status=Transaction.Status.COMPLETED, completion_date__range=[start_of_month, end_of_month])
        pending_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__range=[start_of_month, end_of_month])
        
        return Transaction.objects.filter(
            owner=user
        ).filter(
            completed_q | pending_q
        ).select_related(
            'category', 'origin_account__country', 'destination_account__country'
        ).order_by('-completion_date', '-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_transactions_for_month = self.get_queryset()
        user = self.request.user
        account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=user)
        
        is_future_month = self.report_date.year > timezone.now().year or \
                          (self.report_date.year == timezone.now().year and self.report_date.month > timezone.now().month)
        end_of_previous_month = self.report_date - relativedelta(days=1)
        
        # --- LÓGICA DE CÁLCULO DO SALDO INICIAL CORRIGIDA ---

        starting_balance = 0
        
        if is_future_month:
            # Para meses FUTUROS, o saldo inicial é o PREVISTO (inclui pendentes)
            context['starting_balance_type'] = 'Forecasted'
            
            # Filtro para transações completadas no passado
            completed_past_q = Q(status=Transaction.Status.COMPLETED, completion_date__lte=end_of_previous_month)
            # Filtro para transações pendentes/vencidas no passado
            pending_past_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__lte=end_of_previous_month)
            
            # Combina os filtros com um OR
            past_incomes = Transaction.objects.filter(
                Q(owner=user), Q(destination_account=account),
                completed_past_q | pending_past_q
            ).aggregate(total=Sum('value'))['total'] or 0
            
            past_expenses = Transaction.objects.filter(
                Q(owner=user), Q(origin_account=account),
                completed_past_q | pending_past_q
            ).aggregate(total=Sum('value'))['total'] or 0

            starting_balance = account.initial_balance + past_incomes - past_expenses

        else:
            # Para meses CORRENTES ou PASSADOS, o saldo inicial é o REAL (apenas completadas)
            context['starting_balance_type'] = 'Actual'

            past_incomes = Transaction.objects.filter(
                owner=user, destination_account=account, status=Transaction.Status.COMPLETED,
                completion_date__lte=end_of_previous_month
            ).aggregate(total=Sum('value'))['total'] or 0
            
            past_expenses = Transaction.objects.filter(
                owner=user, origin_account=account, status=Transaction.Status.COMPLETED,
                completion_date__lte=end_of_previous_month
            ).aggregate(total=Sum('value'))['total'] or 0
            
            starting_balance = account.initial_balance + past_incomes - past_expenses
            
        # --- FIM DA CORREÇÃO DO SALDO INICIAL ---

        # O resto da lógica de cálculo (movimentações do mês) já estava correta.
        income_this_month_completed = all_transactions_for_month.filter(status=Transaction.Status.COMPLETED, destination_account=account).aggregate(total=Sum('value'))['total'] or 0
        expense_this_month_completed = all_transactions_for_month.filter(status=Transaction.Status.COMPLETED, origin_account=account).aggregate(total=Sum('value'))['total'] or 0
        
        income_this_month_forecasted = all_transactions_for_month.filter(status__in=[Transaction.Status.COMPLETED, Transaction.Status.PENDING, Transaction.Status.OVERDUE], destination_account=account).aggregate(total=Sum('value'))['total'] or 0
        expense_this_month_forecasted = all_transactions_for_month.filter(status__in=[Transaction.Status.COMPLETED, Transaction.Status.PENDING, Transaction.Status.OVERDUE], origin_account=account).aggregate(total=Sum('value'))['total'] or 0

        context['account'] = account
        context['account_id'] = self.kwargs['account_id']
        context['summary'] = {
            'starting_balance': starting_balance,
            'income_this_month_completed': income_this_month_completed,
            'expense_this_month_completed': expense_this_month_completed,
            'current_balance': starting_balance + income_this_month_completed - expense_this_month_completed,
            'forecasted_balance': starting_balance + income_this_month_forecasted - expense_this_month_forecasted
        }
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
    

# --- VIEWS DE CATEGORIAS ---
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'transactions/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'transactions/category_form.html'
    success_url = reverse_lazy('transactions:category_list')

    # NOVO: Passa o usuário para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Category created successfully.")
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'transactions/category_form.html'
    success_url = reverse_lazy('transactions:category_list')
    
    # NOVO: Passa o usuário para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)
        
    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully.")
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'transactions/category_confirm_delete.html'
    success_url = reverse_lazy('transactions:category_list')
    
    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)
        
    def form_valid(self, form):
        messages.warning(self.request, "Category deleted successfully.")
        return super().form_valid(form)    
    
# --- VIEW PARA MARCAR TRANSAÇÃO COMO 'COMPLETED' ---
@login_required
@require_POST # Garante que esta view só pode ser acessada via método POST
def complete_transaction_view(request, pk):
    """
    Marca uma transação como 'Completed'.
    """
    # Busca a transação, garantindo que ela pertence ao usuário logado
    transaction = get_object_or_404(Transaction, pk=pk, owner=request.user)
    
    # Altera o status e salva. A lógica no model.save() cuidará do saldo.
    if transaction.status in [Transaction.Status.PENDING, Transaction.Status.OVERDUE]:
        transaction.status = Transaction.Status.COMPLETED
        transaction.save()
        messages.success(request, f"Transaction '{transaction.description}' marked as completed.")
    else:
        messages.warning(request, "This transaction has already been completed.")
        
    # Redireciona o usuário de volta para a página de onde ele veio (a lista)
    return redirect(request.META.get('HTTP_REFERER', reverse_lazy('transactions:list')))    