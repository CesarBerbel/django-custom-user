from django.core.management.base import BaseCommand
from django.utils import timezone
from transactions.models import Transaction

class Command(BaseCommand):
    """
    Comando Django para encontrar transações pendentes e com data vencida,
    e atualizar seu status para "Vencida" (Overdue).
    """
    help = 'Updates the status of overdue pending transactions to "Overdue"'

    def handle(self, *args, **options):
        """
        A lógica principal do comando.
        """
        # Pega a data de hoje. É importante usar timezone.now().date() para
        # respeitar as configurações de fuso horário do projeto.
        today = timezone.now().date()

        self.stdout.write(self.style.NOTICE(f"Checking for overdue transactions as of {today}..."))

        # Constrói a query para encontrar as transações que correspondem aos critérios:
        # 1. O status é 'PENDING'
        # 2. A data da transação é anterior a hoje (date__lt)
        overdue_transactions = Transaction.objects.filter(
            status=Transaction.Status.PENDING,
            date__lt=today
        )
        
        # Conta quantas transações foram encontradas
        count = overdue_transactions.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No overdue transactions found. Everything is up to date!"))
            return

        self.stdout.write(self.style.WARNING(f"Found {count} overdue transaction(s). Updating status..."))

        # Usa o método .update() para atualizar todas as transações encontradas
        # em uma única e eficiente query de banco de dados.
        # Isso é muito mais rápido do que iterar e salvar cada uma.
        updated_count = overdue_transactions.update(status=Transaction.Status.OVERDUE)

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} transaction(s) to 'Overdue' status."))