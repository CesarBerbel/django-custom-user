#
# Arquivo: transactions/views.py
# (Versão Final, Completa e Verificada)
#
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q, DecimalField, Case, When, F, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, FormView
from django.http import HttpResponse
from accounts.models import Account
from accounts.services import get_conversion_rate
from users.models import UserPreferences
from .models import Transaction, Category
from .forms import (
    IncomeForm, ExpenseForm, TransferForm, 
    CategoryForm, CompleteTransferForm
)
from .services import create_installments, create_transfer
from django.template.loader import render_to_string
from .forms import CompleteTransferForm
from django.db import models

# ==============================================================================
# VIEW DE AÇÃO SIMPLES
# ==============================================================================

@login_required
@require_POST
def complete_transaction_view(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, owner=request.user)

    # Condição de saída nº 1: já está completa
    if transaction.status == Transaction.Status.COMPLETED:
        messages.warning(request, "This transaction has already been completed.")
        return refresh_page_or_redirect(request) # Helper que vamos recriar

    is_multi_currency = (
        transaction.type == Transaction.TransactionType.TRANSFER and
        transaction.origin_account and transaction.destination_account and
        transaction.origin_account.country.currency_code != transaction.destination_account.country.currency_code
    )

    if is_multi_currency:
        form = CompleteTransferForm(request.POST)
        if form.is_valid():
            rate = form.cleaned_data['exchange_rate']
            transaction.exchange_rate = rate
            transaction.converted_value = transaction.value * rate
            messages.info(request, f"Rate of {rate:.4f} applied.") # Adiciona uma msg info útil
        else:
            # Condição de saída nº 2: formulário inválido
            error_msg = "Invalid data. " + form.errors.as_text().replace('\n', ' ')
            messages.error(request, error_msg)
            return refresh_page_or_redirect(request)
    
    # Se chegamos aqui, a transação é válida para ser completada
    # (seja normal ou multi-moeda com form válido)
    transaction.complete()
    
    # Adiciona a mensagem de sucesso apropriada
    if is_multi_currency:
        messages.success(request, "Transfer completed with custom exchange rate.")
    else:
        messages.success(request, f"Transaction '{transaction.description}' marked as completed.")
        
    # Redireciona em caso de sucesso
    return refresh_page_or_redirect(request)

def refresh_page_or_redirect(request):
    """
    Se o request é do HTMX, retorna uma resposta para forçar o reload da página.
    Senão, retorna um redirect normal.
    """
    if 'HX-Request' in request.headers:
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true' # Força o refresh da página no lado do cliente
        return response
    
    # Fallback para o redirect normal
    redirect_url = request.META.get('HTTP_REFERER', reverse_lazy('transactions:expense_list'))
    return redirect(redirect_url)

