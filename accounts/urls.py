from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.AccountListView.as_view(), name="list"),
    path("create/", views.AccountCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.AccountUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.AccountDeleteView.as_view(), name="delete"),

    # NOVAS URLs PARA ACCOUNT TYPES
    path('types/', views.AccountTypeListView.as_view(), name='type_list'),
    path('types/create/', views.AccountTypeCreateView.as_view(), name='type_create'),
    path('types/<int:pk>/edit/', views.AccountTypeUpdateView.as_view(), name='type_edit'),
    path('types/<int:pk>/delete/', views.AccountTypeDeleteView.as_view(), name='type_delete'),

    # NOVAS URLs PARA COUNTRIES
    path('countries/', views.CountryListView.as_view(), name='country_list'),
    path('countries/create/', views.CountryCreateView.as_view(), name='country_create'),
    path('countries/<int:pk>/edit/', views.CountryUpdateView.as_view(), name='country_edit'),
    path('countries/<int:pk>/delete/', views.CountryDeleteView.as_view(), name='country_delete'),
]
