from __future__ import annotations
from decimal import Decimal
from django.test import TestCase
from accounts.forms import AccountCreateForm, AccountUpdateForm
from accounts.models import Account, AccountType, Country, Bank
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse


class AccountFormsTests(TestCase):
    def setUp(self):
        self.type = AccountType.objects.create(name="Savings")
        self.country = Country.objects.create(code="BR", currency_code="BRL", currency_name="Real")
        self.bank = Bank.objects.create(name="Bank X")

    def test_account_create_form_fields(self):
        form = AccountCreateForm()
        self.assertIn("bank", form.fields)
        self.assertIn("type", form.fields)
        self.assertIn("country", form.fields)
        self.assertIn("initial_balance", form.fields)
        # Must NOT be present in create:
        self.assertNotIn("balance", form.fields)
        self.assertNotIn("active", form.fields)

    def test_account_update_form_fields(self):
        form = AccountUpdateForm()
        self.assertIn("bank", form.fields)
        self.assertIn("type", form.fields)
        self.assertIn("country", form.fields)
        self.assertNotIn("initial_balance", form.fields)
        self.assertNotIn("balance", form.fields)
        self.assertNotIn("active", form.fields)

    def test_account_create_form_saves_active_and_default_balance(self):
        data = {
            "bank": self.bank.id,
            "type": self.type.id,
            "country": self.country.id,
            "initial_balance": "123.45",
        }
        form = AccountCreateForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        obj.save()
        self.assertTrue(obj.active)
        self.assertEqual(obj.balance, Decimal("123.45"))

class AccountModelTests(TestCase):
    def setUp(self):
        self.type = AccountType.objects.create(name="Checking")
        self.country = Country.objects.create(code="pt", currency_code="eur", currency_name="Euro")
        self.bank = Bank.objects.create(name="Test Bank")

    def test_create_account_sets_balance_to_initial(self):
        acc = Account.objects.create(
            bank=self.bank,
            type=self.type,
            country=self.country,
            initial_balance=Decimal("100.00"),
            balance=None,  # ensure defaulting happens
        )
        self.assertTrue(acc.active)
        self.assertEqual(acc.balance, Decimal("100.00"))

    def test_country_codes_are_normalized_to_uppercase_on_save(self):
        acc = Account.objects.create(
            bank=self.bank,
            type=self.type,
            country=self.country,  # lower setUp values
            initial_balance=Decimal("0.00"),
            balance=None,
        )
        # refresh related
        acc.country.refresh_from_db()
        self.assertEqual(acc.country.currency_code, "EUR")
        self.assertEqual(acc.country.code, "PT")

    def test_soft_delete_marks_inactive_and_sets_timestamp(self):
        acc = Account.objects.create(
            bank=self.bank,
            type=self.type,
            country=self.country,
            initial_balance=Decimal("10.00"),
            balance=None,
        )
        self.assertTrue(acc.active)
        self.assertIsNone(acc.deactivated_at)

        acc.delete()  # soft delete
        acc.refresh_from_db()
        self.assertFalse(acc.active)
        self.assertIsNotNone(acc.deactivated_at)
        self.assertLessEqual(acc.deactivated_at, timezone.now())

    def test_queryset_active_only_convention(self):
        active = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("1.00"), balance=None
        )
        inactive = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("2.00"), balance=None
        )
        inactive.delete()  # soft delete

        active_ids = set(Account.objects.filter(active=True).values_list("id", flat=True))
        self.assertIn(active.id, active_ids)
        self.assertNotIn(inactive.id, active_ids)        

class AccountViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="pass12345")
        self.client.force_login(self.user)

        self.type = AccountType.objects.create(name="Checking")
        self.country = Country.objects.create(code="PT", currency_code="EUR", currency_name="Euro")
        self.bank = Bank.objects.create(name="Bank Y")

        self.acc = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("50.00"), balance=None
        )

    def test_list_view_shows_only_active(self):
        # Make an inactive account
        inactive = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("20.00"), balance=None
        )
        inactive.delete()  # soft delete

        url = reverse("accounts:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        accounts = list(resp.context["accounts"])
        ids = [a.id for a in accounts]
        self.assertIn(self.acc.id, ids)
        self.assertNotIn(inactive.id, ids)

    def test_create_view_creates_active_with_initial_balance(self):
        url = reverse("accounts:create")
        data = {
            "bank": self.bank.id,
            "type": self.type.id,
            "country": self.country.id,
            "initial_balance": "999.99",
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "created successfully", html=False)

        created = Account.objects.exclude(id=self.acc.id).latest("id")
        self.assertTrue(created.active)
        self.assertEqual(created.balance, Decimal("999.99"))

    def test_delete_view_soft_deletes(self):
        url = reverse("accounts:delete", args=[self.acc.id])
        # GET confirm page
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "deactivate", html=False)

        # POST to soft delete
        resp_post = self.client.post(url, follow=True)
        self.assertEqual(resp_post.status_code, 200)
        # self.assertContains(resp_post, "deactivated", html=False)

        self.acc.refresh_from_db()
        self.assertFalse(self.acc.active)

        # ensure it disappears from list
        list_url = reverse("accounts:list")
        resp_list = self.client.get(list_url)
        self.assertNotContains(resp_list, str(self.acc.bank), html=False)

    def test_list_view_shows_symbol(self):
        self.country.currency_symbol = "€"
        self.country.save()
        resp = self.client.get(reverse("accounts:list"))
        self.assertContains(resp, "€", html=False)