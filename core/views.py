from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url="users:login")
def home_view(request: HttpRequest) -> HttpResponse:
    """
    Render a simple home page.
    This view is intentionally minimal for a fresh start.
    """
    context = {
        "title": "Config Starter",
        "message": "It works! MTF 🚀",
    }
    return render(request, "core/index.html", context)
