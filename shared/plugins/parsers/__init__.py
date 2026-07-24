"""Parser plugins — fetch raw items from news sources.

Each parser implements :class:`BaseParser` and registers itself in
``parser_registry`` under its :class:`~shared.enums.SourceType` value.
"""

from __future__ import annotations

from shared.plugins.parsers import api as _api  # noqa: F401,E402

# Register built-in parsers.
from shared.plugins.parsers import rss as _rss  # noqa: F401,E402
from shared.plugins.parsers import telegram as _telegram  # noqa: F401,E402
from shared.plugins.parsers import website as _website  # noqa: F401,E402
from shared.plugins.parsers.base import BaseParser, ParsedItem, parser_registry

__all__ = ["BaseParser", "ParsedItem", "parser_registry"]
