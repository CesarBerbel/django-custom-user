#
# Arquivo: transactions/querysets.py
# (O método get_balance_until, completo e verificado)
#
# Garanta que todos estes imports estejam no topo do seu arquivo:
from decimal import Decimal, InvalidOperation
from django.db import models
from django.db.models import Sum, Q, F, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone


class TransactionQuerySet(models.QuerySet):
    
    def get_balance_until(self, account, end_date, is_forecasted=False):
        """
        Calcula o saldo cumulativo de UMA conta específica até uma determinada data,
        usando o valor correto (convertido ou original) para cada movimentação.
        """
        # Importação local para evitar importação circular com o models.py
        from .models import Transaction

        # 1. Define quais status e qual campo de data usar
        if is_forecasted:
            # Para projeções, consideramos todas as transações (completas, pendentes, vencidas)
            # usando a data de vencimento/agendamento ('date') como referência.
            relevant_statuses_q = Q(status__in=[
                Transaction.Status.COMPLETED,
                Transaction.Status.PENDING,
                Transaction.Status.OVERDUE
            ])
            # Aqui, para projeção, consideramos as transações que já deveriam ter ocorrido.
            date_filter_q = Q(date__lte=end_date)
            # E as que foram completadas, independente da data de agendamento.
            date_filter_q |= Q(status=Transaction.Status.COMPLETED, completion_date__lte=end_date)
            
        else:
            # Para o saldo real, consideramos APENAS transações completadas,
            # usando a data de efetivação ('completion_date') como referência.
            relevant_statuses_q = Q(status=Transaction.Status.COMPLETED)
            date_filter_q = Q(completion_date__lte=end_date)

        # 2. Expressão condicional para somar o valor correto para ENTRADAS na conta.
        # Se for uma transferência recebida e tiver um valor convertido, use-o.
        # Caso contrário, use o 'value' padrão.
        income_value_expression = Case(
            When(type=Transaction.TransactionType.TRANSFER, converted_value__isnull=False, then=F('converted_value')),
            default=F('value'),
            output_field=DecimalField()
        )
        
        # 3. Agregação de ENTRADAS (incomes) para esta conta
        incomes = self.filter(
            destination_account=account
        ).filter(
            relevant_statuses_q,
            date_filter_q
        ).aggregate(
            total=Coalesce(Sum(income_value_expression), Decimal('0.0'))
        )['total']
        
        # 4. Agregação de SAÍDAS (expenses) para esta conta
        # Para saídas (despesas e transferências), o valor é sempre 'value'.
        expenses = self.filter(
            origin_account=account
        ).filter(
            relevant_statuses_q,
            date_filter_q
        ).aggregate(
            total=Coalesce(Sum('value'), Decimal('0.0'), output_field=DecimalField())
        )['total']

        # 5. Retorna o saldo final calculado
        return account.initial_balance + incomes - expenses
    
    def get_type_summary(self, user, preferred_currency_code=None):
        """
        Calcula os totais 'completed' e 'forecasted' para um queryset
        de transações, convertendo-os para a moeda preferida.
        """
        completed_total = Decimal('0.0')
        forecasted_total = Decimal('0.0')

        from .models import Transaction

        # Se não há moeda preferida, retorna zero para evitar conversões
        if not preferred_currency_code:
            return {'completed': completed_total, 'forecasted': forecasted_total}
        
        # O self aqui é o queryset já pré-filtrado pela view (por tipo e mês)
        for tx in self:
            value = tx.value
            
            origin_currency = None
            if tx.origin_account:
                origin_currency = tx.origin_account.country.currency_code
            elif tx.destination_account: # Para receitas puras
                origin_currency = tx.destination_account.country.currency_code
            else:
                continue # Pula transações sem conta associada

            converted_value = value
            if origin_currency and origin_currency != preferred_currency_code:
                try:
                    from accounts.services import get_conversion_rate
                    rate = get_conversion_rate(origin_currency, preferred_currency_code)
                    converted_value = value * rate
                except (Exception, InvalidOperation):
                    # Pula a transação se a conversão falhar, para não corromper o total
                    continue

            # A transação está sendo contada duas vezes. Vamos refatorar.
            # O laço itera sobre transações já filtradas por TIPO e MÊS.

            if tx.status in [Transaction.Status.PENDING, Transaction.Status.OVERDUE, Transaction.Status.COMPLETED]:
                forecasted_total += converted_value
            if tx.status == Transaction.Status.COMPLETED:
                completed_total += converted_value
                
        return {'completed': completed_total, 'forecasted': forecasted_total}    

    def mark_overdue(self) -> int:
        """
        Encontra todas as transações 'PENDING' cuja data de vencimento já passou
        e atualiza seu status para 'OVERDUE'.
        
        Retorna a quantidade de transações que foram atualizadas.
        """
        today = timezone.now().date()
        
        # Importação local para evitar importação circular com o models.py
        from .models import Transaction

        # O self aqui é o queryset base (ex: Transaction.objects)
        # Filtra as transações que estão pendentes e com data no passado
        transactions_to_update = self.filter(
            status=Transaction.Status.PENDING,
            date__lt=today
        )
        
        # Usa .update() para uma única e eficiente query no banco de dados
        # e retorna o número de linhas afetadas.
        count = transactions_to_update.update(status=Transaction.Status.OVERDUE)
        
        return count    