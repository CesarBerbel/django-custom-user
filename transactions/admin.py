from django.contrib import admin
from .models import Category, Transaction
from django.contrib import messages

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
        
        updated_count = 0
        # Itera sobre os objetos selecionados
        for transaction in queryset:
            # Chama nosso novo método de modelo!
            if transaction.complete():
                updated_count += 1
                
        self.message_user(request, f"{updated_count} transaction(s) were successfully marked as completed.", messages.SUCCESS)

    @admin.action(description='Delete selected transactions (reverting balances)')
    def custom_delete_selected_action(self, request, queryset):
        """
        Ação que chama o método .delete() de cada objeto, garantindo que a
        lógica de negócio (reversão de saldo) seja executada.
        """
        count = queryset.count()
        for obj in queryset:
            obj.delete()
        
        plural = 's' if count != 1 else ''
        self.message_user(request, f"{count} transaction{plural} were successfully deleted and balances adjusted.", messages.WARNING)

    def get_actions(self, request):
        """
        Sobrescreve este método para remover a ação de exclusão padrão do Django.
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions        