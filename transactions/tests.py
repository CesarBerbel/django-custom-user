# #
# # Arquivo: transactions/tests.py
# #
import datetime
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse, reverse_lazy
from django.contrib.auth import get_user_model
from accounts.models import Account, Bank, AccountType, Country
from .models import Transaction, Category, RecurringTransaction
from .forms import TransferForm
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.management import call_command
from unittest.mock import patch, MagicMock
from .services import create_transfer

class TransactionModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='test@user.com', password='foo')
        self.bank = Bank.objects.create(name='Bank 1')
        self.type = AccountType.objects.create(name='Checking')
        self.country = Country.objects.create(code='BR', currency_code='BRL')
        
        # Conta com saldo inicial de 1000
        self.acc1 = Account.objects.create(
            owner=self.user, bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal('1000.00')
        )
        # Conta com saldo inicial de 0
        self.acc2 = Account.objects.create(
            owner=self.user, bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal('0.00')
        )

        self.cat_income = Category.objects.create(owner=self.user, name='Salary', type=Category.TransactionType.INCOME)
        self.cat_expense = Category.objects.create(owner=self.user, name='Food', type=Category.TransactionType.EXPENSE)

#     # --- Testes de Lógica de Atualização de Saldo (MUITO IMPORTANTES) ---

    def test_expense_completion_deducts_balance(self):
        """Creates a completed expense and checks if origin balance decreases."""
        tx = Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.EXPENSE,
            origin_account=self.acc1, category=self.cat_expense,
            value=Decimal('100.00'), description='Test Expense',
            status=Transaction.Status.COMPLETED
        )
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('900.00')) # 1000 - 100

    def test_income_completion_adds_balance(self):
        """Creates a completed income and checks if destination balance increases."""
        tx = Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.INCOME,
            destination_account=self.acc1, category=self.cat_income,
            value=Decimal('500.00'), description='Test Income',
            status=Transaction.Status.COMPLETED
        )
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('1500.00')) # 1000 + 500

    def test_transfer_completion_moves_balance(self):
        """Creates a completed transfer and checks both accounts."""
        tx = Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.TRANSFER,
            origin_account=self.acc1, destination_account=self.acc2,
            value=Decimal('300.00'), description='Test Transfer',
            status=Transaction.Status.COMPLETED
        )
        self.acc1.refresh_from_db()
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('700.00')) # 1000 - 300
        self.assertEqual(self.acc2.balance, Decimal('300.00'))  # 0 + 300

    def test_pending_transaction_does_not_change_balance(self):
        """Pending transactions should have NO effect on balance."""
        Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.EXPENSE,
            origin_account=self.acc1, category=self.cat_expense,
            value=Decimal('999.00'), description='Pending',
            status=Transaction.Status.PENDING
        )
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('1000.00')) # No change

    def test_updating_status_to_completed_updates_balance(self):
        """Create as pending, then update to completed. Balance should change only then."""
        tx = Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.INCOME,
            destination_account=self.acc1, category=self.cat_income,
            value=Decimal('50.00'), status=Transaction.Status.PENDING
        )
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('1000.00')) # Still initial

        # Now, update to COMPLETED
        tx.status = Transaction.Status.COMPLETED
        tx.save()

        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('1050.00')) # Updated

    def test_reverting_completed_transaction_reverts_balance(self):
        """Changing status from COMPLETED to PENDING should undo the balance change."""
        # Start with a completed transaction
        tx = Transaction.objects.create(
            owner=self.user, type=Transaction.TransactionType.EXPENSE,
            origin_account=self.acc1, category=self.cat_expense,
            value=Decimal('100.00'), status=Transaction.Status.COMPLETED
        )
        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('900.00')) # Deducted

        # Revert to PENDING (e.g., marked by mistake)
        tx.status = Transaction.Status.PENDING
        tx.save()

        self.acc1.refresh_from_db()
        self.assertEqual(self.acc1.balance, Decimal('1000.00')) # Restored

class TransactionViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='test@user.com', password='foo')
        self.client.force_login(self.user)
        
        # Setup data
        self.bank = Bank.objects.create(name='B1')
        self.type = AccountType.objects.create(name='T1')
        self.country = Country.objects.create(code='US', currency_code='USD')
        self.acc = Account.objects.create(owner=self.user, bank=self.bank, type=self.type, country=self.country, initial_balance=Decimal('0'))
        self.cat = Category.objects.create(owner=self.user, name='Cat1', type=Category.TransactionType.EXPENSE)

    def test_create_expense_view(self):
        url = reverse('transactions:expense_create')
        data = {
            'value': '50.00',
            'date': '2023-01-01',
            'description': 'Test',
            'status': 'PENDING',
            'category': self.cat.id,
            'origin_account': self.acc.id,
        }
        response = self.client.post(url, data)
        
        # Check redirection to expense list
        self.assertRedirects(response, reverse('transactions:expense_list'))
        
        # Check object creation
        tx = Transaction.objects.latest('id')
        self.assertEqual(tx.value, Decimal('50.00'))
        self.assertEqual(tx.type, Transaction.TransactionType.EXPENSE)
        self.assertEqual(tx.owner, self.user)

    def test_data_isolation_in_forms(self):
        """Forms should only show accounts/categories belonging to the logged-in user."""
        # Create another user and their data
        user2 = get_user_model().objects.create_user(email='user2@test.com', password='foo')
        acc2 = Account.objects.create(owner=user2, bank=self.bank, type=self.type, country=self.country, initial_balance=Decimal('0'))
        cat2 = Category.objects.create(owner=user2, name='Cat2', type=Category.TransactionType.EXPENSE)

        # Get form for logged-in user (self.user)
        response = self.client.get(reverse('transactions:expense_create'))
        
        # Form fields should only contain self.user's choices
        origin_accounts = list(response.context['form'].fields['origin_account'].queryset)
        categories = list(response.context['form'].fields['category'].queryset)
        
        self.assertIn(self.acc, origin_accounts)
        self.assertNotIn(acc2, origin_accounts) # user2's account not shown
        
        self.assertIn(self.cat, categories)
        self.assertNotIn(cat2, categories) # user2's category not shown

    def test_transfer_form_validates_accounts(self):
        """Transfer form should not allow same origin and destination."""
        form = TransferForm(
            user=self.user,
            data={
                'value': '10', 'date': '2023-01-01', 'description': 'Invalid', 'status': 'PENDING',
                'origin_account': self.acc.id,
                'destination_account': self.acc.id # Same account!
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Origin and destination accounts cannot be the same.", form.non_field_errors())

class CategoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='u@test.com', password='foo')
        self.client.force_login(self.user)

    def test_create_category(self):
        url = reverse('transactions:category_create')
        data = {'name': 'food', 'type': 'EXPENSE', 'color': '#000000'}
        response = self.client.post(url, data)
        
        self.assertRedirects(response, reverse('transactions:category_list'))
        cat = Category.objects.latest('id')
        # Name should be capitalized by form.clean_name()
        self.assertEqual(cat.name, 'Food') 
        self.assertEqual(cat.owner, self.user)

    def test_unique_name_per_type_per_user(self):
        # Create first category
        Category.objects.create(owner=self.user, name='Food', type='EXPENSE')
        
        # Try creating the same one via form
        url = reverse('transactions:category_create')
        data = {'name': 'food', 'type': 'EXPENSE'} # 'food' will be capfirst'ed to 'Food'
        response = self.client.post(url, data)
        
        # Should fail validation
        self.assertEqual(response.status_code, 200) # Form re-rendered
        self.assertContains(response, "already exists")

class CategoryManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user1 = User.objects.create_user(email="user1_cat@test.com", password="pw")
        self.user2 = User.objects.create_user(email="user2_cat@test.com", password="pw")
        
        self.category1 = Category.objects.create(
            owner=self.user1, 
            name="Groceries", 
            type=Category.TransactionType.EXPENSE
        )

    def test_authentication_required(self):
        """Test that all category views require a logged-in user."""
        urls = [
            reverse("transactions:category_list"),
            reverse("transactions:category_create"),
            reverse("transactions:category_edit", args=[self.category1.pk]),
            reverse("transactions:category_delete", args=[self.category1.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('users:login')}?next={url}")

    def test_list_shows_only_owned_categories(self):
        Category.objects.create(owner=self.user2, name="Salary", type=Category.TransactionType.INCOME)
        self.client.force_login(self.user1)
        response = self.client.get(reverse("transactions:category_list"))
        
        self.assertContains(response, "Groceries")
        self.assertNotContains(response, "Salary")

    def test_create_category(self):
        self.client.force_login(self.user1)
        url = reverse("transactions:category_create")
        data = {"name": "Transport", "type": Category.TransactionType.EXPENSE}
        self.client.post(url, data)
        
        new_cat = Category.objects.get(name="Transport")
        self.assertEqual(new_cat.owner, self.user1)

    def test_update_owned_category(self):
        self.client.force_login(self.user1)
        url = reverse("transactions:category_edit", args=[self.category1.pk])
        self.client.post(url, {"name": "Food", "type": self.category1.type})
        self.category1.refresh_from_db()
        self.assertEqual(self.category1.name, "Food")

    def test_user_cannot_edit_another_users_category(self):
        self.client.force_login(self.user2) # user2 logged in
        url = reverse("transactions:category_edit", args=[self.category1.pk]) # tries to edit user1's category
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404) # Should not find it due to queryset filtering

    def test_delete_owned_category(self):
        self.client.force_login(self.user1)
        url = reverse("transactions:category_delete", args=[self.category1.pk])
        self.client.post(url)
        self.assertFalse(Category.objects.filter(pk=self.category1.pk).exists())        

class TransactionModelLogicTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="txlogic@test.com", password="pw")
        country = Country.objects.create(code="XX", currency_code="XXX")
        bank = Bank.objects.create(name="Bank Test")
        acc_type = AccountType.objects.create(name="Current")
        self.account = Account.objects.create(owner=self.user, country=country, bank=bank, type=acc_type, initial_balance=1000)

    def test_completion_date_is_set_on_save(self):
        """Testa se a completion_date é definida quando o status muda para COMPLETED."""
        tx = Transaction.objects.create(
            owner=self.user,
            description="Test Pending",
            value=100,
            origin_account=self.account,
            type=Transaction.TransactionType.EXPENSE,
            status=Transaction.Status.PENDING,
            date=timezone.now().date()
        )
        self.assertIsNone(tx.completion_date)

        # Efetiva a transação
        tx.status = Transaction.Status.COMPLETED
        tx.save()
        tx.refresh_from_db()

        self.assertIsNotNone(tx.completion_date)
        self.assertEqual(tx.completion_date, timezone.now().date())
        
        # Testa se o saldo da conta é atualizado
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal('900.00'))

    def test_completion_date_is_cleared_on_revert(self):
        """Testa se a completion_date é limpa se o status é revertido."""
        tx = Transaction.objects.create(
            owner=self.user,
            description="Test Completed",
            value=50,
            origin_account=self.account,
            type=Transaction.TransactionType.EXPENSE,
            status=Transaction.Status.COMPLETED
        )
        tx.refresh_from_db() # Para garantir que save() foi chamado
        self.assertIsNotNone(tx.completion_date)

        # Reverte o status
        tx.status = Transaction.Status.PENDING
        tx.save()
        tx.refresh_from_db()

        self.assertIsNone(tx.completion_date)
        
        # Testa se o saldo da conta foi revertido
        self.account.refresh_from_db()

        self.assertEqual(self.account.balance, Decimal('1000.00'))

class ManagementCommandsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="cmd@test.com", password="pw")

    def test_update_overdue_command(self):
        """Testa se o comando 'update_overdue' funciona corretamente."""
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        
        # Transação que DEVE ser atualizada
        tx_overdue = Transaction.objects.create(
            owner=self.user, value=10, type=Transaction.TransactionType.EXPENSE,
            date=yesterday, status=Transaction.Status.PENDING
        )
        
        # Transação que NÃO deve ser atualizada (data futura)
        tx_future = Transaction.objects.create(
            owner=self.user, value=10, type=Transaction.TransactionType.EXPENSE,
            date=timezone.now().date() + datetime.timedelta(days=1),
            status=Transaction.Status.PENDING
        )
        
        # Transação que NÃO deve ser atualizada (status diferente)
        tx_completed = Transaction.objects.create(
            owner=self.user, value=10, type=Transaction.TransactionType.EXPENSE,
            date=yesterday, status=Transaction.Status.COMPLETED
        )
        
        # Executa o comando
        call_command('update_overdue')

        tx_overdue.refresh_from_db()
        tx_future.refresh_from_db()
        tx_completed.refresh_from_db()

        self.assertEqual(tx_overdue.status, Transaction.Status.OVERDUE)
        self.assertEqual(tx_future.status, Transaction.Status.PENDING)
        self.assertEqual(tx_completed.status, Transaction.Status.COMPLETED)        

class TransactionListViewLogicTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="listlogic@test.com", password="pw")
        self.client.force_login(self.user)
        country = Country.objects.create(code="LL", currency_code="YYY")
        bank = Bank.objects.create(name="List Bank")
        acc_type = AccountType.objects.create(name="Checking")
        self.account = Account.objects.create(
            owner=self.user, country=country, bank=bank, type=acc_type, 
            initial_balance=1000
        )
        self.exp_cat = Category.objects.create(owner=self.user, name="Services", type=Category.TransactionType.EXPENSE)
        
        # Define datas de referência
        last_month = timezone.now().date().replace(day=1) - datetime.timedelta(days=1)
        this_month = timezone.now().date().replace(day=1)
        next_month = this_month + relativedelta(months=1)

        # Cenário de teste:
        # 1. Transação do mês passado, efetivada no mês passado (impacta o saldo inicial)
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, category=self.exp_cat,
            value=100, type=Transaction.TransactionType.EXPENSE,
            date=last_month, completion_date=last_month, status=Transaction.Status.COMPLETED,
            description="Last Month Bill"
        )
        # 2. Transação deste mês, efetivada neste mês
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, category=self.exp_cat,
            value=50, type=Transaction.TransactionType.EXPENSE,
            date=this_month, completion_date=this_month, status=Transaction.Status.COMPLETED,
            description="This Month Completed"
        )
        # 3. Transação deste mês, pendente (deve contar no previsto)
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, category=self.exp_cat,
            value=25, type=Transaction.TransactionType.EXPENSE,
            date=this_month, status=Transaction.Status.PENDING,
            description="This Month Pending"
        )
        # 4. Transação do mês que vem, pendente (só deve aparecer na projeção)
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, category=self.exp_cat,
            value=200, type=Transaction.TransactionType.EXPENSE,
            date=next_month, status=Transaction.Status.PENDING,
            description="Next Month Forecast"
        )

    def test_account_statement_current_month(self):
        """Testa o extrato da conta para o mês corrente."""
        url = reverse("transactions:list_by_account", args=[self.account.pk])
        response = self.client.get(url)
        summary = response.context['summary']

        # Saldo inicial = 1000 (inicial) - 100 (conta do mês passado) = 900
        self.assertEqual(summary['starting_balance'], Decimal('900.00'))
        
        # Saldo atual = 900 - 50 (efetivada este mês) = 850
        self.assertEqual(summary['current_balance'], Decimal('850.00'))
        
        # Saldo previsto = 900 - 50 (efetivada) - 25 (pendente) = 825
        self.assertEqual(summary['forecasted_balance'], Decimal('825.00'))

    def test_account_statement_future_month(self):
        """Testa a projeção do extrato da conta para um mês futuro."""
        next_month = timezone.now().date().replace(day=1) + relativedelta(months=1)
        url = reverse("transactions:list_by_account_specific", args=[self.account.pk, next_month.year, next_month.month])
        response = self.client.get(url)
        summary = response.context['summary']
        
        # Saldo inicial do mês futuro = Saldo PREVISTO do mês corrente = 825
        self.assertEqual(summary['starting_balance'], Decimal('825.00'))
        
        # Saldo atual do mês futuro (não há efetivadas) = saldo inicial = 825
        self.assertEqual(summary['current_balance'], Decimal('825.00'))

        # Saldo previsto = 825 - 200 (conta pendente do mês futuro) = 625
        self.assertEqual(summary['forecasted_balance'], Decimal('625.00'))        



