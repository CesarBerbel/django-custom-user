import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import GoogleCredentials

def get_upcoming_events(user):
    """
    Busca os próximos eventos e tarefas do Google Calendar e Tasks.
    Retorna um dicionário com duas listas separadas: {'events': [...], 'tasks': [...]},
    ou None se o usuário não estiver autenticado.
    """
    try:
        creds_model = user.google_credentials
    except GoogleCredentials.DoesNotExist:
        return None

    credentials = Credentials(
        token=creds_model.access_token,
        refresh_token=creds_model.refresh_token,
        token_uri=creds_model.token_uri,
        client_id=creds_model.client_id,
        client_secret=creds_model.client_secret,
        scopes=creds_model.scopes.split(" "),
    )

    events_list = []
    tasks_list = []
    now_utc = datetime.datetime.utcnow().isoformat() + 'Z'

    # --- 1. Buscar Eventos do Google Agenda ---
    try:
        calendar_service = build('calendar', 'v3', credentials=credentials)
        events_result = calendar_service.events().list(
            calendarId='primary', 
            timeMin=now_utc,
            maxResults=5, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events_result.get('items', []):
            start = event['start'].get('dateTime', event['start'].get('date'))
            events_list.append({
                'source': 'Calendar',
                'title': event['summary'],
                'start_time': start,
            })
    except Exception as e:
        print(f"Error fetching calendar events: {e}")

    # --- 2. Buscar Tarefas do Google Tarefas ---
    try:
        tasks_service = build('tasks', 'v1', credentials=credentials)
        tasks_result = tasks_service.tasks().list(
            tasklist='@default',
            showCompleted=False,
            maxResults=5
        ).execute()
        
        for task in tasks_result.get('items', []):
            if task.get('due'): # Só incluímos tarefas com data de vencimento
                tasks_list.append({
                    'source': 'Tasks',
                    'title': task['title'],
                    'due_date': task.get('due'),
                })
    except Exception as e:
        print(f"Error fetching tasks: {e}")

    # --- 3. Retornar o dicionário com as listas separadas ---
    return {
        'events': events_list,
        'tasks': tasks_list
    }