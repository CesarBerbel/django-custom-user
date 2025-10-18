# core/services.py
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from accounts.models import Account
from accounts.services import get_exchange_rates
from transactions.models import Transaction
from appointments.services import get_upcoming_events, GoogleCredentials
from django.db.models import Q 

import json
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from users.models import UserPreferences

def calculate_total_net_worth(accounts, target_currency_code):
    """
    Calcula o patrimônio líquido total convertendo todos os saldos de conta
    para a moeda de destino.
    """
    if not target_currency_code or not accounts:
        return None, None

    # As taxas são geralmente baseadas em USD, então buscamos a base USD
    usd_based_rates = get_exchange_rates(base_currency='USD')
    if not usd_based_rates:
        return None, None
        
    total_in_usd = Decimal('0.0')

    # Passo 1: Converter todos os saldos para um denominador comum (USD)
    for account in accounts:
        balance = account.balance
        currency_code = account.country.currency_code.upper()
        
        if currency_code == 'USD':
            total_in_usd += balance
        else:
            rate_to_usd = usd_based_rates.get(currency_code)
            if rate_to_usd:
                # balance / rate = valor em USD (Ex: 5 EUR / 0.92 EUR/USD = X USD. ERRADO)
                # O correto é: balance / rate_EUR = valor em USD (Ex: 5 EUR / 0.92 EUR_por_USD -> Não faz sentido)
                # A API retorna 1 USD = X OTRA. Então valor / rate_to_usd
                # 1 USD = 0.92 EUR. Logo, 5 EUR / 0.92 = 5.43 USD
                # 1 USD = 5.0 BRL. Logo, 10 BRL / 5.0 = 2.0 USD
                usd_value = balance / Decimal(str(rate_to_usd))
                total_in_usd += usd_value
            else:
                print(f"Warning: No exchange rate found for {currency_code}")

    # Passo 2: Converter o total em USD para a moeda de destino do usuário
    rate_from_usd_to_target = usd_based_rates.get(target_currency_code.upper())
    
    if not rate_from_usd_to_target:
        print(f"Warning: Could not find target currency rate for {target_currency_code}")
        return None, None
    
    total_in_target_currency = total_in_usd * Decimal(str(rate_from_usd_to_target))

    return total_in_target_currency, target_currency_code

def get_dashboard_context(*, user: 'User', report_date: 'datetime.date') -> dict:
    """
    Orquestra a busca e o cálculo de todos os dados necessários para o dashboard.
    Retorna um dicionário de contexto pronto para o template.
    """

    # 1. Determina o estado do período
    today = timezone.now().date()
    is_current_or_past_month = report_date <= today.replace(day=1)
    end_of_period = (report_date + relativedelta(months=1)) - relativedelta(days=1)
    
    # 2. Obtém as contas e calcula seus saldos (reais ou projetados)
    # Aqui usamos nosso novo método de manager/queryset!
    accounts = Account.objects.filter(owner=user, active=True).with_calculated_balances(
        user=user,
        end_date=end_of_period,
        is_forecasted=not is_current_or_past_month
    )
    
    currency_totals, chart_labels, chart_data = {}, [], []
    for acc in accounts:
        # Prepara totais por moeda
        code = acc.country.currency_code
        if code not in currency_totals:
            currency_totals[code] = {'total': Decimal('0.0'), 'symbol': acc.country.currency_symbol}
        currency_totals[code]['total'] += acc.calculated_balance
        
        # Prepara dados do gráfico
        chart_labels.append(f"{acc.bank} ({acc.country.code})")
        chart_data.append(str(acc.calculated_balance))

        # Importante: Substituímos o .balance pelo calculado para consistência no template
        acc.balance = acc.calculated_balance

    currency_totals_list = [{'code': c, 'symbol': d['symbol'], 'total': d['total']} for c, d in currency_totals.items()]

    # 4. Calcula o patrimônio líquido total (com os saldos já calculados)
    user_preferences, _ = UserPreferences.objects.get_or_create(user=user)
    total_net_worth, preferred_currency = None, None
    if user_preferences.preferred_currency:
        target_currency = user_preferences.preferred_currency
        total_net_worth, _ = calculate_total_net_worth(accounts, target_currency.currency_code) # Passa a lista já modificada
        preferred_currency = target_currency

    latest_transactions = Transaction.objects.filter(
        owner=user
    ).filter(
        Q(status=Transaction.Status.COMPLETED, completion_date__lte=today) |
        Q(status=Transaction.Status.OVERDUE, date__lte=today)
    ).order_by('-completion_date', '-date')[:5]

    upcoming_transactions = Transaction.objects.filter(
        owner=user, status=Transaction.Status.PENDING, date__gte=today
    ).order_by('date')[:5]

    # 7. Busca os compromissos da API do Google
    google_connected = GoogleCredentials.objects.filter(user=user).exists()
    upcoming_calendar_events, upcoming_google_tasks = [], []
    if google_connected:
        appointments_data = get_upcoming_events(user) or {}
        upcoming_calendar_events = appointments_data.get('events', [])
        upcoming_google_tasks = appointments_data.get('tasks', [])

    # 8. Monta e retorna o dicionário de contexto final
    return {
        "report_date": report_date,
        "is_current_or_past_month": is_current_or_past_month,
        "previous_month": report_date - relativedelta(months=1),
        "next_month": report_date + relativedelta(months=1),
        "accounts": accounts,
        "currency_totals": currency_totals_list,
        "total_net_worth": total_net_worth,
        "preferred_currency": preferred_currency,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        "latest_transactions": latest_transactions,
        "upcoming_transactions": upcoming_transactions,
        "google_connected": google_connected,
        "upcoming_calendar_events": upcoming_calendar_events,
        "upcoming_google_tasks": upcoming_google_tasks,
    }