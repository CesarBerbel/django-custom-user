from __future__ import annotations
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Country


class UserManager(BaseUserManager):
    """Custom manager where email is the unique identifiers for authentication."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create a regular user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None, **extra_fields):
        """Create a superuser with all permissions."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model that uses email as the unique identifier instead of username.
    """
    username = None  # remove username field
    email = models.EmailField(_("email address"), unique=True)

    # Add future-proof fields here (e.g., company, phone, etc.)
    # company = models.CharField(max_length=120, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # Email & Password are required by default

    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
            self.email = self.__class__.objects.normalize_email(self.email)
        super().save(*args, **kwargs)


class UserPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences"
    )
    # Moeda na qual o patrimônio total será exibido
    preferred_currency = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="The currency to display the total net worth in."
    )
    
    def __str__(self):
        return f"Preferences for {self.user.email}"

# SINAL (Signal): Cria um UserPreferences automaticamente para cada novo User
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        UserPreferences.objects.create(user=instance)        