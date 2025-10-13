#
# Arquivo: transactions/tests.py
#
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import Account, Bank, AccountType, Country
from .models import Transaction, Category
from .forms import IncomeForm, ExpenseForm, TransferForm

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

    # --- Testes de Lógica de Atualização de Saldo (MUITO IMPORTANTES) ---

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