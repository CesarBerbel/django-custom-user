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
        self.stdout.write(self.style.NOTICE("Checking for overdue transactions..."))
        
        # --- LÓGICA DE NEGÓCIO DELEGADA ---
        # Chama o nosso novo método do manager
        updated_count = Transaction.objects.mark_overdue()
        # --- FIM DA DELEGAÇÃO ---

        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS("No overdue transactions found."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {updated_count} transaction(s) to 'Overdue'."
                )
            )