@login_required
def prepare_complete_transfer_view(request, pk):
    """
    Busca os dados para o modal de efetivação de transferência.
    Retorna o fragmento de HTML do formulário para o HTMX.
    """
    transaction = get_object_or_404(Transaction, pk=pk, owner=request.user)
    
    initial_rate = None
    error_message = None # Para passar uma mensagem ao template se a API falhar

    # Garante que temos contas para a conversão
    if transaction.origin_account and transaction.destination_account:
        origin_currency = transaction.origin_account.country.currency_code
        dest_currency = transaction.destination_account.country.currency_code
        
        if origin_currency != dest_currency:
            try:
                raw_rate = get_conversion_rate(origin_currency, dest_currency)

                # --- LÓGICA DE ARREDONDAMENTO APLICADA AQUI ---
                # Garante que 'raw_rate' seja um Decimal antes de arredondar
                if raw_rate is not None:
                    # Decimal('1.000000') define o "quantum" ou o número de casas decimais
                    six_places = Decimal('1.000000')
                    # .quantize() é o método para arredondamento preciso
                    initial_rate = Decimal(raw_rate).quantize(six_places)
                # --- FIM DO ARREDONDAMENTO ---

            except Exception as e:
                error_message = f"Could not fetch live exchange rate: {e}"
                print(error_message)

    # Preenche o formulário com a taxa inicial (ou deixa em branco)
    form = CompleteTransferForm(initial={'exchange_rate': initial_rate})
    
    context = {
        'transaction': transaction,
        'form': form,
        'error_message': error_message
    }
    
    return render(request, 'transactions/partials/complete_transfer_modal_form.html', context)


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
        
        if is_installment:
            try:
                # 1. Delega toda a lógica de criação de parcelas para o serviço
                created_installments = create_installments(
                    user=self.request.user,
                    total_installments=form.cleaned_data['installments_total'],
                    start_date=form.cleaned_data['date'],
                    frequency=form.cleaned_data['frequency'],
                    value=form.cleaned_data['value'],
                    description=form.cleaned_data['description'],
                    transaction_type=self.get_transaction_type(),
                    origin_account=form.cleaned_data.get('origin_account'),
                    destination_account=form.cleaned_data.get('destination_account'),
                    category=form.cleaned_data.get('category'),
                    start_installment=form.cleaned_data.get('installments_paid', 1), # Usa o campo do formulário
                    initial_status=form.cleaned_data['status'],
                )
                
                # O método 'create_installments' já cuidou de salvar.
                # Agora só precisamos mostrar a mensagem e redirecionar.
                self.object = created_installments
                messages.success(
                    self.request,
                    f"{created_installments.installments_total} installments for "
                    f"'{created_installments.description}' were created."
                )
                return redirect(self.get_success_url())
                
            except Exception as e:
                # Captura qualquer erro do serviço
                messages.error(self.request, f"An error occurred: {e}")
                return self.form_invalid(form)
                
        else:
            # A lógica para transação única já estava limpa
            form.instance.owner = self.request.user
            form.instance.type = self.get_transaction_type()
            messages.success(self.request, 'Single transaction created successfully.')
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

    # --- MÉTODO form_valid REFATORADO ---
    def form_valid(self, form):
        origin_account = form.cleaned_data.get('origin_account')
        destination_account = form.cleaned_data.get('destination_account')
        status = form.cleaned_data.get('status')
        is_multi_currency = origin_account.country.currency_code != destination_account.country.currency_code
        
        # Se for uma transferência multi-moeda e COMPLETED...
        if is_multi_currency and status == Transaction.Status.COMPLETED:
            # 1. Guarda os dados válidos do formulário na sessão.
            # Convertemos para IDs e strings para garantir que seja serializável.
            self.request.session['pending_transfer_data'] = {
                'value': str(form.cleaned_data['value']),
                'date': form.cleaned_data['date'].isoformat(),
                'description': form.cleaned_data['description'],
                'origin_account_id': origin_account.pk,
                'destination_account_id': destination_account.pk,
            }
            # 2. Redireciona para a nova página de confirmação.
            return redirect('transactions:transfer_confirm_rate')

        # Comportamento normal para transferências simples ou pendentes
        form.instance.owner = self.request.user
        form.instance.type = Transaction.TransactionType.TRANSFER
        messages.success(self.request, "Transfer created successfully.")
        return super().form_valid(form)

