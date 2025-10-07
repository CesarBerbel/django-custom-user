from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

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
