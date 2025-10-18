#
# Arquivo: transactions/services.py
#
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from .models import Transaction, RecurringTransaction, Category, Account
import datetime
# Adicione InvalidOperation ao import de decimal
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.http import HttpRequest
from accounts.services import get_conversion_rate, get_exchange_rates

def create_installments(
    *, 
    user,
    total_installments: int,
    start_installment: int,
    start_date: 'datetime.date',
    frequency: str,
    value: 'Decimal',
    description: str,
    transaction_type: str,
    initial_status: str,
    origin_account: Account | None = None,
    destination_account: Account | None = None,
    category: Category | None = None
) -> RecurringTransaction:
    """
    Serviço para criar uma 'receita' de recorrência e gerar todas as suas
    transações de parcela, com a primeira parcela potencialmente já completa.
    """
    recurring_transaction = RecurringTransaction.objects.create(
        owner=user, start_date=start_date, frequency=frequency,
        installments_total=total_installments, installments_paid=start_installment,
        value=value, description=description, transaction_type=transaction_type,
        origin_account=origin_account, destination_account=destination_account, category=category
    )
    
    transactions_to_create = []
    current_date = start_date

    for i in range(start_installment, total_installments + 1):
        installment_desc = f"{description} [{i}/{total_installments}]"
        
        current_status = Transaction.Status.PENDING
        if i == start_installment:
            current_status = initial_status
            
        transactions_to_create.append(Transaction(
            owner=user, recurring_transaction=recurring_transaction,
            installment_number=i, description=installment_desc, value=value,
            date=current_date, 
            status=current_status,
            type=transaction_type,
            origin_account=origin_account, destination_account=destination_account,
            category=category
        ))
        
        # --- LÓGICA DE ATUALIZAÇÃO DE DATA CORRIGIDA ---
        if frequency == RecurringTransaction.Frequency.DAILY:
            current_date += relativedelta(days=1)
        elif frequency == RecurringTransaction.Frequency.WEEKLY:
            current_date += relativedelta(weeks=1)
        elif frequency == RecurringTransaction.Frequency.BIWEEKLY:
            current_date += relativedelta(weeks=2)
        elif frequency == RecurringTransaction.Frequency.MONTHLY:
            current_date += relativedelta(months=1)
        elif frequency == RecurringTransaction.Frequency.SEMESTRAL:
            current_date += relativedelta(months=6)
        elif frequency == RecurringTransaction.Frequency.ANNUALLY:
            current_date += relativedelta(years=1)
        # --- FIM DA CORREÇÃO ---

    # Separa a primeira transação para salvar individualmente (garantir que 'save()' seja chamado)
    first_transaction = transactions_to_create.pop(0)
    first_transaction.save()

    # Cria o resto das transações (pendentes) em massa
    if transactions_to_create:
        Transaction.objects.bulk_create(transactions_to_create)

    return recurring_transaction

def get_type_summary(self, user, preferred_currency_code=None):
        """
        Calcula os totais 'completed' e 'forecasted' para um queryset de
        transações de um tipo específico, convertendo para a moeda preferida.
        """
        completed_total = Decimal('0.0')
        forecasted_total = Decimal('0.0')

        transactions = self.all() # O queryset já deve estar pré-filtrado por tipo e mês

        # Se não há moeda preferida ou nenhuma transação, retorna zero
        if not preferred_currency_code or not transactions:
            return {'completed': completed_total, 'forecasted': forecasted_total}
        
        # Como as transações podem estar em moedas diferentes, precisamos iterar.
        for tx in transactions:
            value = tx.value
            
            origin_currency = None
            if tx.origin_account:
                origin_currency = tx.origin_account.country.currency_code
            elif tx.destination_account: # Para receitas puras
                origin_currency = tx.destination_account.country.currency_code
            
            converted_value = value
            if origin_currency and origin_currency != preferred_currency_code:
                try:
                    # Importa localmente para evitar dependências no topo
                    from core.services import get_conversion_rate
                    rate = get_conversion_rate(origin_currency, preferred_currency_code)
                    converted_value = value * rate
                except Exception:
                    continue # Pula a transação se a conversão falhar

            if tx.status in [Transaction.Status.PENDING, Transaction.Status.OVERDUE, Transaction.Status.COMPLETED]:
                forecasted_total += converted_value
            if tx.status == Transaction.Status.COMPLETED:
                completed_total += converted_value
                
        return {'completed': completed_total, 'forecasted': forecasted_total}


# --- NOVO SERVIÇO DE CRIAÇÃO DE TRANSFERÊNCIA ---
def create_transfer(*, user, request: HttpRequest, form_data: dict) -> Transaction:
    """
    Serviço para criar uma transação de transferência.
    Lida com a conversão de moeda se as contas forem diferentes.
    
    Pode levantar uma Exception se a conversão de moeda falhar.
    Retorna a instância de Transaction criada.
    """
    origin_account = form_data.get('origin_account')
    destination_account = form_data.get('destination_account')
    
    # Prepara o objeto de transação, mas não salva ainda (commit=False)
    transaction = Transaction(
        owner=user,
        type=Transaction.TransactionType.TRANSFER,
        value=form_data.get('value'),
        date=form_data.get('date'),
        description=form_data.get('description'),
        status=form_data.get('status'),
        origin_account=origin_account,
        destination_account=destination_account,
    )
    
    # Lógica de conversão
    origin_currency = origin_account.country.currency_code
    dest_currency = destination_account.country.currency_code

    if origin_currency != dest_currency:
        try:
            rate = get_conversion_rate(origin_currency, dest_currency)
            converted_value = transaction.value * rate
            
            # Adiciona os dados da conversão ao objeto
            transaction.exchange_rate = rate
            transaction.converted_value = converted_value
            
            messages.info(
                request, 
                f"Exchange rate applied: 1 {origin_currency} = {rate:.4f} {dest_currency}. "
                f"Destination will receive {converted_value:.2f} {dest_currency}."
            )

        except (Exception, InvalidOperation) as e:
            # Se a conversão falhar, lança uma exceção que a view pode capturar
            raise Exception(f"Could not perform currency conversion: {e}")

    # Salva o objeto Transaction no banco de dados
    transaction.save()
    
    return transaction