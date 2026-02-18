"""
Agiloft API Client Library

A simple Python library for interacting with Agiloft REST API.
"""

__version__ = "1.0.0"

from .client import AgiloftClient
from .config import Config
from .exceptions import AgiloftError, AgiloftAuthError, AgiloftAPIError, AgiloftConfigError

__all__ = [
    "AgiloftClient",
    "Config",
    "AgiloftError",
    "AgiloftAuthError",
    "AgiloftAPIError",
    "AgiloftConfigError",
]
