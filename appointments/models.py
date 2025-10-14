from django.db import models
from django.conf import settings

class GoogleCredentials(models.Model):
    """
    Stores OAuth 2.0 credentials for a user.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_credentials"
    )
    access_token = models.CharField(max_length=2048)
    refresh_token = models.CharField(max_length=2048)
    # Store other useful info from the token response
    token_uri = models.URLField()
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()

    def __str__(self):
        return f"Credentials for {self.user.email}"

    class Meta:
        verbose_name_plural = "Google Credentials"  