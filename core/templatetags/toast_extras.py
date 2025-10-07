from __future__ import annotations
from django import template

register = template.Library()

LEVEL_LABELS = {
    "success": "Success",
    "error": "Error",
    "warning": "Warning",
    "info": "Info",
}

@register.filter
def toast_level_label(tags: str) -> str:
    """
    Return a human-friendly label for the first known message tag.
    Example: 'error extra-stuff' -> 'Error'
    """
    if not tags:
        return "Info"
    for part in str(tags).split():
        if part in LEVEL_LABELS:
            return LEVEL_LABELS[part]
    return "Info"
