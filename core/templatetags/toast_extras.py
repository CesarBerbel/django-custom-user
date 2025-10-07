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

@register.filter
def toast_bs_classes(tags: str) -> str:
    """
    Map Django message tags to Bootstrap 5.3 subtle background/border classes.
    """
    if not tags:
        return "bg-info-subtle border border-info-subtle"
    parts = str(tags).split()
    if "success" in parts:
        return "bg-success-subtle border border-success-subtle"
    if "error" in parts:
        return "bg-danger-subtle border border-danger-subtle"
    if "warning" in parts:
        return "bg-warning-subtle border border-warning-subtle"
    return "bg-info-subtle border border-info-subtle"