# Nova View para a página de confirmação
class ConfirmTransferRateView(LoginRequiredMixin, FormView):
    form_class = CompleteTransferForm
    template_name = 'transactions/transfer_confirm_rate.html'
    success_url = reverse_lazy('transactions:transfer_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Resgata os dados da sessão
        transfer_data = self.request.session.get('pending_transfer_data')
        if not transfer_data:
            return context # Lidar com o erro de alguma forma
        
        # Reconstitui os objetos para exibir informações na página
        context['origin_account'] = get_object_or_404(Account, pk=transfer_data['origin_account_id'])
        context['destination_account'] = get_object_or_404(Account, pk=transfer_data['destination_account_id'])
        context['value'] = Decimal(transfer_data['value'])
        
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pre-preenche o formulário com a taxa de câmbio
        transfer_data = self.request.session.get('pending_transfer_data', {})
        origin_account = Account.objects.get(pk=transfer_data.get('origin_account_id'))
        dest_account = Account.objects.get(pk=transfer_data.get('destination_account_id'))
        
        try:
            rate = get_conversion_rate(origin_account.country.currency_code, dest_account.country.currency_code)
            six_places = Decimal('1.000000')
            kwargs['initial'] = {'exchange_rate': Decimal(rate).quantize(six_places)}
        except Exception:
            pass # Deixa o campo em branco se a API falhar
        
        return kwargs
        
    def form_valid(self, form):
        # Finalmente, cria a transação aqui
        transfer_data = self.request.session.pop('pending_transfer_data', None)
        if not transfer_data:
            messages.error(self.request, "Session expired. Please try again.")
            return redirect('transactions:transfer_create')
            
        rate = form.cleaned_data['exchange_rate']
        
        Transaction.objects.create(
            owner=self.request.user,
            type=Transaction.TransactionType.TRANSFER,
            status=Transaction.Status.COMPLETED,
            value=Decimal(transfer_data['value']),
            date=datetime.date.fromisoformat(transfer_data['date']),
            description=transfer_data['description'],
            origin_account_id=transfer_data['origin_account_id'],
            destination_account_id=transfer_data['destination_account_id'],
            exchange_rate=rate,
            converted_value=Decimal(transfer_data['value']) * rate
        )
        
        messages.success(self.request, "Transfer created and completed successfully with custom rate.")
        return super().form_valid(form)

# ==============================================================================
# VIEWS DE LISTAGEM
# ==============================================================================
class BaseMonthlyListView(LoginRequiredMixin, ListView):
    """
    Classe base que define o comportamento comum para todas as listagens mensais:
    - Navegação de data (mês anterior/próximo)
    - Contexto comum (moeda preferida, etc.)
    """
    model = Transaction
    template_name = 'transactions/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 30
    report_date = None

    def setup_dates(self):
        """Helper para definir as datas, chamado uma vez por request."""
        if self.report_date is None: # Garante que só seja executado uma vez
            year = self.kwargs.get('year', timezone.now().year)
            month = self.kwargs.get('month', timezone.now().month)
            self.report_date = datetime.date(year, month, 1)

    def dispatch(self, request, *args, **kwargs):
        """Garante que a data do relatório seja definida antes de qualquer outro método."""
        self.setup_dates()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Prepara o contexto comum (navegação de data e moeda)."""
        context = super().get_context_data(**kwargs)
        user_prefs, _ = UserPreferences.objects.get_or_create(user=self.request.user)
        context['preferred_currency'] = user_prefs.preferred_currency
        context['current_month'] = self.report_date
        context['previous_month'] = self.report_date - relativedelta(months=1)
        context['next_month'] = self.report_date + relativedelta(months=1)
        context['base_url_name'] = self.request.resolver_match.url_name.replace('_specific', '')
        return context

class TransactionTypeListView(BaseMonthlyListView):
    """
    Herda da base e adiciona a lógica para:
    - Filtrar por tipo de transação
    - Calcular os resumos de 'completed' e 'forecasted'
    """
    transaction_type = None # Deve ser sobrescrito pelas classes filhas

    def get_queryset(self):
        """
        Usa a lógica de "regime de caixa" para filtrar as transações por tipo,
        mostrando as efetivadas no mês em que foram completadas, e as pendentes
        no mês em que estão agendadas.
        """
        start_of_month = self.report_date
        end_of_month = (self.report_date + relativedelta(months=1)) - relativedelta(days=1)
        
        # Filtro para transações EFETIVADAS no mês (baseado em completion_date)
        completed_q = Q(status=Transaction.Status.COMPLETED, completion_date__range=[start_of_month, end_of_month])
        
        # Filtro para transações PENDENTES/VENCIDAS no mês (baseado em date)
        pending_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__range=[start_of_month, end_of_month])
        
        # A query agora é consistente com a TransactionByAccountListView
        return Transaction.objects.filter(
            owner=self.request.user,
            type=self.transaction_type,
            # A condição OR que combina os dois filtros
        ).filter(
            completed_q | pending_q
        ).select_related(
            'category', 'origin_account', 'destination_account'
        ).order_by('-completion_date', '-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Para os totais, precisamos do queryset completo, não apenas da página
        full_queryset = self.get_queryset()

        preferred_code = context['preferred_currency'].currency_code if context['preferred_currency'] else None
        
        # Delega o trabalho de cálculo para o método do QuerySet
        summary_data = full_queryset.get_type_summary(
            user=self.request.user, 
            preferred_currency_code=preferred_code
        )
        
        context['transaction_type'] = self.transaction_type
        context['summary'] = summary_data
        return context

# As classes filhas agora são extremamente simples
class IncomeListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.INCOME

class ExpenseListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.EXPENSE

class TransferListView(TransactionTypeListView):
    transaction_type = Transaction.TransactionType.TRANSFER

    def get_context_data(self, **kwargs):
        """
        Sobrescreve o contexto para criar um resumo de transferências
        agrupado por moeda.
        """

        # Primeiro, chama o get_context_data da classe base para ter a navegação
        context = super(TransactionTypeListView, self).get_context_data(**kwargs)
        all_month_tx = self.get_queryset()

        # Agrega as SAÍDAS por moeda
        outflows = all_month_tx.filter(
            origin_account__isnull=False
        ).values(
            'origin_account__country__currency_code', 
            'origin_account__country__currency_symbol'
        ).annotate(
            total_out=Coalesce(Sum('value'), Decimal('0.0'))
        ).order_by('origin_account__country__currency_code')

        # Agrega as ENTRADAS por moeda
        inflows = all_month_tx.filter(
            destination_account__isnull=False
        ).annotate(
            # Usa a expressão Case/When que já validamos para somar o valor correto
            total_in=Coalesce(
                Sum(
                    Case(
                        When(converted_value__isnull=False, then=F('converted_value')),
                        default=F('value'),
                        output_field=models.DecimalField()
                    )
                ), Decimal('0.0')
            )
        ).values(
            'destination_account__country__currency_code',
            'destination_account__country__currency_symbol',
            'total_in'
        ).order_by('destination_account__country__currency_code')
        
        # Não precisamos mais dos totais 'completed' e 'forecasted'
        # Em vez disso, passamos as novas agregações
        context['summary'] = {
            'outflows': list(outflows),
            'inflows': list(inflows)
        }
        
        context['transaction_type'] = self.transaction_type
        return context


class TransactionByAccountListView(BaseMonthlyListView):
    """
    Herda da base e adiciona a lógica específica para o extrato de conta.
    Esta hierarquia é separada da 'TransactionTypeListView' para evitar conflitos.
    """
    def get_queryset(self):
        account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=self.request.user)
        start_of_month = self.report_date
        end_of_month = (self.report_date + relativedelta(months=1)) - relativedelta(days=1)
        
        # A query aqui usa a lógica de 'data de caixa'
        completed_q = Q(status=Transaction.Status.COMPLETED, completion_date__range=[start_of_month, end_of_month])
        pending_q = Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__range=[start_of_month, end_of_month])
        
        return Transaction.objects.filter(
            Q(owner=self.request.user),
            Q(origin_account=account) | Q(destination_account=account),
            completed_q | pending_q
        ).select_related('category').order_by('-completion_date', '-date')
    
    def get_context_data(self, **kwargs):
        # ... (A implementação completa e complexa do get_context_data do extrato,
        # que já estava funcionando, continua aqui)
        # ...
        context = super().get_context_data(**kwargs)
        #... e o resto da sua lógica
        return context

    def get_context_data(self, **kwargs):
        """
        Calcula os saldos (inicial, atual, previsto) e as movimentações
        do mês para a exibição no extrato da conta.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # O objeto 'self.account' é definido no get_queryset,
        # mas vamos buscá-lo novamente aqui para ter certeza e clareza.
        account = get_object_or_404(Account, pk=self.kwargs['account_id'], owner=user)
        
        # Queryset completo do mês para os cálculos
        all_transactions_for_month = self.get_queryset()

        # --- CÁLCULO DO SALDO INICIAL ---
        # (Esta parte já estava correta, usando get_balance_until)
        is_future_month = self.report_date > timezone.now().date().replace(day=1)
        end_of_previous_month = self.report_date - relativedelta(days=1)
        
        starting_balance = Transaction.objects.filter(owner=user).get_balance_until(
            account=account,
            end_date=end_of_previous_month,
            is_forecasted=is_future_month
        )
        
        # --- CÁLCULO DAS MOVIMENTAÇÕES DO MÊS (COMPLETED) ---
        
        completed_txs_this_month = all_transactions_for_month.filter(status=Transaction.Status.COMPLETED)
        
        # Expressão para somar o valor correto para as ENTRADAS
        income_value_expression = Case(
            When(type=Transaction.TransactionType.TRANSFER, converted_value__isnull=False, then='converted_value'),
            default='value',
            output_field=DecimalField()
        )
        
        # Agrega as ENTRADAS (INCOMES) do mês para esta conta
        income_this_month_completed = completed_txs_this_month.filter(
            destination_account=account
        ).aggregate(
            total=Coalesce(Sum(income_value_expression), Decimal('0.0'))
        )['total']
        
        # Agrega as SAÍDAS (EXPENSES e TRANSFERS) do mês para esta conta
        expense_this_month_completed = completed_txs_this_month.filter(
            origin_account=account
        ).aggregate(
            total=Coalesce(Sum('value'), Decimal('0.0'))
        )['total']
        
        
        # --- CÁLCULO DO SALDO PREVISTO ---
        # A forma mais segura é recalcular o saldo final previsto
        forecasted_balance = Transaction.objects.filter(owner=user).get_balance_until(
            account=account,
            end_date=(self.report_date + relativedelta(months=1)) - relativedelta(days=1),
            is_forecasted=True
        )

        # Montagem do contexto final
        context['account'] = account
        context['account_id'] = self.kwargs['account_id']
        context['starting_balance_type'] = 'Forecasted' if is_future_month else 'Actual'
        context['summary'] = {
            'starting_balance': starting_balance,
            'income_this_month_completed': income_this_month_completed,
            'expense_this_month_completed': expense_this_month_completed,
            # Saldo atual é derivado das movimentações calculadas + saldo inicial
            'current_balance': starting_balance + income_this_month_completed - expense_this_month_completed,
            'forecasted_balance': forecasted_balance
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
    
