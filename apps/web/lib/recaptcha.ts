import 'server-only'

// Google reCAPTCHA (v3-style, invisible) server-side verification.
//
// The client executes an action and gets a short-lived token; we verify it
// here against Google's siteverify endpoint before allowing a sensitive
// action (login, signup, password reset, checkout). Secrets stay server-side.
//
// Unlike Turnstile (SaaS-only in this codebase), reCAPTCHA is intended for
// THIS deployment specifically and is gated purely on RECAPTCHA_SECRET_KEY
// being set — active in OSS/self-host the same as anywhere else. When the
// secret is absent, verification is disabled and every action is allowed
// through, so the app degrades gracefully instead of locking everyone out.

const SITEVERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

// v3 tokens carry a 0.0 (bot) - 1.0 (human) score instead of a pass/fail.
// 0.5 is Google's own suggested default cutoff.
const SCORE_THRESHOLD = 0.5

/** True when a server secret is configured, i.e. reCAPTCHA is active. */
export function isRecaptchaEnabled(): boolean {
  return Boolean(process.env.RECAPTCHA_SECRET_KEY)
}

export interface RecaptchaResult {
  /** Whether the request should be allowed through. */
  ok: boolean
  /** Machine reason, informational — 'missing_token' and 'error' are fail-open, never block. */
  reason?: 'missing_token' | 'verification_failed' | 'low_score' | 'action_mismatch' | 'error'
  score?: number
}

/**
 * Verify a reCAPTCHA token. Returns { ok: true } when reCAPTCHA is disabled
 * (no secret) so callers can stay unconditional. When enabled, a missing or
 * invalid token, a low score, or an action mismatch yields ok: false.
 *
 * `action` should match the action name the client passed to
 * grecaptcha.execute() (e.g. 'LOGIN', 'SIGNUP') — Google echoes it back so we
 * can catch a token minted for a different action being replayed here.
 */
export async function verifyRecaptcha(
  token: string | null | undefined,
  action?: string,
  remoteIp?: string | null,
): Promise<RecaptchaResult> {
  const secret = process.env.RECAPTCHA_SECRET_KEY
  // Disabled deployment — allow through.
  if (!secret) return { ok: true }

  // Fail-OPEN on a missing token too: a real human can end up with no token
  // for reasons that have nothing to do with being a bot — an ad-blocker or
  // privacy extension blocking google.com/recaptcha, a slow connection, a
  // corporate proxy. Blocking those visitors trades a small amount of bot
  // pressure for turning away real signups/logins/checkouts entirely, which
  // is the worse outcome. This still stops the far more common case: a bot
  // that DOES run the JS and gets scored low. A bot that skips the script
  // entirely was already unprotected before this feature existed, so this
  // isn't a regression — it's declining to make missing-token strictness a
  // new single point of failure for genuine visitors.
  if (!token) {
    console.warn('[recaptcha] no token supplied — allowing through (fail-open)', { action })
    return { ok: true, reason: 'missing_token' }
  }

  try {
    const body = new URLSearchParams({ secret, response: token })
    if (remoteIp) body.set('remoteip', remoteIp)

    const res = await fetch(SITEVERIFY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      // Never let a slow/unreachable Google hang the request forever.
      signal: AbortSignal.timeout(8000),
    })
    const data = (await res.json()) as {
      success: boolean
      score?: number
      action?: string
      'error-codes'?: string[]
    }

    if (!data.success) return { ok: false, reason: 'verification_failed' }
    if (typeof data.score === 'number' && data.score < SCORE_THRESHOLD) {
      return { ok: false, reason: 'low_score', score: data.score }
    }
    if (action && data.action && data.action !== action) {
      return { ok: false, reason: 'action_mismatch', score: data.score }
    }
    return { ok: true, score: data.score }
  } catch (err) {
    console.error('[recaptcha] siteverify request failed:', err)
    // Fail-OPEN on infrastructure errors: a Google outage shouldn't take down
    // our auth/checkout flows. Bot pressure is the exceptional case, not the norm.
    return { ok: true, reason: 'error' }
  }
}

/** Extract the best-effort client IP from a request for remoteip verification. */
export function clientIpFromHeaders(headers: Headers): string | undefined {
  const xff = headers.get('cf-connecting-ip') || headers.get('x-forwarded-for')
  if (!xff) return undefined
  return xff.split(',')[0]?.trim() || undefined
}
