#
# Arquivo: accounts/services.py
#
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

def get_exchange_rates(base_currency='USD'):
    """
    Busca as taxas de câmbio da API e as armazena em cache.
    """
    cache_key = f'exchange_rates_{base_currency}'
    rates = cache.get(cache_key)
    
    if rates is None:
        api_key = settings.EXCHANGERATE_API_KEY
        if not api_key:
            return None
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get('result') == 'success':
                rates = data['conversion_rates']
                cache.set(cache_key, rates, timeout=6 * 60 * 60)
        except requests.RequestException as e:
            print(f"Error fetching exchange rates: {e}")
            return None
    return rates

def get_conversion_rate(origin_currency, destination_currency):
    """
    Obtém a taxa de conversão entre duas moedas.
    """
    origin_currency = origin_currency.upper()
    destination_currency = destination_currency.upper()
    if origin_currency == destination_currency:
        return Decimal("1.0")

    usd_based_rates = get_exchange_rates('USD')
    if not usd_based_rates:
        raise Exception("Could not retrieve exchange rates.")
    
    rate_origin = usd_based_rates.get(origin_currency)
    rate_destination = usd_based_rates.get(destination_currency)

    if not rate_origin or not rate_destination:
        raise Exception(f"Currency not supported: {origin_currency} or {destination_currency}")
        
    # taxa_destino / taxa_origem
    rate = Decimal(str(rate_destination)) / Decimal(str(rate_origin))
    return rate