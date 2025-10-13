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

@login_required(login_url="users:login")
def home_view(request: HttpRequest) -> HttpResponse:
    # Lógica existente para contas
    accounts = Account.objects.filter(owner=request.user, active=True).select_related("country")
    
    currency_totals = list(
        accounts.values("country__currency_code", "country__currency_symbol")
        .annotate(total=Sum("balance"))
        .order_by("country__currency_code")
    )
    
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
        "accounts": accounts,
        "currency_totals": currency_totals,
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