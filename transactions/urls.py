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

    path('<int:pk>/complete/', views.complete_transaction_view, name='complete'),
    
    # View para listar transações de uma conta específica
    path('account/<int:account_id>/', views.TransactionByAccountListView.as_view(), name='list_by_account'),

    # URLs de Listagem COM data (para navegação mensal)
    path('incomes/<int:year>/<int:month>/', views.IncomeListView.as_view(), name='income_list_specific'),
    path('expenses/<int:year>/<int:month>/', views.ExpenseListView.as_view(), name='expense_list_specific'),
    path('transfers/<int:year>/<int:month>/', views.TransferListView.as_view(), name='transfer_list_specific'),
    path('account/<int:account_id>/<int:year>/<int:month>/', views.TransactionByAccountListView.as_view(), name='list_by_account_specific'),
    
    # NOVAS URLs PARA CATEGORIAS
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
]