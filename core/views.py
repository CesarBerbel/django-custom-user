#
# Arquivo: core/views.py
# (Substitua a função home_view inteira)
#
import datetime
import json
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Account
from appointments.models import GoogleCredentials
from appointments.services import get_upcoming_events
from transactions.models import Transaction
from users.models import UserPreferences
from .services import calculate_total_net_worth
from .services import get_dashboard_context 


@login_required(login_url="users:login")
def home_view(request, year=None, month=None):
    """
    View "magra" para o dashboard. Delega toda a lógica de negócio
    para a camada de serviço e apenas renderiza a resposta.
    """
    if year and month:
        report_date = datetime.date(year, month, 1)
    else:
        report_date = timezone.now().date().replace(day=1)
    
    # Chama o serviço para obter todo o contexto de uma vez
    context = get_dashboard_context(user=request.user, report_date=report_date)
    
    # Adiciona o título e renderiza o template
    context['title'] = "Dashboard"
    return render(request, "core/index.html", context)