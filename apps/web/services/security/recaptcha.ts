'use client'
import { getConfig, withBasePath } from '@services/config/config'

// Client-side Google reCAPTCHA (v3-style, invisible — no checkbox widget).
// Reads the PUBLIC site key from the runtime config (getConfig — this is a
// prebuilt image, so process.env.NEXT_PUBLIC_* isn't reliable at runtime),
// same convention as TurnstileWidget's getTurnstileSiteKey.
//
// Unlike Turnstile, reCAPTCHA here is active on ANY deployment mode (not
// SaaS-only) — this app self-hosts under one fixed production domain, so the
// per-domain site-key registration concern that gates Turnstile to SaaS
// doesn't apply. The server enforces the real gate (RECAPTCHA_SECRET_KEY set
// or not); the client-side site key merely decides whether to bother asking
// Google for a token at all.

/** Read the public site key at runtime. Empty string ⇒ reCAPTCHA disabled. */
export function getRecaptchaSiteKey(): string {
  return getConfig('NEXT_PUBLIC_RECAPTCHA_SITE_KEY', '')
}

export function isRecaptchaConfigured(): boolean {
  return getRecaptchaSiteKey().length > 0
}

declare global {
  interface Window {
    grecaptcha?: {
      enterprise?: {
        ready: (cb: () => void) => void
        execute: (siteKey: string, opts: { action: string }) => Promise<string>
      }
    }
  }
}

let scriptLoadPromise: Promise<void> | null = null

/** Injects the reCAPTCHA loader script once, no matter how many callers ask. */
function loadScript(siteKey: string): Promise<void> {
  if (scriptLoadPromise) return scriptLoadPromise

  scriptLoadPromise = new Promise((resolve, reject) => {
    if (typeof document === 'undefined') return reject(new Error('no document'))
    if (window.grecaptcha?.enterprise) return resolve()

    const existing = document.querySelector<HTMLScriptElement>('script[data-recaptcha-loader]')
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('recaptcha script failed to load')))
      return
    }

    const script = document.createElement('script')
    script.src = `https://www.google.com/recaptcha/enterprise.js?render=${encodeURIComponent(siteKey)}`
    script.async = true
    script.defer = true
    script.dataset.recaptchaLoader = 'true'
    script.addEventListener('load', () => resolve())
    script.addEventListener('error', () => reject(new Error('recaptcha script failed to load')))
    document.head.appendChild(script)
  })

  return scriptLoadPromise
}

/**
 * Executes a reCAPTCHA action and returns the resulting token, or null when
 * reCAPTCHA is disabled (no site key) or anything goes wrong — callers treat
 * a null token as "no bot signal available" and let the server-side
 * verification (which fails OPEN when its own secret is unset) decide.
 */
export async function getRecaptchaToken(action: string): Promise<string | null> {
  const siteKey = getRecaptchaSiteKey()
  if (!siteKey) return null

  try {
    await loadScript(siteKey)
    return await new Promise<string | null>((resolve) => {
      const grecaptcha = window.grecaptcha?.enterprise
      if (!grecaptcha) return resolve(null)
      grecaptcha.ready(() => {
        grecaptcha
          .execute(siteKey, { action })
          .then((token) => resolve(token || null))
          .catch(() => resolve(null))
      })
    })
  } catch (err) {
    console.error('[recaptcha] failed to obtain token:', err)
    return null
  }
}

/**
 * Verifies a token via the server route. Resolves true when reCAPTCHA is
 * disabled server-side, the token checks out, or a network error occurs
 * (fail-open, matching the server's own philosophy) — false only on a
 * positive verification failure (bad/missing token, low score, expired).
 */
export async function verifyRecaptchaToken(token: string | null, action: string): Promise<boolean> {
  if (!isRecaptchaConfigured()) return true
  try {
    const res = await fetch(withBasePath('/api/recaptcha/verify'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, action }),
    })
    const data = await res.json().catch(() => ({ ok: true }))
    return Boolean(data.ok)
  } catch {
    return true
  }
}

/** Convenience: get a fresh token for `action` and verify it in one call. */
export async function checkRecaptcha(action: string): Promise<boolean> {
  const token = await getRecaptchaToken(action)
  return verifyRecaptchaToken(token, action)
}
