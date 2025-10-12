from __future__ import annotations
from django import template

register = template.Library()

@register.filter
def replace_str(value, args):
    """
    Replaces a substring with another.
    Usage: {{ some_string|replace_str:"old,new" }}
    Note: 'args' must be a comma-separated string.
    """
    if not isinstance(value, str):
        value = str(value)
    
    try:
        old, new = str(args).split(',')
        return value.replace(old, new)
    except (ValueError, TypeError):
        # Return original value if args are invalid
        return value