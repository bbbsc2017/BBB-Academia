"""
Google reCAPTCHA server-side verification.

Used by endpoints the frontend calls DIRECTLY (bypassing the Next.js BFF),
where the bot-check token has to be verified in the Python backend instead —
currently just checkout. Auth flows (login/signup/reset) are verified in
Next.js (see apps/web/lib/recaptcha.ts); this module intentionally mirrors
that file's behavior so the two stay consistent.

Optional infrastructure: when LEARNHOUSE_RECAPTCHA_SECRET_KEY is unset,
verification is disabled and every request is allowed through, so the app
degrades gracefully instead of locking everyone out.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

# v3 tokens carry a 0.0 (bot) - 1.0 (human) score instead of a pass/fail.
# 0.5 is Google's own suggested default cutoff.
SCORE_THRESHOLD = 0.5


def is_recaptcha_enabled() -> bool:
    """True when a server secret is configured, i.e. reCAPTCHA is active."""
    return bool(os.environ.get("LEARNHOUSE_RECAPTCHA_SECRET_KEY"))


async def verify_recaptcha(
    token: str | None,
    action: str | None = None,
    remote_ip: str | None = None,
) -> bool:
    """
    Verify a reCAPTCHA token. Returns True when reCAPTCHA is disabled (no
    secret) so callers can stay unconditional. When enabled, a missing or
    invalid token, a low score, or an action mismatch returns False.
    """
    secret = os.environ.get("LEARNHOUSE_RECAPTCHA_SECRET_KEY")
    if not secret:
        return True  # Disabled deployment — allow through.

    # Fail-OPEN on a missing token too: a real human can end up with no token
    # for reasons that have nothing to do with being a bot — an ad-blocker or
    # privacy extension blocking google.com/recaptcha, a slow connection, a
    # corporate proxy. Blocking checkout for those visitors trades a small
    # amount of bot pressure for turning away real purchases, which is the
    # worse outcome. This still stops the far more common case: a bot that
    # DOES run the JS and gets scored low.
    if not token:
        logger.warning("[recaptcha] no token supplied — allowing through (fail-open), action=%s", action)
        return True

    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(SITEVERIFY_URL, data=data)
        result = response.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.error("[recaptcha] siteverify request failed: %s", e)
        # Fail-OPEN on infrastructure errors: a Google outage shouldn't take
        # down checkout. Bot pressure is the exceptional case, not the norm.
        return True

    if not result.get("success"):
        return False

    score = result.get("score")
    if score is not None and score < SCORE_THRESHOLD:
        return False

    result_action = result.get("action")
    return not (action and result_action and result_action != action)
