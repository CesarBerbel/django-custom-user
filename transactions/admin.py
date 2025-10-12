from django.contrib import admin
from .models import Category, Transaction

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'owner', 'icon', 'color')
    list_filter = ('owner', 'type')
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'owner', 'type', 'value', 'status', 
        'category', 'origin_account', 'destination_account'
    )
    list_filter = ('owner', 'type', 'status', 'date')
    search_fields = ('description', 'category__name')
    autocomplete_fields = ('owner', 'category', 'origin_account', 'destination_account')
    
    # Ação customizada para marcar como "Efetivada"
    @admin.action(description='Mark selected transactions as Completed')
    def mark_as_completed(self, request, queryset):
        for transaction in queryset:
            transaction.status = Transaction.Status.COMPLETED
            transaction.save() # Isso vai disparar a lógica de atualização do saldo

    actions = [mark_as_completed]