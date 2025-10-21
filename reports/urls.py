#
# Arquivo: reports/urls.py
#
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # A URL principal redirecionará para o relatório do mês atual
    path('', views.MonthlyReportRedirectView.as_view(), name='index'),
    # URL específica para o relatório de um mês/ano
    path('<int:year>/<int:month>/', views.MonthlyReportView.as_view(), name='monthly'),
    
    # NOVAS URLs para filtro por conta
    # Ex: /reports/account/5/ (mês atual)
    path('account/<int:account_id>/', views.MonthlyReportView.as_view(), name='monthly_by_account'),
    # Ex: /reports/2025/10/account/5/
    path('<int:year>/<int:month>/account/<int:account_id>/', views.MonthlyReportView.as_view(), name='monthly_by_account_specific'),
]