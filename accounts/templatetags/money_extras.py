from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()

def _fmt_amount(amount: Decimal | float | int) -> str:
    """Format to 2 decimal places with HALF_UP."""
    if amount is None:
        return "0.00"
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # basic thousands separator (international style); adjust if needed
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
