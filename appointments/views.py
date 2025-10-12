from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from google_auth_oauthlib.flow import Flow
from .models import GoogleCredentials

# Escopos definem o que pediremos permissão para acessar.
# .readonly significa que só poderemos ler, não modificar.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

def get_flow():
    """
    Builds the Google OAuth 2.0 Flow object.
    """
    return Flow.from_client_secrets_file(
        # Esta linha assume que você baixou o client_secret.json da tela de credenciais.
        # Alternativamente, podemos construir a configuração a partir do settings.py.
        # Por simplicidade, vamos usar o arquivo por enquanto.
        # Crie um arquivo `client_secret.json` na raiz do seu projeto com o conteúdo
        # fornecido pelo Google.
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_OAUTH2_REDIRECT_URI
    )

@login_required
def google_connect_view(request):
    """
    Initiates the OAuth 2.0 authorization flow.
    """
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent' # 'offline' é crucial para obter um refresh_token
    )
    request.session['oauth_state'] = state
    return redirect(authorization_url)

@login_required
def google_oauth2_callback_view(request):
    """
    Handles the redirect from Google after user authorization.
    """
    state = request.session.pop('oauth_state', '')
    if state != request.GET.get('state'):
        messages.error(request, "Authorization state mismatch. Please try again.")
        return redirect(reverse("core:home"))

    flow = get_flow()
    flow.fetch_token(authorization_response=request.get_full_path())
    credentials = flow.credentials

    # Salva as credenciais para o usuário
    GoogleCredentials.objects.update_or_create(
        user=request.user,
        defaults={
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': " ".join(credentials.scopes),
        }
    )

    messages.success(request, "Successfully connected to your Google account.")
    return redirect(reverse("core:home"))
    
@login_required
def google_disconnect_view(request):
    """
    Deletes the user's stored Google credentials.
    """
    GoogleCredentials.objects.filter(user=request.user).delete()
    messages.info(request, "Your Google account has been disconnected.")
    return redirect(reverse("core:home"))