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
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="pass12345")
        self.client.force_login(self.user)
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
        # Must NOT be present in update:
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
        obj.owner = self.user  # normally set in view
        obj.save()
        self.assertTrue(obj.active)
        self.assertEqual(obj.balance, Decimal("123.45"))

class AccountModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="pass12345")
        self.client.force_login(self.user)
        self.type = AccountType.objects.create(name="Checking")
        self.country = Country.objects.create(code="pt", currency_code="eur", currency_name="Euro")
        self.bank = Bank.objects.create(name="Test Bank")

    def test_create_account_sets_balance_to_initial(self):
        acc = Account.objects.create(
            bank=self.bank,
            type=self.type,
            owner=self.user,
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
            owner=self.user,
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
            owner=self.user,
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
            initial_balance=Decimal("1.00"), balance=None, owner=self.user
        )
        inactive = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("2.00"), balance=None, owner=self.user
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
            initial_balance=Decimal("50.00"), balance=None, owner=self.user
        )

    def test_list_view_shows_only_active(self):
        # Make an inactive account
        inactive = Account.objects.create(
            bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("20.00"), balance=None, owner=self.user
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

class AccountOwnershipTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.u1 = U.objects.create_user(email="u1@example.com", password="pass12345")
        self.u2 = U.objects.create_user(email="u2@example.com", password="pass12345")
        self.type = AccountType.objects.create(name="Checking")
        self.country = Country.objects.create(code="PT", currency_code="EUR", currency_name="Euro")
        self.bank = Bank.objects.create(name="Bank Z")

        # u1's account
        self.acc_u1 = Account.objects.create(
            owner=self.u1, bank=self.bank, type=self.type, country=self.country,
            initial_balance=Decimal("10.00"), balance=Decimal("10.00"),
        )

    def test_list_shows_only_own_accounts(self):
        self.client.force_login(self.u2)
        resp = self.client.get(reverse("accounts:list"))
        self.assertNotContains(resp, str(self.acc_u1.bank), html=False)

    def test_cannot_edit_or_delete_foreign_account(self):
        self.client.force_login(self.u2)
        resp = self.client.get(reverse("accounts:edit", args=[self.acc_u1.id]))
        self.assertEqual(resp.status_code, 404)  # filtered by queryset
        resp2 = self.client.post(reverse("accounts:delete", args=[self.acc_u1.id]))
        self.assertEqual(resp2.status_code, 404)       

    def test_create_binds_owner(self):
        self.client.force_login(self.u2)
        resp = self.client.post(reverse("accounts:create"), {
            "bank": self.bank.id,
            "type": self.type.id,
            "country": self.country.id,
            "initial_balance": "12.34",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        acc = Account.objects.latest("id")
        self.assertEqual(acc.owner, self.u2)         


# accounts/tests.py

# ... (imports existentes e outras classes de teste) ...

class AccountTypeManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="settings@test.com", password="pw")
        self.client.force_login(self.user)
        self.type = AccountType.objects.create(name="Savings")

    def test_type_list_view(self):
        url = reverse("accounts:type_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Savings")

    def test_type_create_view(self):
        url = reverse("accounts:type_create")
        response = self.client.post(url, {"name": "Investment"}, follow=True)
        self.assertRedirects(response, reverse("accounts:type_list"))
        self.assertTrue(AccountType.objects.filter(name="Investment").exists())
        self.assertContains(response, "created successfully")

    def test_type_update_view(self):
        url = reverse("accounts:type_edit", args=[self.type.pk])
        response = self.client.post(url, {"name": "Emergency Fund"}, follow=True)
        self.assertRedirects(response, reverse("accounts:type_list"))
        self.type.refresh_from_db()
        self.assertEqual(self.type.name, "Emergency Fund")

    def test_type_delete_view(self):
        url = reverse("accounts:type_delete", args=[self.type.pk])
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, reverse("accounts:type_list"))
        self.assertFalse(AccountType.objects.filter(pk=self.type.pk).exists())

class CountryManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="country@test.com", password="pw")
        self.client.force_login(self.user)
        self.country = Country.objects.create(code="BR", currency_code="BRL", currency_name="Real", currency_symbol="R$")

    def test_country_list_view(self):
        url = reverse("accounts:country_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BR")

    def test_country_create_view(self):
        url = reverse("accounts:country_create")
        data = {"code": "PT", "currency_code": "EUR", "currency_name": "Euro", "currency_symbol": "€"}
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, reverse("accounts:country_list"))
        self.assertTrue(Country.objects.filter(code="PT").exists())

    def test_country_update_view(self):
        url = reverse("accounts:country_edit", args=[self.country.pk])
        data = {"code": "BR", "currency_code": "BRL", "currency_name": "Brazilian Real", "currency_symbol": "R$"}
        response = self.client.post(url, data, follow=True)
        self.country.refresh_from_db()
        self.assertEqual(self.country.currency_name, "Brazilian Real")

    def test_country_delete_view(self):
        url = reverse("accounts:country_delete", args=[self.country.pk])
        response = self.client.post(url, follow=True)
        self.assertFalse(Country.objects.filter(pk=self.country.pk).exists())