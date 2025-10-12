from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
import json
from decimal import Decimal
from accounts.models import Account, AccountType, Country, Bank

class HomeViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="pass12345")
        self.client.force_login(self.user)    

    def test_home_status_code(self):
        """Home page should return HTTP 200."""
        url = reverse("core:home")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

class DashboardViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        # Create users
        self.user1 = User.objects.create_user(email="user1@example.com", password="password")
        self.user2 = User.objects.create_user(email="user2@example.com", password="password")

        # Create related objects
        self.type_checking = AccountType.objects.create(name="Checking")
        self.country_eur = Country.objects.create(code="EU", currency_code="EUR", currency_symbol="€")
        self.country_usd = Country.objects.create(code="US", currency_code="USD", currency_symbol="$")
        self.bank_a = Bank.objects.create(name="Bank A")
        self.bank_b = Bank.objects.create(name="Bank B")
        self.bank_c = Bank.objects.create(name="Inactive Bank")
        self.bank_d = Bank.objects.create(name="Other User Bank")

        # Create accounts for user1
        # Two active EUR accounts to test currency aggregation
        self.acc1_user1 = Account.objects.create(
            owner=self.user1, bank=self.bank_a, type=self.type_checking, country=self.country_eur,
            initial_balance=Decimal("1000.00")
        )
        self.acc2_user1 = Account.objects.create(
            owner=self.user1, bank=self.bank_b, type=self.type_checking, country=self.country_eur,
            initial_balance=Decimal("200.00")
        )
        # One active USD account
        self.acc3_user1 = Account.objects.create(
            owner=self.user1, bank=self.bank_b, type=self.type_checking, country=self.country_usd,
            initial_balance=Decimal("500.00")
        )
        # One inactive account for user1 (soft-deleted)
        self.acc4_user1_inactive = Account.objects.create(
            owner=self.user1, bank=self.bank_c, type=self.type_checking, country=self.country_eur,
            initial_balance=Decimal("999.00")
        )
        self.acc4_user1_inactive.delete()

        # Create account for user2 (should not be visible to user1)
        self.acc1_user2 = Account.objects.create(
            owner=self.user2, bank=self.bank_d, type=self.type_checking, country=self.country_usd,
            initial_balance=Decimal("3000.00")
        )

    def test_dashboard_requires_login(self):
        """Dashboard page should redirect anonymous users to the login page."""
        url = reverse("core:home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users:login')}?next={url}")

    def test_dashboard_empty_state_for_new_user(self):
        """Dashboard should show a welcome message if the user has no accounts."""
        # Create a user with no accounts and log in
        user_no_accounts = get_user_model().objects.create_user(email="new@example.com", password="password")
        self.client.force_login(user_no_accounts)

        url = reverse("core:home")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You don't have any active accounts yet.")
        self.assertContains(response, "Create your first account")
        # Ensure that chart and totals are not rendered
        self.assertNotContains(response, '<canvas id="accountBalanceChart">')
        self.assertNotContains(response, "Total Balance")

    def test_dashboard_displays_correct_data_and_totals(self):
        """Dashboard should display correct totals and only active, owned accounts."""
        self.client.force_login(self.user1)
        url = reverse("core:home")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")

        # 1. Check currency totals (1000 + 200 EUR)
        self.assertContains(response, "Total Balance (EUR)")
        self.assertContains(response, "1,200.00") # using money tag format
        # 2. Check USD total
        self.assertContains(response, "Total Balance (USD)")
        self.assertContains(response, "500.00")

        # 3. Check if active accounts are listed
        self.assertContains(response, self.bank_a.name) # acc1
        self.assertContains(response, self.bank_b.name) # acc2 and acc3

        # 4. Check that inactive and other user's accounts are NOT listed
        self.assertNotContains(response, self.bank_c.name) # inactive
        self.assertNotContains(response, self.bank_d.name) # user2's account

    def test_dashboard_context_for_chart_is_correct(self):
        """The context should contain correctly formatted chart data."""
        self.client.force_login(self.user1)
        url = reverse("core:home")
        response = self.client.get(url)
        
        # Check context variables for the chart
        self.assertIn("chart_labels", response.context)
        self.assertIn("chart_data", response.context)
        
        # Decode the JSON data from the context
        labels = json.loads(response.context["chart_labels"])
        data = json.loads(response.context["chart_data"])

        # There should be 3 active accounts for user1
        self.assertEqual(len(labels), 3)
        self.assertEqual(len(data), 3)

        # The data should match the balances of the active accounts
        # Note: Order can vary depending on default DB ordering, so we test for presence
        expected_labels = [
            f"{self.acc1_user1.bank} ({self.acc1_user1.country.code})",
            f"{self.acc2_user1.bank} ({self.acc2_user1.country.code})",
            f"{self.acc3_user1.bank} ({self.acc3_user1.country.code})",
        ]
        expected_data = ["1000.00", "200.00", "500.00"]

        self.assertCountEqual(labels, expected_labels)
        self.assertCountEqual(data, expected_data)