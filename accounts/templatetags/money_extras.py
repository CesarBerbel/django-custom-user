from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django import template

register = template.Library()

def _fmt_amount(amount: Decimal | float | int | None) -> str:
    """Formata para 2 casas decimais com HALF_UP, de forma segura."""
    # Checagem de segurança robusta
    if amount is None or amount == '':
        amount = Decimal("0") # Trata None e string vazia como zero
    
    try:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
    except (TypeError, ValueError, InvalidOperation):
        # Se, mesmo assim, a conversão falhar, retorne um erro amigável em vez de quebrar
        print(f"DEBUG: Could not convert amount '{amount}' (type: {type(amount)}) to Decimal.")
        return "ERR"

    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:,.2f}"

@register.simple_tag
def money(amount, country=None, currency_code: str | None = None, symbol: str | None = None, symbol_first: bool = True):
    """
    Format money with a symbol when available; fallback to currency code.
    Usage:
      {% money acc.balance acc.country %}
      {% money total currency_code="EUR" symbol="€" %}
    """
    txt = _fmt_amount(amount)

    # Resolve symbol/code from country if given
    if country is not None:
        try:
            if symbol is None:
                symbol = (country.currency_symbol or "").strip()
            if currency_code is None:
                currency_code = (country.currency_code or "").upper()
        except Exception:
            pass

    # Choose formatting
    if symbol:
        # default style: symbol before number with a non-breaking space
        return f"{symbol}\u00A0{txt}" if symbol_first else f"{txt}\u00A0{symbol}"
    if currency_code:
        return f"{txt} {currency_code}"
    return txt
