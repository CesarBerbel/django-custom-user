#
# Arquivo: transactions/views.py
# (Versão Final, Completa e Verificada)
#
import datetime
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from core.services import get_conversion_rate

from accounts.models import Account
from users.models import UserPreferences
from .models import Transaction, Category, RecurringTransaction
from .forms import (
    IncomeForm, ExpenseForm, TransferForm, 
    CategoryForm, RecurringTransactionForm
)

# ==============================================================================
# VIEW DE AÇÃO SIMPLES
# ==============================================================================

@login_required
@require_POST
def complete_transaction_view(request, pk):
    """Marca uma transação pendente/vencida como 'Completed'."""
    transaction = get_object_or_404(Transaction, pk=pk, owner=request.user)
    
    if transaction.status in [Transaction.Status.PENDING, Transaction.Status.OVERDUE]:
        transaction.status = Transaction.Status.COMPLETED
        transaction.save()
        messages.success(request, f"Transaction '{transaction.description}' marked as completed.")
    else:
        messages.warning(request, "This transaction has already been completed.")
        
    return redirect(request.META.get('HTTP_REFERER', reverse_lazy('transactions:expense_list')))


# ==============================================================================
# VIEWS DE CRIAÇÃO
# ==============================================================================

class TransactionCreateMixin(LoginRequiredMixin):
    """Mixin para lidar com a lógica de criação de transação única vs. parcelada."""
    model = Transaction
    template_name = 'transactions/transaction_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
        
    def form_valid(self, form):
        is_installment = form.cleaned_data.get('is_installment')
        user = self.request.user
        transaction_type=self.get_transaction_type()

        if is_installment:
            try:
                total_installments = form.cleaned_data['installments_total']
                start_date = form.cleaned_data['date']
                frequency = form.cleaned_data['frequency']
                value = form.cleaned_data['value']
                description = form.cleaned_data['description']
                
                rec_tx = RecurringTransaction.objects.create(
                    owner=user, start_date=start_date, frequency=frequency,
                    installments_total=total_installments, value=value, description=description,
                    transaction_type=transaction_type,
                    origin_account=form.cleaned_data.get('origin_account'),
                    destination_account=form.cleaned_data.get('destination_account'),
                    category=form.cleaned_data.get('category')
                )
                
                self.object = rec_tx
                transactions_to_create = []
                current_date = start_date

                for i in range(1, total_installments + 1):
                    installment_desc = f"{description} [{i}/{total_installments}]"
                    transactions_to_create.append(Transaction(
                        owner=user, recurring_transaction=rec_tx, installment_number=i,
                        description=installment_desc, value=value, date=current_date, 
                        status=Transaction.Status.PENDING, type=transaction_type,
                        origin_account=rec_tx.origin_account,
                        destination_account=rec_tx.destination_account,
                        category=rec_tx.category
                    ))
                    
                    if frequency == RecurringTransaction.Frequency.DAILY: current_date += relativedelta(days=1)
                    elif frequency == RecurringTransaction.Frequency.WEEKLY: current_date += relativedelta(weeks=1)
                    elif frequency == RecurringTransaction.Frequency.BIWEEKLY: current_date += relativedelta(weeks=2)
                    elif frequency == RecurringTransaction.Frequency.MONTHLY: current_date += relativedelta(months=1)
                    elif frequency == RecurringTransaction.Frequency.SEMESTRAL: current_date += relativedelta(months=6)
                    elif frequency == RecurringTransaction.Frequency.ANNUALLY: current_date += relativedelta(years=1)

                Transaction.objects.bulk_create(transactions_to_create)
                messages.success(self.request, f"{len(transactions_to_create)} installments created.")
                return redirect(self.get_success_url())

            except Exception as e:
                messages.error(self.request, f"An error occurred while creating installments: {e}")
                return self.form_invalid(form)
                
        else:
            form.instance.type = transaction_type
            form.instance.owner = user
            messages.success(self.request, f'Transaction created successfully.')
            return super().form_valid(form)

    def get_transaction_type(self):
        raise NotImplementedError("Subclasses must implement get_transaction_type()")

class IncomeCreateView(TransactionCreateMixin, CreateView):
    form_class = IncomeForm
    success_url = reverse_lazy('transactions:income_list')
    def get_transaction_type(self): return Transaction.TransactionType.INCOME

class ExpenseCreateView(TransactionCreateMixin, CreateView):
    form_class = ExpenseForm
    success_url = reverse_lazy('transactions:expense_list')
    def get_transaction_type(self): return Transaction.TransactionType.EXPENSE

class TransferCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransferForm
    template_name = 'transactions/transaction_form.html'
    success_url = reverse_lazy('transactions:transfer_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        origin_account = form.cleaned_data.get('origin_account')
        destination_account = form.cleaned_data.get('destination_account')
        transaction = form.save(commit=False)
        transaction.owner = self.request.user
        transaction.type = Transaction.TransactionType.TRANSFER
        
        origin_currency = origin_account.country.currency_code
        dest_currency = destination_account.country.currency_code

        if origin_currency != dest_currency:
            try:
                rate = get_conversion_rate(origin_currency, dest_currency)
                converted_value = transaction.value * rate
                transaction.exchange_rate = rate
                transaction.converted_value = converted_value
                messages.info(self.request, f"Exchange rate applied: 1 {origin_currency} = {rate:.4f} {dest_currency}. Destination will receive {converted_value:.2f} {dest_currency}.")
            except Exception as e:
                form.add_error(None, f"Could not perform currency conversion: {e}")
                return self.form_invalid(form)
        
        # Chamada super().form_valid() agora está correta. A transação é salva.
        messages.success(self.request, "Transfer created successfully.")
        return super().form_valid(form)


# ==============================================================================
# VIEWS DE LISTAGEM
# ==============================================================================

class BaseMonthlyListView(LoginRequiredMixin, ListView):
    """Classe base APENAS para a navegação de data e contexto comum."""
    model = Transaction
    template_name = 'transactions/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 30
    report_date = None

    def dispatch(self, request, *args, **kwargs):
        year = self.kwargs.get('year', timezone.now().year)
        month = self.kwargs.get('month', timezone.now().month)
        self.report_date = datetime.date(year, month, 1)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_prefs, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        context['preferred_currency'] = user_prefs.preferred_currency
        context['current_month'] = self.report_date
        context['previous_month'] = self.report_date - relativedelta(months=1)
        context['next_month'] = self.report_date + relativedelta(months=1)
        context['base_url_name'] = self.request.resolver_match.url_name.replace('_specific', '')
        return context

# --- Hierarquia para Listas por Tipo ---
class TransactionTypeListView(BaseMonthlyListView):
    transaction_type = None

    def get_queryset(self):
        start_of_month = self.report_date
        end_of_month = (self.report_date + relativedelta(months=1)) - relativedelta(days=1)
        
        return Transaction.objects.filter(
            owner=self.request.user,
            type=self.transaction_type,
            date__range=[start_of_month, end_of_month] # Usa 'date' para competência
        ).select_related('category', 'origin_account', 'destination_account')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_month_tx = self.get_queryset()
        
        context['transaction_type'] = self.transaction_type
        context['summary'] = {
            'completed': all_month_tx.filter(status=Transaction.Status.COMPLETED).aggregate(total=Sum('value'))['total'] or 0,
            'forecasted': all_month_tx.filter(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE, Transaction.Status.COMPLETED]).aggregate(total=Sum('value'))['total'] or 0,
        }
        return context

class IncomeListView(TransactionTypeListView): transaction_type = Transaction.TransactionType.INCOME
class ExpenseListView(TransactionTypeListView): transaction_type = Transaction.TransactionType.EXPENSE
class TransferListView(TransactionTypeListView): transaction_type = Transaction.TransactionType.TRANSFER

# --- Hierarquia Separada para Lista por Conta ---
class TransactionByAccountListView(BaseMonthlyListView):
    def get_queryset(self):
        self.account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=self.request.user)
        start_of_month = self.report_date
        end_of_month = (self.report_date + relativedelta(months=1)) - relativedelta(days=1)
        
        completed_q = Q(status=Transaction.Status.COMPLETED, completion_date__range=[start_of_month, end_of_month])
        pending_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__range=[start_of_month, end_of_month])
        
        return Transaction.objects.filter(
            Q(owner=self.request.user),
            Q(origin_account=self.account) | Q(destination_account=self.account),
            completed_q | pending_q
        ).select_related('category').order_by('-completion_date', '-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_transactions_for_month = self.get_queryset()
        user = self.request.user
        account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=user)
        
        is_future_month = self.report_date.year > timezone.now().year or \
                          (self.report_date.year == timezone.now().year and self.report_date.month > timezone.now().month)
        end_of_previous_month = self.report_date - relativedelta(days=1)
        
        if is_future_month:
            context['starting_balance_type'] = 'Forecasted'
            completed_past_q = Q(status=Transaction.Status.COMPLETED, completion_date__lte=end_of_previous_month)
            pending_past_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__lte=end_of_previous_month)
            
            past_incomes = Transaction.objects.filter(Q(owner=user), Q(destination_account=account), completed_past_q | pending_past_q).aggregate(total=Sum('value'))['total'] or 0
            past_expenses = Transaction.objects.filter(Q(owner=user), Q(origin_account=account), completed_past_q | pending_past_q).aggregate(total=Sum('value'))['total'] or 0
            
            starting_balance = account.initial_balance + past_incomes - past_expenses
        else:
            context['starting_balance_type'] = 'Actual'
            past_incomes = Transaction.objects.filter(owner=user, destination_account=account, status=Transaction.Status.COMPLETED, completion_date__lte=end_of_previous_month).aggregate(total=Sum('value'))['total'] or 0
            past_expenses = Transaction.objects.filter(owner=user, origin_account=account, status=Transaction.Status.COMPLETED, completion_date__lte=end_of_previous_month).aggregate(total=Sum('value'))['total'] or 0
            starting_balance = account.initial_balance + past_incomes - past_expenses
            
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

# ==============================================================================
# VIEWS DE CATEGORIA (CRUD)
# ==============================================================================

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'transactions/category_list.html'
    context_object_name = 'categories'
    def get_queryset(self): return Category.objects.filter(owner=self.request.user)

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'transactions/category_form.html'
    success_url = reverse_lazy('transactions:category_list')
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
    def get_queryset(self): return Category.objects.filter(owner=self.request.user)
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully.")
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'transactions/category_confirm_delete.html'
    success_url = reverse_lazy('transactions:category_list')
    def get_queryset(self): return Category.objects.filter(owner=self.request.user)
    def form_valid(self, form):
        messages.warning(self.request, "Category deleted successfully.")
        return super().form_valid(form)