# NOVA CLASSE DE TESTE PARA TRANSAÇÕES PARCELADAS
class InstallmentCreationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="installment@test.com", password="pw")
        self.client.force_login(self.user)
        
        country = Country.objects.create(code="IT", currency_code="EUR")
        bank = Bank.objects.create(name="Installment Bank")
        acc_type = AccountType.objects.create(name="Credit Card")
        self.account = Account.objects.create(
            owner=self.user, country=country, bank=bank, type=acc_type, initial_balance=0
        )
        self.category = Category.objects.create(
            owner=self.user, name="Electronics", type=Category.TransactionType.EXPENSE
        )
        
        # A URL agora está em um formulário integrado, não em uma página separada.
        # Vamos testar a criação de despesas.
        self.create_url = reverse("transactions:expense_create")

    def test_create_monthly_installments(self):
        """Testa se a criação de 12 parcelas mensais funciona."""
        start_date = timezone.now().date()
        post_data = {
            'description': 'New Laptop',
            'value': 100.00,
            'date': start_date.strftime('%Y-%m-%d'),
            'origin_account': self.account.pk,
            'category': self.category.pk,
            'status': Transaction.Status.PENDING,
            
            # Campos de parcelamento
            'is_installment': 'on', # Checkbox marcado
            'installments_total': 12,
            'installments_paid': 1, 
            'frequency': RecurringTransaction.Frequency.MONTHLY,
        }
        
        response = self.client.post(self.create_url, post_data, follow=True)
        
        # Verifica se o redirecionamento foi para a lista correta
        self.assertRedirects(response, reverse("transactions:expense_list"))
        
        # 1. Verifica se a "receita" foi criada
        self.assertEqual(RecurringTransaction.objects.count(), 1)
        rec_tx = RecurringTransaction.objects.first()
        self.assertEqual(rec_tx.owner, self.user)
        self.assertEqual(rec_tx.installments_total, 12)

        # 2. Verifica se as 12 transações foram criadas
        self.assertEqual(Transaction.objects.count(), 12)
        
        # 3. Verifica os detalhes da primeira e da última parcela
        first_tx = Transaction.objects.order_by('date').first()
        last_tx = Transaction.objects.order_by('date').last()
        
        self.assertEqual(first_tx.installment_number, 1)
        self.assertEqual(first_tx.description, "New Laptop [1/12]")
        self.assertEqual(first_tx.date, start_date)
        self.assertEqual(first_tx.status, Transaction.Status.PENDING)
        self.assertEqual(first_tx.value, Decimal('100.00'))

        self.assertEqual(last_tx.installment_number, 12)
        self.assertEqual(last_tx.description, "New Laptop [12/12]")
        # A data da última parcela deve ser 11 meses após a primeira
        expected_last_date = start_date + relativedelta(months=11)
        self.assertEqual(last_tx.date, expected_last_date)
        
    def test_create_weekly_installments(self):
        """Testa se a criação de 4 parcelas semanais funciona."""
        start_date = timezone.now().date()
        post_data = {
            'description': 'Groceries',
            'value': 50.00,
            'date': start_date.strftime('%Y-%m-%d'),
            'origin_account': self.account.pk,
            'category': self.category.pk,
            'status': Transaction.Status.PENDING,
            'is_installment': 'on',
            'installments_total': 4,
            'installments_paid': 1,
            'frequency': RecurringTransaction.Frequency.WEEKLY,
        }

        self.client.post(self.create_url, post_data)
        
        self.assertEqual(Transaction.objects.count(), 4)
        
        first_tx = Transaction.objects.order_by('date').first()
        last_tx = Transaction.objects.order_by('date').last()
        
        # A última parcela deve ser 3 semanas após a primeira
        expected_last_date = start_date + relativedelta(weeks=3)
        self.assertEqual(last_tx.date, expected_last_date)

    def test_single_transaction_is_created_if_not_installment(self):
        """Testa se apenas uma transação é criada se o checkbox não for marcado."""
        post_data = {
            'description': 'Single Coffee',
            'value': 5.00,
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'origin_account': self.account.pk,
            'category': self.category.pk,
            'status': Transaction.Status.PENDING,
            # 'is_installment': 'off' ou ausente
        }
        
        self.client.post(self.create_url, post_data)
        
        # Apenas UMA transação deve existir
        self.assertEqual(Transaction.objects.count(), 1)
        
        # NENHUMA transação recorrente deve ser criada
        self.assertEqual(RecurringTransaction.objects.count(), 0)

        tx = Transaction.objects.first()
        self.assertIsNone(tx.recurring_transaction)
        self.assertIsNone(tx.installment_number)        

class TransactionModelMethodTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="service_test@email.com", password="pw")
        country_us = Country.objects.create(code="US", currency_code="USD")
        bank = Bank.objects.create(name="Service Bank")
        acc_type = AccountType.objects.create(name="Standard")
        self.account = Account.objects.create(owner=self.user, bank=bank, country=country_us, type=acc_type, initial_balance=1000)

    def test_complete_method_changes_status_and_balance(self):
        """Testa se o método transaction.complete() funciona."""
        initial_balance = self.account.balance
        tx = Transaction.objects.create(
            owner=self.user, origin_account=self.account,
            value=100, type=Transaction.TransactionType.EXPENSE,
            status=Transaction.Status.PENDING
        )

        success = tx.complete()
        tx.refresh_from_db()
        self.account.refresh_from_db()

        self.assertTrue(success)
        self.assertEqual(tx.status, Transaction.Status.COMPLETED)
        self.assertIsNotNone(tx.completion_date)
        self.assertEqual(self.account.balance, initial_balance - 100)

    def test_delete_completed_transaction_reverts_balance(self):
        """Testa se deletar uma transação completada reverte o saldo da conta."""
        initial_balance = self.account.balance
        tx = Transaction.objects.create(
            owner=self.user, origin_account=self.account,
            value=50, type=Transaction.TransactionType.EXPENSE,
            status=Transaction.Status.COMPLETED
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, initial_balance - 50)

        tx.delete()

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, initial_balance)


class TransactionServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="service_test@email.com", password="pw")
        country_us = Country.objects.create(code="US", currency_code="USD")
        country_pt = Country.objects.create(code="PT", currency_code="EUR")
        bank = Bank.objects.create(name="Service Bank")
        acc_type = AccountType.objects.create(name="Standard")
        self.account_usd = Account.objects.create(owner=self.user, bank=bank, country=country_us, type=acc_type, initial_balance=1000)
        self.account_eur = Account.objects.create(owner=self.user, bank=bank, country=country_pt, type=acc_type, initial_balance=1000)

    @patch('transactions.services.get_conversion_rate')
    def test_create_multi_currency_transfer(self, mock_get_rate):
        """Testa o serviço create_transfer com moedas diferentes."""
        mock_get_rate.return_value = Decimal('0.92') # 1 USD = 0.92 EUR

        form_data = {
            'value': Decimal('100.00'), 'date': timezone.now().date(),
            'description': 'Test Transfer', 'status': Transaction.Status.PENDING,
            'origin_account': self.account_usd,
            'destination_account': self.account_eur,
        }
        
        # O request é mockado, pois o service espera um objeto request
        mock_request = MagicMock()

        transaction = create_transfer(user=self.user, request=mock_request, form_data=form_data)
        
        self.assertEqual(transaction.value, Decimal('100.00'))
        self.assertEqual(transaction.exchange_rate, Decimal('0.92'))
        self.assertEqual(transaction.converted_value, Decimal('92.00'))

class TransactionQuerySetTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="service_test@email.com", password="pw")
        country_us = Country.objects.create(code="US", currency_code="USD")
        country_pt = Country.objects.create(code="PT", currency_code="EUR")
        bank = Bank.objects.create(name="Service Bank")
        acc_type = AccountType.objects.create(name="Standard")
        self.account = Account.objects.create(owner=self.user, bank=bank, country=country_us, type=acc_type, initial_balance=1000)
        self.end_of_last_month = timezone.now().date().replace(day=1) - relativedelta(days=1)
        # 1. Saldo inicial: 1000
        # 2. Despesa completada no mês passado (-100)
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, status=Transaction.Status.COMPLETED,
            date=self.end_of_last_month, completion_date=self.end_of_last_month,
            value=100, type=Transaction.TransactionType.EXPENSE
        )
        # 3. Despesa pendente no mês passado (-50, deve contar na projeção)
        Transaction.objects.create(
            owner=self.user, origin_account=self.account, status=Transaction.Status.PENDING,
            date=self.end_of_last_month, value=50, type=Transaction.TransactionType.EXPENSE
        )

    def test_get_balance_until_actual(self):
        """Testa o cálculo de saldo real."""
        balance = Transaction.objects.filter(owner=self.user).get_balance_until(
            account=self.account, end_date=self.end_of_last_month, is_forecasted=False
        )
        # Saldo inicial (1000) - Despesa completada (100) = 900
        self.assertEqual(balance, Decimal('900.00'))

    def test_get_balance_until_forecasted(self):
        """Testa o cálculo de saldo projetado."""
        balance = Transaction.objects.filter(owner=self.user).get_balance_until(
            account=self.account, end_date=self.end_of_last_month, is_forecasted=True
        )
        # Saldo inicial (1000) - Despesa completada (100) - Despesa pendente (50) = 850
        self.assertEqual(balance, Decimal('850.00'))        

class TransferCreationFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="transfer@test.com", password="pw")
        self.client.force_login(self.user)

        # Contas com moedas diferentes
        country_br = Country.objects.create(code="BR", currency_code="BRL", currency_symbol="R$")
        country_pt = Country.objects.create(code="PT", currency_code="EUR", currency_symbol="€")
        self.bank = Bank.objects.create(name="Transfer Bank")
        self.acc_type = AccountType.objects.create(name="International")
        self.account_brl = Account.objects.create(owner=self.user, country=country_br, bank=self.bank, type=self.acc_type, initial_balance=5000)
        self.account_eur = Account.objects.create(owner=self.user, country=country_pt, bank=self.bank, type=self.acc_type, initial_balance=5000)
        
        self.create_url = reverse("transactions:transfer_create")
        self.confirm_url = reverse("transactions:transfer_confirm_rate")

    def test_create_simple_transfer_same_currency(self):
        """Testa a criação de uma transferência normal, sem conversão."""
        post_data = {
            'value': 100,
            'description': 'Simple Transfer',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'origin_account': self.account_eur.pk,
            'destination_account': self.account_eur.pk, # Erro de teste intencional, mas o form valida
        }
        # A validação de mesma conta já está no form.clean, então aqui apenas verificamos a criação.
        # Criamos uma nova conta EUR para o teste.
        another_eur_account = Account.objects.create(owner=self.user, country=self.account_eur.country, bank=self.bank, type=self.acc_type, initial_balance=0)
        post_data = {
            'value': 100,
            'description': 'Simple Transfer',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'origin_account': self.account_eur.pk,
            'destination_account': another_eur_account.pk,
            'status': Transaction.Status.PENDING, # <-- CAMPO FALTANTE ADICIONADO
        }

        response = self.client.post(self.create_url, post_data, follow=True)
        self.assertRedirects(response, reverse("transactions:transfer_list"))
        
        self.assertEqual(Transaction.objects.count(), 1)
        tx = Transaction.objects.first()
        self.assertEqual(tx.type, Transaction.TransactionType.TRANSFER)
        self.assertIsNone(tx.exchange_rate) # Garante que não houve conversão
        self.assertIsNone(tx.converted_value)

    @patch('accounts.services.get_conversion_rate')
    def test_multi_currency_transfer_redirects_to_confirmation(self, mock_get_rate):
        """Testa se uma transferência multi-moeda COMPLETED redireciona para a tela de confirmação."""
        mock_get_rate.return_value = Decimal('0.18') # 1 BRL = 0.18 EUR

        post_data = {
            'value': 1000,
            'description': 'BRL to EUR',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'origin_account': self.account_brl.pk,
            'destination_account': self.account_eur.pk,
            'status': Transaction.Status.COMPLETED, # Essencial para acionar o fluxo
        }

        response = self.client.post(self.create_url, post_data)
        
        # 1. Verifica se houve um redirecionamento para a página de confirmação
        self.assertRedirects(response, self.confirm_url)
        
        # 2. Verifica se os dados foram salvos na sessão
        self.assertIn('pending_transfer_data', self.client.session)
        session_data = self.client.session['pending_transfer_data']
        self.assertEqual(session_data['value'], '1000')

    @patch('accounts.services.get_conversion_rate')
    def test_finalize_multi_currency_transfer(self, mock_get_rate):
        """Testa o segundo passo: confirmação e criação final da transferência."""
        mock_get_rate.return_value = Decimal('0.18')

        # Passo 1: Simula o primeiro POST e a configuração da sessão
        session = self.client.session
        session['pending_transfer_data'] = {
            'value': '1000', 'date': '2025-10-20', 'description': 'BRL to EUR',
            'origin_account_id': self.account_brl.pk, 'destination_account_id': self.account_eur.pk
        }
        session.save()
        
        # Passo 2: Simula o POST da página de confirmação
        confirm_post_data = {
            'exchange_rate': '0.185' # Usuário pode ter editado a taxa
        }
        
        response = self.client.post(self.confirm_url, confirm_post_data, follow=True)
        self.assertRedirects(response, reverse("transactions:transfer_list"))
        
        # 3. Verifica se a sessão foi limpa
        self.assertNotIn('pending_transfer_data', self.client.session)
        
        # 4. Verifica se a transação foi criada corretamente com os novos valores
        self.assertEqual(Transaction.objects.count(), 1)
        tx = Transaction.objects.first()
        
        self.assertEqual(tx.owner, self.user)
        self.assertEqual(tx.status, Transaction.Status.COMPLETED)
        self.assertEqual(tx.value, Decimal('1000'))
        self.assertEqual(tx.exchange_rate, Decimal('0.185'))
        self.assertEqual(tx.converted_value, Decimal('185.00')) # 1000 * 0.185

class TransactionEditDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="crud@test.com", password="pw")
        self.client.force_login(self.user)
        
        country = Country.objects.create(code="XX", currency_code="XXX")
        bank = Bank.objects.create(name="CRUD Bank")
        acc_type = AccountType.objects.create(name="Standard")
        self.account1 = Account.objects.create(owner=self.user, country=country, bank=bank, type=acc_type, initial_balance=1000)
        self.account2 = Account.objects.create(owner=self.user, country=country, bank=bank, type=acc_type, initial_balance=2000)
        self.exp_category = Category.objects.create(owner=self.user, name="Bills", type=Category.TransactionType.EXPENSE)
        
        # Cria uma transação para ser manipulada nos testes
        self.tx = Transaction.objects.create(
            owner=self.user,
            origin_account=self.account1,
            category=self.exp_category,
            value=Decimal("50.00"),
            description="Initial Bill",
            type=Transaction.TransactionType.EXPENSE,
            status=Transaction.Status.PENDING,
            date=timezone.now().date()
        )
        self.initial_balance = self.account1.balance

    def test_delete_pending_transaction(self):
        """Testa se deletar uma transação pendente não afeta o saldo."""
        self.tx.delete()
        self.account1.refresh_from_db()
        
        self.assertFalse(Transaction.objects.filter(pk=self.tx.pk).exists())
        self.assertEqual(self.account1.balance, self.initial_balance) # Não deve mudar

    def test_delete_completed_transaction_reverts_balance(self):
        """Testa se deletar uma transação completada reverte o saldo."""
        # Completa a transação primeiro
        self.tx.complete()
        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, self.initial_balance - self.tx.value) # Saldo deve diminuir
        
        # Deleta
        self.tx.delete()
        self.account1.refresh_from_db()
        
        self.assertFalse(Transaction.objects.filter(pk=self.tx.pk).exists())
        self.assertEqual(self.account1.balance, self.initial_balance) # Saldo deve voltar ao normal

    def test_update_single_transaction_value(self):
        """Testa se editar o valor de uma transação única (já completada) corrige o saldo."""
        self.tx.complete() # Completa a despesa de 50, saldo da conta = 950
        self.account1.refresh_from_db()
        
        url = reverse('transactions:edit', args=[self.tx.pk])
        
        # Simula a edição: muda o valor de 50 para 75
        post_data = {
            'value': '75.00',
            'description': self.tx.description,
            'date': self.tx.date.strftime('%Y-%m-%d'),
            'origin_account': self.account1.pk,
            'category': self.exp_category.pk,
            'status': Transaction.Status.COMPLETED
        }
        
        self.client.post(url, post_data)
        self.account1.refresh_from_db()

        # O saldo final deve ser: 1000 - 75 = 925
        expected_balance = self.initial_balance - Decimal("75.00")
        self.assertEqual(self.account1.balance, expected_balance)

    def test_update_transaction_from_pending_to_completed(self):
        """Testa se editar uma transação e mudar o status para COMPLETED atualiza o saldo."""
        url = reverse('transactions:edit', args=[self.tx.pk])
        
        post_data = {
            'value': self.tx.value,
            'description': 'Updated Bill',
            'date': self.tx.date.strftime('%Y-%m-%d'),
            'origin_account': self.account1.pk,
            'category': self.exp_category.pk,
            'status': Transaction.Status.COMPLETED # Muda o status
        }

        self.client.post(url, post_data)
        self.account1.refresh_from_db()
        
        expected_balance = self.initial_balance - self.tx.value
        self.assertEqual(self.account1.balance, expected_balance)

    def test_update_transaction_change_account(self):
        """Testa se editar uma transação e mudar a conta corrige os saldos de AMBAS as contas."""
        self.tx.complete() # Completa a despesa de 50 na conta 1. Saldo C1=950, C2=2000
        self.account1.refresh_from_db()
        account2_initial_balance = self.account2.balance
        
        url = reverse('transactions:edit', args=[self.tx.pk])

        # Edita a transação, movendo-a da conta 1 para a conta 2
        post_data = {
            'value': self.tx.value,
            'description': self.tx.description,
            'date': self.tx.date.strftime('%Y-%m-%d'),
            'origin_account': self.account2.pk, # <--- MUDA A CONTA
            'category': self.exp_category.pk,
            'status': Transaction.Status.COMPLETED
        }
        
        self.client.post(url, post_data)
        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        
        # Saldo da conta 1 deve voltar ao original (reversão)
        self.assertEqual(self.account1.balance, self.initial_balance)
        
        # Saldo da conta 2 deve ser debitado (aplicação)
        self.assertEqual(self.account2.balance, account2_initial_balance - self.tx.value)

    def test_cannot_edit_recurring_transaction(self):
        """Testa se a edição de uma transação recorrente é bloqueada."""
        rec_tx = RecurringTransaction.objects.create(
            owner=self.user,
            start_date=timezone.now().date(),
            frequency='MONTHLY',
            installments_total=2,
            value=10,
            transaction_type=Transaction.TransactionType.EXPENSE,
        )
        self.tx.recurring_transaction = rec_tx
        self.tx.save()

        url = reverse('transactions:edit', args=[self.tx.pk])
        response = self.client.get(url, follow=True)
        
        # A view deve redirecionar e mostrar uma mensagem de erro
        self.assertRedirects(response, reverse_lazy('transactions:expense_list'))
        self.assertContains(response, "Editing recurring transactions is not supported.")