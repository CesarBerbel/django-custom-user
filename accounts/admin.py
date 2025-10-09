from django.contrib import admin
from .models import Account, AccountType, Country, Bank


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "currency_code", "currency_symbol", "currency_name")
    list_filter = ("currency_code",)
    search_fields = ("code", "currency_code", "currency_name", "currency_symbol")

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("bank", "type", "country", "initial_balance", "balance", "active", "created_at")
    list_filter = ("active", "type", "country__code")
    search_fields = ("bank",)
    autocomplete_fields = ("type", "country")
    readonly_fields = ("created_at", "updated_at", "deactivated_at", "balance")