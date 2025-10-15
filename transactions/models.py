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
        # Para evitar dupla contagem, primeiro salvamos o objeto para obter um PK
        # e rastrear o estado anterior do 'status'
        is_new = self._state.adding
        
        if not is_new:
            old_transaction = Transaction.objects.get(pk=self.pk)
            old_status = old_transaction.status
        else:
            old_status = None
            
        super().save(*args, **kwargs) # Salva a transação primeiro
        
        # A mágica acontece aqui: ajusta o saldo apenas se o status MUDOU para COMPLETED
        if self.status == self.Status.COMPLETED and old_status != self.Status.COMPLETED:
            self.completion_date = timezone.now().date() # Define a data de efetivação
            self._process_completion()
        
        # Se uma transação que estava COMPLETED for revertida (ex: para PENDING)
        elif old_status == self.Status.COMPLETED and self.status != self.Status.COMPLETED:
            self.completion_date = None # Limpa a data de efetivação
            self._reverse_completion(old_transaction)

        super().save(*args, **kwargs) # Salva novamente para garantir que as mudanças sejam persistidas

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