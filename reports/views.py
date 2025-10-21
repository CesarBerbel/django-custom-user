#
# Arquivo: reports/views.py
#
import datetime
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from dateutil.relativedelta import relativedelta

class MonthlyReportRedirectView(LoginRequiredMixin, RedirectView):
    """Redireciona /reports/ para o relatório do mês atual."""
    
    def get_redirect_url(self, *args, **kwargs):
        today = timezone.now()
        # O padrão `permanent=False` é o correto aqui
        return reverse_lazy('reports:monthly', kwargs={'year': today.year, 'month': today.month})

class MonthlyReportView(LoginRequiredMixin, TemplateView):
    """Exibe o relatório mensal."""
    template_name = 'reports/monthly_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pega o ano e mês da URL
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        report_date = datetime.date(year, month, 1)

        # Prepara o contexto para navegação e título
        context['current_month'] = report_date
        context['previous_month'] = report_date - relativedelta(months=1)
        context['next_month'] = report_date + relativedelta(months=1)

        return context