from django.db import models
from django.conf import settings
from django.utils import timezone
from .querysets import TransactionQuerySet
from django.db.models import F
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

    objects = TransactionQuerySet.as_manager()

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

    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=8, null=True, blank=True,
        help_text="Exchange rate applied at the time of the transfer"
    )
    converted_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="The value in the destination account's currency"
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

    def complete(self) -> bool:
        if self.status in [self.Status.PENDING, self.Status.OVERDUE]:
            self.status = self.Status.COMPLETED
            self.save()
            return True
        return False

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
        old_instance = None
        if not is_new:
            old_instance = Transaction.objects.get(pk=self.pk)
            old_status = old_instance.status

        status_is_now_completed = self.status == self.Status.COMPLETED
        status_was_completed = old_status == self.Status.COMPLETED
        
        status_changed_to_completed = status_is_now_completed and not status_was_completed
        status_reverted_from_completed = not status_is_now_completed and status_was_completed

        if status_is_now_completed and self.completion_date is None:
            self.completion_date = timezone.now().date()
        elif status_reverted_from_completed:
            self.completion_date = None
        
        super().save(*args, **kwargs)

        if status_changed_to_completed:
            self._process_balance_changes()
        elif status_reverted_from_completed and old_instance:
            self._reverse_balance_changes(old_instance)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED:
            self._reverse_balance_changes(self)
        return super().delete(*args, **kwargs)

    def _process_balance_changes(self):
        if self.type == self.TransactionType.EXPENSE and self.origin_account:
            Account.objects.filter(pk=self.origin_account.pk).update(balance=F('balance') - self.value)
        elif self.type == self.TransactionType.INCOME and self.destination_account:
            Account.objects.filter(pk=self.destination_account.pk).update(balance=F('balance') + self.value)
        elif self.type == self.TransactionType.TRANSFER and self.origin_account and self.destination_account:
            value_to_add = self.converted_value if self.converted_value is not None else self.value
            Account.objects.filter(pk=self.origin_account.pk).update(balance=F('balance') - self.value)
            Account.objects.filter(pk=self.destination_account.pk).update(balance=F('balance') + value_to_add)

    def _reverse_balance_changes(self, transaction_to_revert):
        ttype = transaction_to_revert.type
        origin_account = transaction_to_revert.origin_account
        dest_account = transaction_to_revert.destination_account
        value = transaction_to_revert.value
        converted_value = transaction_to_revert.converted_value
        
        if ttype == self.TransactionType.EXPENSE and origin_account:
            Account.objects.filter(pk=origin_account.pk).update(balance=F('balance') + value)
        elif ttype == self.TransactionType.INCOME and dest_account:
            Account.objects.filter(pk=dest_account.pk).update(balance=F('balance') - value)
        elif ttype == self.TransactionType.TRANSFER and origin_account and dest_account:
            value_to_subtract = converted_value if converted_value is not None else value
            Account.objects.filter(pk=origin_account.pk).update(balance=F('balance') + value)
            Account.objects.filter(pk=dest_account.pk).update(balance=F('balance') - value_to_subtract)

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