"""Validation for Telegram Mini App (WebApp) ``initData``.

The mini app opened from the bot passes a signed ``initData`` string. We verify
it with HMAC-SHA256 using ``HMAC_SHA256("WebAppData", bot_token)`` as the secret
key, per https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, *, max_age: int = 86400) -> dict | None:
    """Return the parsed ``user`` dict when ``init_data`` is authentic, else None.

    ``init_data`` is the raw query-string handed to the WebApp. On success the
    returned dict is the Telegram user object (id, first_name, username, …).
    """
    if not init_data or not bot_token:
        return None

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    auth_date = pairs.get("auth_date")
    if auth_date:
        try:
            if time.time() - int(auth_date) > max_age:
                return None
        except ValueError:
            return None

    raw_user = pairs.get("user")
    if not raw_user:
        return None
    try:
        return json.loads(raw_user)
    except json.JSONDecodeError:
        return None
