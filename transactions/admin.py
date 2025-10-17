#
# Arquivo: transactions/admin.py
#
from django.contrib import admin, messages
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
        'category', 'origin_account', 'destination_account', 'completion_date'
    )
    list_filter = ('owner', 'type', 'status', 'date')
    search_fields = ('description', 'category__name')
    autocomplete_fields = ('owner', 'category', 'origin_account', 'destination_account')
    
    # Ações customizadas
    actions = ['mark_as_completed', 'custom_delete_selected']

    @admin.action(description='Mark selected transactions as Completed')
    def mark_as_completed(self, request, queryset):
        for transaction in queryset:
            transaction.status = Transaction.Status.COMPLETED
            transaction.save() # Dispara a lógica de saldo e completion_date
        self.message_user(request, f"{queryset.count()} transaction(s) were marked as completed.", messages.SUCCESS)

    # --- NOVA AÇÃO DE EXCLUSÃO CUSTOMIZADA ---
    @admin.action(description='Delete selected transactions (reverting balances)')
    def custom_delete_selected(self, request, queryset):
        """
        Ação de exclusão que chama o método .delete() de cada objeto
        para garantir que a lógica de reversão de saldo seja executada.
        """
        count = queryset.count()
        # Itera sobre cada objeto e chama seu método delete() individualmente
        for obj in queryset:
            obj.delete()
            
        self.message_user(request, f"{count} transaction(s) were successfully deleted and balances adjusted.", messages.WARNING)

    def get_actions(self, request):
        """
        Sobrescreve este método para remover a ação de exclusão padrão ('delete_selected').
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions