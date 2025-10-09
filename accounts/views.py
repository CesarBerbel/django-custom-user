from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views import generic
from .models import Account
from .forms import AccountCreateForm, AccountUpdateForm
from django.utils import timezone


class AccountListView(LoginRequiredMixin, generic.ListView):
    model = Account
    template_name = "accounts/account_list.html"
    context_object_name = "accounts"
    ordering = ["-updated_at"]

    def get_queryset(self):
        # show only active accounts
        return Account.objects.filter(active=True).order_by("-updated_at")


class AccountCreateView(LoginRequiredMixin, generic.CreateView):
    model = Account
    form_class = AccountCreateForm
    template_name = "accounts/account_form.html"
    success_url = reverse_lazy("accounts:list")

    def form_valid(self, form):
        # ensure created as active; balance will default to initial in model.save()
        obj = form.save(commit=False)
        obj.active = True
        obj.save()
        messages.success(self.request, f"Account '{obj.bank}' created successfully.")
        return super().form_valid(form)


class AccountUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = Account
    form_class = AccountUpdateForm
    template_name = "accounts/account_form.html"
    success_url = reverse_lazy("accounts:list")

    def form_valid(self, form):
        messages.success(self.request, f"Account '{form.instance.bank}' updated successfully.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, generic.DeleteView):
    """
    Soft delete: marks account as inactive and sets deactivated_at via model.delete().
    """
    model = Account
    template_name = "accounts/account_confirm_delete.html"
    success_url = reverse_lazy("accounts:list")

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()  # soft delete via model.delete()
        messages.warning(request, f"Account '{obj.bank}' has been deactivated.")
        return super().delete(request, *args, **kwargs)
