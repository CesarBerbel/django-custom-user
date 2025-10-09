from __future__ import annotations
from decimal import Decimal
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class AccountType(models.Model):
    """
    Registrable class of account types (e.g., 'Personal', 'Business', 'Savings').
    """
    name = models.CharField(max_length=80, unique=True, help_text="Human-friendly type name")

    class Meta:
        verbose_name = "Account Type"
        verbose_name_plural = "Account Types"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Country(models.Model):
    """
    Registrable country with 2-letter ISO code and currency.
    """
    code = models.CharField(
        max_length=2,
        unique=True,
        help_text="Two-letter ISO code, e.g., 'PT', 'BR'",
        validators=[RegexValidator(r"^[A-Za-z]{2}$", "Use a 2-letter country code.")],
    )
    currency_code = models.CharField(
        max_length=3,
        help_text="Three-letter currency code, e.g., 'EUR', 'BRL'",
        validators=[RegexValidator(r"^[A-Za-z]{3}$", "Use a 3-letter currency code.")],
    )
    currency_name = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional currency name, e.g., 'Euro', 'Brazilian Real'",
    )

    class Meta:
        verbose_name = "Country"
        verbose_name_plural = "Countries"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code.upper()} ({self.currency_code.upper()})"


    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.currency_code = self.currency_code.upper()
        super().save(*args, **kwargs)

class Bank(models.Model):
    """
    Registrable bank/provider entity.
    """
    name = models.CharField(max_length=120, unique=True, help_text="Bank or provider display name")

    class Meta:
        verbose_name = "Bank"
        verbose_name_plural = "Banks"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
    

class Account(models.Model):
    """
    Financial account with bank, type, country, balances, and control fields.
    """
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name="accounts")
    type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name="accounts")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="accounts")

    initial_balance = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Initial balance at account creation",
    )
    balance = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Current balance; defaults to initial on create",
    )

    # Control fields
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")
    active = models.BooleanField(default=True, help_text="Whether the account is active")
    deactivated_at = models.DateTimeField(null=True, blank=True, help_text="When the account was deactivated")

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        ordering = ["bank", "id"]
        indexes = [
            models.Index(fields=["bank"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self) -> str:
        return f"{self.bank} · {self.type} · {self.country.code.upper()}"

    def save(self, *args, **kwargs):
        """
        Initialize 'balance' to 'initial_balance' on first save if not provided.
        Also auto-set deactivated_at when toggling active -> False.
        """
        if self._state.adding and (self.balance is None):
            self.balance = self.initial_balance

        if self.active is False and self.deactivated_at is None:
            self.deactivated_at = timezone.now()
        if self.active is True and self.deactivated_at is not None:
            # If reactivating, clear deactivation timestamp
            self.deactivated_at = None

        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self._state.adding and self.balance is not None and self.balance != self.initial_balance:
            raise ValidationError("On create, 'balance' must match 'initial_balance' or be empty.")

    def delete(self, using=None, keep_parents=False):
        if self.active:
            self.active = False
            self.deactivated_at = timezone.now()
            self.save(update_fields=["active", "deactivated_at", "updated_at"])        
