#
# Arquivo: reports/views.py
#
import datetime
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Q, F
from users.models import UserPreferences
from transactions.models import Transaction

class MonthlyReportRedirectView(LoginRequiredMixin, RedirectView):
    """Redireciona /reports/ para o relatório do mês atual."""
    
    def get_redirect_url(self, *args, **kwargs):
        today = timezone.now()
        # O padrão `permanent=False` é o correto aqui
        return reverse_lazy('reports:monthly', kwargs={'year': today.year, 'month': today.month})

class MonthlyReportView(LoginRequiredMixin, TemplateView):
    """Exibe o relatório mensal com fluxo de caixa e outras visualizações."""
    template_name = 'reports/monthly_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 1. Determina as datas do relatório (já existente)
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        report_date = datetime.date(year, month, 1)
        start_of_month = report_date
        end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

        # 2. Prepara o contexto de navegação (já existente)
        context['current_month'] = report_date
        context['previous_month'] = report_date - relativedelta(months=1)
        context['next_month'] = report_date + relativedelta(months=1)

        # 3. Adiciona a moeda preferida para formatar os totais
        user_prefs, _ = UserPreferences.objects.get_or_create(user=user)
        context['preferred_currency'] = user_prefs.preferred_currency

        # --- NOVA LÓGICA DE CÁLCULO DE FLUXO DE CAIXA ---

        # Query base para o regime de "caixa" do mês selecionado
        transactions_in_month_q = Q(
            Q(status=Transaction.Status.COMPLETED, completion_date__range=[start_of_month, end_of_month]) |
            Q(status__in=[Transaction.Status.PENDING, Transaction.Status.OVERDUE], date__range=[start_of_month, end_of_month])
        )
        transactions = Transaction.objects.filter(owner=user).filter(transactions_in_month_q)

        # 4. Agrega os totais
        # Nota: Estes cálculos ainda não fazem conversão de moeda, assumindo
        # que o usuário queira uma visão nominal por enquanto.
        completed_txs = transactions.filter(status=Transaction.Status.COMPLETED)
        
        income_real = completed_txs.filter(type=Transaction.TransactionType.INCOME).aggregate(total=Sum('value'))['total'] or 0
        expense_real = completed_txs.filter(type=Transaction.TransactionType.EXPENSE).aggregate(total=Sum('value'))['total'] or 0

        income_forecasted = transactions.filter(type=Transaction.TransactionType.INCOME).aggregate(total=Sum('value'))['total'] or 0
        expense_forecasted = transactions.filter(type=Transaction.TransactionType.EXPENSE).aggregate(total=Sum('value'))['total'] or 0

        # 5. Adiciona os totais ao contexto
        context['cash_flow'] = {
            'income_real': income_real,
            'expense_real': expense_real,
            'balance_real': income_real - expense_real,
            'income_forecasted': income_forecasted,
            'expense_forecasted': expense_forecasted,
            'balance_forecasted': income_forecasted - expense_forecasted,
        }
        
        return context