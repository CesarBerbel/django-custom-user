#
# Arquivo: transactions/models.py
# (Versão Completa e Corrigida)
#
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from accounts.models import Account
from dateutil.relativedelta import relativedelta


class Category(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = 'INCOME', 'Income'
        EXPENSE = 'EXPENSE', 'Expense'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories", help_text="User who owns this category")
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=7, choices=TransactionType.choices)
    icon = models.CharField(max_length=50, blank=True, help_text="e.g., Bootstrap Icons class like 'bi-house-fill'")
    color = models.CharField(max_length=7, blank=True, help_text="Hex color code, e.g., #FF5733")

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ('owner', 'name', 'type')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = 'INCOME', 'Income'
        EXPENSE = 'EXPENSE', 'Expense'
        TRANSFER = 'TRANSFER', 'Transfer'
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        OVERDUE = 'OVERDUE', 'Overdue'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=8, choices=TransactionType.choices)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    
    origin_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_transactions")
    destination_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_transactions")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    value = models.DecimalField(max_digits=14, decimal_places=2, help_text="In the currency of the origin account for expenses/transfers, or destination for incomes")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True, help_text="Exchange rate applied at the time of the transfer")
    converted_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text="The value in the destination account's currency")

    date = models.DateField(default=timezone.now, help_text="Due date or date of transaction")
    completion_date = models.DateField(null=True, blank=True, help_text="Date the transaction was actually completed/paid")
    description = models.CharField(max_length=255)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    recurring_transaction = models.ForeignKey('RecurringTransaction', null=True, blank=True, on_delete=models.SET_NULL, related_name="instances")
    installment_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [ models.Index(fields=['owner', 'date']), models.Index(fields=['status']) ]

    def __str__(self):
        return f"{self.get_type_display()} of {self.value} on {self.date}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
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
            self._process_completion()
        elif status_reverted_from_completed and not is_new:
            self._reverse_completion(old_instance)

    # --- NOVO MÉTODO DELETE CUSTOMIZADO ---
    def delete(self, *args, **kwargs):
        """
        Sobrescreve o método delete para garantir que o saldo da conta seja
        revertido se a transação deletada já estivesse efetivada.
        """
        # Verifica se a transação estava efetivada ANTES de deletar
        was_completed = self.status == self.Status.COMPLETED
        
        # Chama a lógica de reversão de saldo se necessário
        if was_completed:
            # Note que passamos 'self' para o método de reversão, pois ele contém
            # o estado da transação que está sendo deletada.
            self._reverse_completion(self)
        
        # Continua com o processo de exclusão padrão
        return super().delete(*args, **kwargs)

    def _process_completion(self):
        """Aplica o efeito da transação nos saldos das contas."""
        if self.type == self.TransactionType.EXPENSE and self.origin_account:
            self.origin_account.balance -= self.value
            self.origin_account.save(update_fields=['balance'])
        elif self.type == self.TransactionType.INCOME and self.destination_account:
            self.destination_account.balance += self.value
            self.destination_account.save(update_fields=['balance'])
        elif self.type == self.TransactionType.TRANSFER and self.origin_account and self.destination_account:
            self.origin_account.balance -= self.value
            value_to_add = self.converted_value if self.converted_value is not None else self.value
            self.destination_account.balance += value_to_add
            self.origin_account.save(update_fields=['balance'])
            self.destination_account.save(update_fields=['balance'])

    def _reverse_completion(self, old_transaction):
        """Reverte o efeito da transação nos saldos das contas."""
        if old_transaction.type == self.TransactionType.EXPENSE and old_transaction.origin_account:
            old_transaction.origin_account.balance += old_transaction.value
            old_transaction.origin_account.save(update_fields=['balance'])
        elif old_transaction.type == self.TransactionType.INCOME and old_transaction.destination_account:
            old_transaction.destination_account.balance -= old_transaction.value
            old_transaction.destination_account.save(update_fields=['balance'])
        elif old_transaction.type == self.TransactionType.TRANSFER and old_transaction.origin_account and old_transaction.destination_account:
            old_transaction.origin_account.balance += old_transaction.value
            value_to_subtract = old_transaction.converted_value if old_transaction.converted_value is not None else old_transaction.value
            old_transaction.destination_account.balance -= value_to_subtract
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
    start_date = models.DateField()
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    installments_total = models.PositiveIntegerField()
    installments_paid = models.PositiveIntegerField(default=1)
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