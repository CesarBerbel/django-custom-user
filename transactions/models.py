from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

# Importa o modelo de Conta da outra app
from accounts.models import Account

# Rule 5.1: Categorias podem ser criadas pelo usuário.
class Category(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = 'INCOME', 'Income'
        EXPENSE = 'EXPENSE', 'Expense'
        # Transferências não precisam de categoria própria, elas são um tipo de transação

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name="categories",
        help_text="User who owns this category"
    )
    name = models.CharField(max_length=100)
    # Rule 1.3: Categoria é específica por tipo
    type = models.CharField(max_length=7, choices=TransactionType.choices) 
    # Rule 5.2: Cor e ícone para a categoria
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="e.g., Bootstrap Icons class like 'bi-house-fill' See more in https://icons.getbootstrap.com/"
    )
    color = models.CharField(max_length=7, blank=True, help_text="Hex color code, e.g., #FF5733")

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ('owner', 'name', 'type') # Um usuário não pode ter categorias duplicadas para o mesmo tipo
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


# O modelo principal que lida com todas as transações
class Transaction(models.Model):
    # Rule 1.1: Tipos de transações
    class TransactionType(models.TextChoices):
        INCOME = 'INCOME', 'Income'
        EXPENSE = 'EXPENSE', 'Expense'
        TRANSFER = 'TRANSFER', 'Transfer'
    
    # Rule 3.1: Estados das transações
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        OVERDUE = 'OVERDUE', 'Overdue'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    type = models.CharField(max_length=8, choices=TransactionType.choices)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    
    # Rule 1.2: Associações
    # Nulo para Receitas (Income)
    origin_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_transactions"
    )
    # Nulo para Despesas (Expense)
    destination_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="received_transactions"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True, blank=True # Transferências não têm categoria
    )
    
    # Outros campos obrigatórios
    value = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(default=timezone.now)
    completion_date = models.DateField(
        null=True, blank=True,
        help_text="Date the transaction was actually completed/paid"
    )    

    recurring_transaction = models.ForeignKey(
        "RecurringTransaction",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="instances"
    )

    # NOVO CAMPO para registrar o número da parcela
    installment_number = models.PositiveIntegerField(null=True, blank=True)        
    description = models.CharField(max_length=255, default="Sem descrição")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Para recorrência (Fase 3)
    # recurring_transaction = models.ForeignKey('RecurringTransaction', null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['owner', 'date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_type_display()} of {self.value} on {self.date}"

    # Rule 4.2: Lógica de atualização de saldo
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
        
        if not is_new:
            old_instance = Transaction.objects.get(pk=self.pk)
            old_status = old_instance.status

        # Determina o status
        status_is_now_completed = self.status == self.Status.COMPLETED
        status_was_completed = old_status == self.Status.COMPLETED
        
        status_changed_to_completed = status_is_now_completed and not status_was_completed
        status_reverted_from_completed = not status_is_now_completed and status_was_completed

        # A lógica para a data de efetivação agora inclui o caso de criação
        if status_is_now_completed and self.completion_date is None:
            self.completion_date = timezone.now().date()
        elif status_reverted_from_completed:
            self.completion_date = None
        
        super().save(*args, **kwargs)

        # Lógica de saldo pós-save
        if status_changed_to_completed:
            self._process_completion()
        elif status_reverted_from_completed and not is_new:
            self._reverse_completion(old_instance)

    def _process_completion(self):
        """Applies the transaction's effect on account balances."""
        if self.type == self.TransactionType.EXPENSE and self.origin_account:
            self.origin_account.balance -= self.value
            self.origin_account.save(update_fields=['balance'])
            
        elif self.type == self.TransactionType.INCOME and self.destination_account:
            self.destination_account.balance += self.value
            self.destination_account.save(update_fields=['balance'])
            
        elif self.type == self.TransactionType.TRANSFER and self.origin_account and self.destination_account:
            self.origin_account.balance -= self.value
            self.destination_account.balance += self.value
            self.origin_account.save(update_fields=['balance'])
            self.destination_account.save(update_fields=['balance'])

    def _reverse_completion(self, old_transaction):
        """Reverts the transaction's effect on account balances."""
        if old_transaction.type == self.TransactionType.EXPENSE and old_transaction.origin_account:
            old_transaction.origin_account.balance += old_transaction.value
            old_transaction.origin_account.save(update_fields=['balance'])
            
        elif old_transaction.type == self.TransactionType.INCOME and old_transaction.destination_account:
            old_transaction.destination_account.balance -= old_transaction.value
            old_transaction.destination_account.save(update_fields=['balance'])
            
        elif old_transaction.type == self.TransactionType.TRANSFER and old_transaction.origin_account and old_transaction.destination_account:
            old_transaction.origin_account.balance += old_transaction.value
            old_transaction.destination_account.balance -= old_transaction.value
            old_transaction.origin_account.save(update_fields=['balance'])
            old_transaction.destination_account.save(update_fields=['balance'])

class RecurringTransaction(models.Model):
    class Frequency(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        BIWEEKLY = 'BIWEEKLY', 'Biweekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        SEMESTRAL = 'SEMESTRAL', 'Semestral'
        ANNUALLY = 'ANNUALLY', 'Annually'
        
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recurring_transactions")
    
    # Modelo para as transações a serem geradas
    start_date = models.DateField()
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    
    installments_total = models.PositiveIntegerField()
    installments_paid = models.PositiveIntegerField(default=1) # Parcela inicial

    value = models.DecimalField(max_digits=14, decimal_places=2, help_text="Value of each installment")
    description = models.CharField(max_length=255)
    
    transaction_type = models.CharField(max_length=8, choices=Transaction.TransactionType.choices)
    origin_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    destination_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Installment: {self.description}"            