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


@login_required(login_url="users:login")
def home_view(request: HttpRequest, year=None, month=None) -> HttpResponse:
    user = request.user
    
    # --- 1. LÓGICA DE DATA E DETECÇÃO DE PERÍODO ---
    if year is None or month is None:
        report_date = timezone.now().date().replace(day=1)
    else:
        report_date = datetime.date(year, month, 1)

    today = timezone.now().date()
    is_current_or_past_month = report_date <= today.replace(day=1)
    end_of_period = (report_date + relativedelta(months=1)) - relativedelta(days=1)

    # --- 2. CÁLCULO DE SALDO POR CONTA (REAL OU PROJETADO) ---
    accounts = list(Account.objects.filter(owner=user, active=True).select_related("country"))
    
    # Status relevantes com base no período (passado/corrente vs. futuro)
    relevant_statuses = [Transaction.Status.COMPLETED]
    if not is_current_or_past_month:
        relevant_statuses.extend([Transaction.Status.PENDING, Transaction.Status.OVERDUE])
        
    for account in accounts:
        # Pega o saldo inicial da conta
        balance = account.initial_balance
        
        # Soma as movimentações até o final do período selecionado
        incomes = Transaction.objects.filter(
            owner=user, destination_account=account, date__lte=end_of_period, status__in=relevant_statuses
        ).aggregate(total=Sum('value'))['total'] or 0
        
        expenses = Transaction.objects.filter(
            owner=user, origin_account=account, date__lte=end_of_period, status__in=relevant_statuses
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Modifica o atributo .balance do objeto em memória para a view/template
        account.balance = balance + incomes - expenses

    # --- 3. (RESTAURADO) AGREGAÇÃO DE TOTAIS POR MOEDA ---
    currency_totals = {}
    for account in accounts:
        code = account.country.currency_code
        symbol = account.country.currency_symbol
        
        if code not in currency_totals:
            currency_totals[code] = {'total': Decimal('0.0'), 'symbol': symbol}
        
        # Soma o saldo já calculado (real ou projetado)
        currency_totals[code]['total'] += account.balance
    
    # Converte o dicionário para a lista que o template espera
    currency_totals_list = [
        {'code': code, 'total': data['total'], 'symbol': data['symbol']}
        for code, data in currency_totals.items()
    ]

    # --- 4. CÁLCULO DO PATRIMÔNIO TOTAL E PREPARAÇÃO DO GRÁFICO ---
    user_preferences, _ = UserPreferences.objects.get_or_create(user=user)
    total_net_worth, preferred_currency = None, None

    if user_preferences.preferred_currency:
        target_currency = user_preferences.preferred_currency
        # A função usa as contas com os saldos já ajustados
        total_net_worth, _ = calculate_total_net_worth(accounts, target_currency.currency_code)
        preferred_currency = target_currency
        
    chart_labels = [f"{acc.bank} ({acc.country.code})" for acc in accounts]
    chart_data = [str(acc.balance) for acc in accounts]

    # --- 5. LÓGICA DOS WIDGETS DE TRANSAÇÕES ---
    latest_transactions = Transaction.objects.filter(
        owner=user, status__in=[Transaction.Status.COMPLETED, Transaction.Status.OVERDUE],
        date__lte=today
    ).order_by('-date', '-created_at')[:5]

    upcoming_transactions = Transaction.objects.filter(
        owner=user, status=Transaction.Status.PENDING, date__gte=today
    ).order_by('date')[:5]
    
    # --- 6. LÓGICA DE COMPROMISSOS DO GOOGLE API ---
    google_connected = GoogleCredentials.objects.filter(user=user).exists()
    upcoming_calendar_events, upcoming_google_tasks = [], []
    if google_connected:
        appointments_data = get_upcoming_events(user) or {}
        upcoming_calendar_events = appointments_data.get('events', [])
        upcoming_google_tasks = appointments_data.get('tasks', [])

    # --- 7. MONTAGEM DO CONTEXTO FINAL ---
    context = {
        # Contexto de Navegação e Estado
        "title": "Dashboard",
        "report_date": report_date,
        "is_current_or_past_month": is_current_or_past_month,
        "previous_month": report_date - relativedelta(months=1),
        "next_month": report_date + relativedelta(months=1),
        
        # Contexto de Contas e Saldos
        "accounts": accounts,
        "currency_totals": currency_totals_list,
        "total_net_worth": total_net_worth,
        "preferred_currency": preferred_currency,

        # Dados para o Gráfico
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        
        # Widgets
        "latest_transactions": latest_transactions,
        "upcoming_transactions": upcoming_transactions,
        
        # API Google
        "google_connected": google_connected,
        "upcoming_calendar_events": upcoming_calendar_events,
        "upcoming_google_tasks": upcoming_google_tasks,
    }
    return render(request, "core/index.html", context)