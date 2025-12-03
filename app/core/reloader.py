"""
Simple centralized reload handler used by supervisor or external triggers
to restart components cleanly without restarting FastAPI itself.
"""

from typing import Callable, Optional

_reload_function: Optional[Callable[[], None]] = None


def set_reload_function(func: Callable[[], None]):
    """Register the reload callback to be invoked on demand."""
    global _reload_function
    _reload_function = func


def reload_app():
    """Invoke the registered reload function if available."""
    if _reload_function is not None:
        _reload_function()
    else:
        print("No reload function set — nothing to reload.")
