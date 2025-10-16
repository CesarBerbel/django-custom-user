# core/services.py
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

def get_exchange_rates(base_currency='USD'):
    """
    Busca as taxas de câmbio da API e as armazena em cache por 6 horas.
    """
    cache_key = f'exchange_rates_{base_currency}'
    rates = cache.get(cache_key)
    
    if rates is None:
        api_key = settings.EXCHANGERATE_API_KEY
        if not api_key:
            return None # Retorna None se a chave de API não estiver configurada

        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status() # Lança um erro se a resposta não for 200 OK
            data = response.json()
            if data.get('result') == 'success':
                rates = data['conversion_rates']
                cache.set(cache_key, rates, timeout=6 * 60 * 60) # Cache por 6 horas
        except requests.RequestException as e:
            print(f"Error fetching exchange rates: {e}")
            return None
            
    return rates

def calculate_total_net_worth(accounts, target_currency_code):
    """
    Calcula o patrimônio líquido total convertendo todos os saldos de conta
    para a moeda de destino.
    """
    if not target_currency_code or not accounts:
        return None, None

    # As taxas são geralmente baseadas em USD, então buscamos a base USD
    usd_based_rates = get_exchange_rates(base_currency='USD')
    if not usd_based_rates:
        return None, None
        
    total_in_usd = Decimal('0.0')

    # Passo 1: Converter todos os saldos para um denominador comum (USD)
    for account in accounts:
        balance = account.balance
        currency_code = account.country.currency_code.upper()
        
        if currency_code == 'USD':
            total_in_usd += balance
        else:
            rate_to_usd = usd_based_rates.get(currency_code)
            if rate_to_usd:
                # balance / rate = valor em USD (Ex: 5 EUR / 0.92 EUR/USD = X USD. ERRADO)
                # O correto é: balance / rate_EUR = valor em USD (Ex: 5 EUR / 0.92 EUR_por_USD -> Não faz sentido)
                # A API retorna 1 USD = X OTRA. Então valor / rate_to_usd
                # 1 USD = 0.92 EUR. Logo, 5 EUR / 0.92 = 5.43 USD
                # 1 USD = 5.0 BRL. Logo, 10 BRL / 5.0 = 2.0 USD
                usd_value = balance / Decimal(str(rate_to_usd))
                total_in_usd += usd_value
            else:
                print(f"Warning: No exchange rate found for {currency_code}")

    # Passo 2: Converter o total em USD para a moeda de destino do usuário
    rate_from_usd_to_target = usd_based_rates.get(target_currency_code.upper())
    
    if not rate_from_usd_to_target:
        print(f"Warning: Could not find target currency rate for {target_currency_code}")
        return None, None
    
    total_in_target_currency = total_in_usd * Decimal(str(rate_from_usd_to_target))

    return total_in_target_currency, target_currency_code

def get_conversion_rate(origin_currency, destination_currency):
    """
    Obtém a taxa de conversão de uma moeda de origem para uma de destino.
    Retorna o multiplicador. Ex: se 1 EUR = 1.08 USD, retorna 1.08.
    """
    origin_currency = origin_currency.upper()
    destination_currency = destination_currency.upper()

    if origin_currency == destination_currency:
        return Decimal("1.0")

    # Usa a função em cache que já busca as taxas com base no USD
    usd_based_rates = get_exchange_rates('USD')
    if not usd_based_rates:
        raise Exception("Could not retrieve exchange rates from the service.")
    
    # Taxas em relação ao USD
    rate_origin_to_usd = usd_based_rates.get(origin_currency)
    rate_usd_to_destination = usd_based_rates.get(destination_currency)

    if not rate_origin_to_usd or not rate_usd_to_destination:
        raise Exception(f"Currency not supported: {origin_currency} or {destination_currency}")
        
    # Lógica de conversão cruzada (ex: EUR -> BRL via USD)
    # 1 EUR = X USD  ->  valor_eur / rate_eur_usd
    # 1 USD = Y BRL  ->  valor_usd * rate_usd_brl
    # Logo, valor_eur * (rate_usd_brl / rate_eur_usd) = valor_brl
    
    # A API v6 retorna as taxas de uma forma mais simples: 1 USD = X EUR, 1 USD = Y BRL
    # valor_usd = valor_eur / rate_eur
    # valor_brl = valor_usd * rate_brl
    # valor_brl = (valor_eur / rate_eur) * rate_brl
    
    rate = Decimal(str(rate_usd_to_destination)) / Decimal(str(rate_origin_to_usd))
    
    return rate