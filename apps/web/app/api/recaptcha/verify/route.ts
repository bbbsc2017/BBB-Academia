import { NextRequest, NextResponse } from 'next/server'
import { verifyRecaptcha, clientIpFromHeaders } from '@lib/recaptcha'

// Standalone reCAPTCHA verification endpoint, used by the forms that call the
// backend DIRECTLY (login / forgot-password / reset-password / guest
// checkout). Signup has its own gateway (app/api/signup) that verifies
// inline. Returns { ok } (200 either way) so the client can branch.
//
// Unlike Turnstile, this is NOT SaaS-gated — it's active on this deployment
// whenever RECAPTCHA_SECRET_KEY is set (see lib/recaptcha.ts).
export async function POST(request: NextRequest) {
  let token: string | null = null
  let action: string | undefined
  try {
    const body = await request.json()
    token = body?.token ?? null
    action = body?.action
  } catch {
    // no/invalid body → treated as missing token below
  }

  const result = await verifyRecaptcha(token, action, clientIpFromHeaders(request.headers))
  return NextResponse.json({ ok: result.ok, reason: result.reason })
}
