#
# Arquivo: reports/views.py
#
import datetime
import json
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
        
        expense_transactions = transactions.filter(type=Transaction.TransactionType.EXPENSE)
        
        category_spending = expense_transactions.values(
            'category__name', 'category__color'
        ).annotate(
            total=Sum('value')
        ).order_by('-total')

        uncategorized_total = expense_transactions.filter(category__isnull=True).aggregate(total=Sum('value'))['total'] or 0

        # Prepara os dados para o gráfico Chart.js
        chart_labels = [item['category__name'] or 'Uncategorized' for item in category_spending]
        
        # --- CORREÇÃO APLICADA AQUI ---
        # Converte cada 'Decimal' em 'str' para que seja serializável em JSON.
        chart_data = [str(item['total']) for item in category_spending]
        # --- FIM DA CORREÇÃO ---
        
        chart_colors = [item['category__color'] or '#808080' for item in category_spending]

        # Adiciona o total de não categorizados se houver
        if uncategorized_total > 0 and 'Uncategorized' not in chart_labels:
             chart_labels.append('Uncategorized')
             # --- CORREÇÃO APLICADA AQUI TAMBÉM ---
             chart_data.append(str(uncategorized_total))
             chart_colors.append('#808080')
             
        # Adiciona ao contexto
        context['category_spending'] = {
            'labels': json.dumps(chart_labels),
            'data': json.dumps(chart_data), # Agora `chart_data` é uma lista de strings
            'colors': json.dumps(chart_colors),
            'raw_data': category_spending
        }

        return context