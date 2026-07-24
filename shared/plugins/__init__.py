"""Plugin system.

Provides a generic ``Registry`` and concrete registries for parsers, AI
providers and publishers. New implementations register themselves via a
decorator and become usable without changing existing code (Open/Closed).
"""

from __future__ import annotations

# Importing the sub-packages triggers registration of built-in plugins.
from shared.plugins import ai as _ai  # noqa: F401,E402
from shared.plugins import parsers as _parsers  # noqa: F401,E402
from shared.plugins import publishers as _publishers  # noqa: F401,E402
from shared.plugins.registry import Registry

__all__ = ["Registry"]
