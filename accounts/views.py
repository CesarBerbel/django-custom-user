from django.shortcuts import render
from django.core.exceptions import PermissionDenied

# Create your views here.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views import generic
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView
)
from .models import Account, AccountType, Country
from .forms import (
    AccountCreateForm, AccountUpdateForm, AccountTypeForm, CountryForm
)

class AccountListView(LoginRequiredMixin, generic.ListView):
    model = Account
    template_name = "accounts/account_list.html"
    context_object_name = "accounts"
    ordering = ["-updated_at"]

    def get_queryset(self):
        # show only active accounts
        return (Account.objects
                .filter(owner=self.request.user, active=True)
                .order_by("-updated_at"))


class AccountCreateView(LoginRequiredMixin, generic.CreateView):
    model = Account
    form_class = AccountCreateForm
    template_name = "accounts/account_form.html"
    success_url = reverse_lazy("accounts:list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        obj.active = True
        if obj.balance is None:
            obj.balance = obj.initial_balance
        obj.save()
        messages.success(self.request, f"Account '{obj.bank}' created successfully.")
        return super().form_valid(form)


class AccountUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = Account
    form_class = AccountUpdateForm
    template_name = "accounts/account_form.html"
    success_url = reverse_lazy("accounts:list")

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user, active=True)

    def form_valid(self, form):
        if form.instance.owner != self.request.user:
            raise PermissionDenied("You cannot edit this account.")
        messages.success(self.request, f"Account '{form.instance.bank}' updated successfully.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, generic.DeleteView):
    """
    Soft delete: marks account as inactive and sets deactivated_at via model.delete().
    """
    model = Account
    template_name = "accounts/account_confirm_delete.html"
    success_url = reverse_lazy("accounts:list")

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user, active=True)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.owner != request.user:
            raise PermissionDenied("You cannot delete this account.")
        obj.delete()  # soft delete
        messages.warning(request, f"Account '{obj.bank}' has been deactivated.")
        return super().delete(request, *args, **kwargs)

# --- VIEWS PARA ACCOUNT TYPE ---

class AccountTypeListView(LoginRequiredMixin, ListView):
    model = AccountType
    template_name = 'accounts/type_list.html'
    context_object_name = 'types'

class AccountTypeCreateView(LoginRequiredMixin, CreateView):
    model = AccountType
    form_class = AccountTypeForm
    template_name = 'accounts/setting_form.html'
    success_url = reverse_lazy('accounts:type_list')

    def form_valid(self, form):
        messages.success(self.request, "Account Type created successfully.")
        return super().form_valid(form)

class AccountTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = AccountType
    form_class = AccountTypeForm
    template_name = 'accounts/setting_form.html'
    success_url = reverse_lazy('accounts:type_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Account Type updated successfully.")
        return super().form_valid(form)

class AccountTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = AccountType
    template_name = 'accounts/setting_confirm_delete.html'
    success_url = reverse_lazy('accounts:type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['delete_message'] = f'Are you sure you want to delete the account type "{self.object.name}"?'
        return context

    def form_valid(self, form):
        messages.warning(self.request, "Account Type deleted successfully.")
        return super().form_valid(form)


# --- VIEWS PARA COUNTRY ---

class CountryListView(LoginRequiredMixin, ListView):
    model = Country
    template_name = 'accounts/country_list.html'
    context_object_name = 'countries'

class CountryCreateView(LoginRequiredMixin, CreateView):
    model = Country
    form_class = CountryForm
    template_name = 'accounts/setting_form.html'
    success_url = reverse_lazy('accounts:country_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Country/Currency created successfully.")
        return super().form_valid(form)

class CountryUpdateView(LoginRequiredMixin, UpdateView):
    model = Country
    form_class = CountryForm
    template_name = 'accounts/setting_form.html'
    success_url = reverse_lazy('accounts:country_list')

    def form_valid(self, form):
        messages.success(self.request, "Country/Currency updated successfully.")
        return super().form_valid(form)

class CountryDeleteView(LoginRequiredMixin, DeleteView):
    model = Country
    template_name = 'accounts/setting_confirm_delete.html'
    success_url = reverse_lazy('accounts:country_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['delete_message'] = f'Are you sure you want to delete "{self.object}"?'
        return context
    
    def form_valid(self, form):
        messages.warning(self.request, "Country/Currency deleted successfully.")
        return super().form_valid(form)