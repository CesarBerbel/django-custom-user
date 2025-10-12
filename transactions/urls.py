from django.urls import path, reverse_lazy
from django.views.generic import RedirectView 
from . import views

app_name = "transactions"

urlpatterns = [        
    # Views para listar por tipo
    path('incomes/', views.IncomeListView.as_view(), name='income_list'),
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('transfers/', views.TransferListView.as_view(), name='transfer_list'),

    # Views para criar transações
    path('income/create/', views.IncomeCreateView.as_view(), name='income_create'),
    path('expense/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('transfer/create/', views.TransferCreateView.as_view(), name='transfer_create'),
    
    # View para listar transações de uma conta específica
    path('account/<int:account_id>/', views.TransactionByAccountListView.as_view(), name='list_by_account'),
]