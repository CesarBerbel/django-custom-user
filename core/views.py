from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
import json
from .services import calculate_total_net_worth
from transactions.models import Transaction 
from accounts.models import Account
from appointments.models import GoogleCredentials
from appointments.services import get_upcoming_events
from users.models import UserPreferences
import datetime
from dateutil.relativedelta import relativedelta

@login_required(login_url="users:login")
def home_view(request: HttpRequest, year=None, month=None) -> HttpResponse:
    user = request.user
    
    # --- 1. LÓGICA DE DATA E DETECÇÃO DE PERÍODO ---
    if year is None or month is None:
        report_date = timezone.now().date().replace(day=1)
    else:
        report_date = datetime.date(year, month, 1)

    is_current_or_past_month = report_date <= timezone.now().date().replace(day=1)
    
    # --- 2. CÁLCULO DE SALDO POR CONTA (REAL OU PROJETADO) ---
    accounts = list(Account.objects.filter(owner=user, active=True).select_related("country"))
    
    # Status a serem considerados nas transações
    relevant_statuses = [Transaction.Status.COMPLETED]
    if not is_current_or_past_month: # Se for um mês futuro
        relevant_statuses.extend([Transaction.Status.PENDING, Transaction.Status.OVERDUE])

    # Fim do período para o qual estamos calculando
    end_of_period = (report_date + relativedelta(months=1)) - relativedelta(days=1)
    
    # Dicionário para armazenar saldos calculados
    calculated_balances = {}
    for account in accounts:
        # Pega o saldo inicial da conta
        balance = account.initial_balance
        
        # Soma as movimentações até o final do período
        incomes = Transaction.objects.filter(
            owner=user, destination_account=account, date__lte=end_of_period, status__in=relevant_statuses
        ).aggregate(total=Sum('value'))['total'] or 0
        
        expenses = Transaction.objects.filter(
            owner=user, origin_account=account, date__lte=end_of_period, status__in=relevant_statuses
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Define o novo saldo (real ou projetado)
        account.balance = balance + incomes - expenses
        calculated_balances[account.id] = account.balance

    # --- 3. CÁLCULO DO PATRIMÔNIO TOTAL E PREPARAÇÃO PARA GRÁFICO ---
    user_preferences, _ = UserPreferences.objects.get_or_create(user=user)
    total_net_worth, preferred_currency = None, None

    if user_preferences.preferred_currency:
        target_currency = user_preferences.preferred_currency
        # A função de cálculo do patrimônio precisa ser chamada com as contas cujos saldos já foram ajustados
        total_net_worth, _ = calculate_total_net_worth(accounts, target_currency.currency_code)
        preferred_currency = target_currency
        
    chart_labels = [f"{acc.bank} ({acc.country.code})" for acc in accounts]
    chart_data = [str(acc.balance) for acc in accounts]

    # --- NOVA LÓGICA PARA COMPROMISSOS ---
    google_connected = GoogleCredentials.objects.filter(user=request.user).exists()
    
    # Inicializa as listas como vazias
    upcoming_calendar_events = []
    upcoming_google_tasks = []

    if google_connected:
        appointments_data = get_upcoming_events(request.user) or {}
        upcoming_calendar_events = appointments_data.get('events', [])
        upcoming_google_tasks = appointments_data.get('tasks', [])
    # --- FIM DA NOVA LÓGICA ---

    latest_transactions = Transaction.objects.filter(
        owner=request.user,
        status__in=[Transaction.Status.COMPLETED, Transaction.Status.OVERDUE],
    ).order_by('-date', '-created_at')[:5]

    # 3. Busca as 5 próximas transações pendentes/vencidas, ordenadas pela data mais próxima
    upcoming_transactions = Transaction.objects.filter(
        owner=request.user,
        status=Transaction.Status.PENDING,
        date__gte=timezone.now().date() # Somente as do futuro ou de hoje
    ).order_by('date')[:5]

    # --- LÓGICA DO PATRIMÔNIO LÍQUIDO TOTAL (CORRIGIDA) ---
    total_net_worth, preferred_currency = None, None
    
    # 1. Obtenha ou crie as preferências do usuário de forma segura.
    user_preferences, created = UserPreferences.objects.get_or_create(user=request.user)
    
    # 2. Verifique se a moeda preferida está definida no objeto de preferências.
    if user_preferences.preferred_currency:
        target_currency = user_preferences.preferred_currency
        total_net_worth, _ = calculate_total_net_worth(accounts, target_currency.currency_code)
        preferred_currency = target_currency
    # --- FIM DA LÓGICA CORRIGIDA ---

    context = {
        "title": "Dashboard",
        "report_date": report_date,
        "is_current_or_past_month": is_current_or_past_month,
        "previous_month": report_date - relativedelta(months=1),
        "next_month": report_date + relativedelta(months=1),
        
        "accounts": accounts,
        "total_net_worth": total_net_worth,
        "preferred_currency": preferred_currency,

        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),

        "google_connected": google_connected,
        "upcoming_calendar_events": upcoming_calendar_events, # Nova variável de contexto
        "upcoming_google_tasks": upcoming_google_tasks,     # Nova variável de contexto
        "latest_transactions": latest_transactions,
        "upcoming_transactions": upcoming_transactions,
        "total_net_worth": total_net_worth,
        "preferred_currency": preferred_currency,
    }
    return render(request, "core/index.html", context)