from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from accounts.models import Account
from django.db.models import Sum
from decimal import Decimal
import json

@login_required(login_url="users:login")
def home_view(request: HttpRequest) -> HttpResponse:
    """
    Render the home page as a dashboard with account summaries and charts.
    """
    # Get active accounts for the logged-in user
    accounts = Account.objects.filter(owner=request.user, active=True).select_related("country")

    # Calculate total balances grouped by currency
    currency_totals = list(
        accounts.values("country__currency_code", "country__currency_symbol")
        .annotate(total=Sum("balance"))
        .order_by("country__currency_code")
    )
    
    # Prepare data for the chart
    chart_labels = [f"{acc.bank} ({acc.country.code})" for acc in accounts]
    # Convert Decimal to string to be JSON serializable
    chart_data = [str(acc.balance) for acc in accounts]

    context = {
        "title": "Dashboard",
        "accounts": accounts,
        "currency_totals": currency_totals,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
    }
    return render(request, "core/index.html", context)
