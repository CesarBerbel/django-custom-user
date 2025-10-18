#
# Arquivo: accounts/querysets.py
#
from django.db import models

class AccountQuerySet(models.QuerySet):
    def with_calculated_balances(self, user, end_date, is_forecasted=False):
        """
        Para cada conta no queryset, calcula seu saldo (real ou projetado)
        até uma data específica e o anexa ao objeto como 'calculated_balance'.
        """
        # Importação local para evitar importação circular
        from transactions.models import Transaction

        # Converte para uma lista para que possamos modificar os objetos
        accounts_list = list(self.select_related('country'))

        for account in accounts_list:
            # Usa o poderoso método que já criamos e validamos!
            calculated_balance = Transaction.objects.filter(owner=user).get_balance_until(
                account=account,
                end_date=end_date,
                is_forecasted=is_forecasted
            )
            # Anexa o saldo calculado ao objeto em memória
            account.calculated_balance = calculated_balance

        return accounts_list