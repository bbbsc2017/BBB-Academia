'use client'
import React, { useRef, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, Loader2, LockKeyhole } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@components/Contexts/AuthContext'
import { getUriWithOrg } from '@services/config/config'
import { signup } from '@services/auth/auth'
import { generateUsernameFromEmail } from '@services/auth/username'
import { getErrorMessage } from '@services/utils/ts/errorMessage'
import { PasswordStrengthIndicator, validatePasswordStrength } from '@components/Auth/PasswordStrengthIndicator'
import TurnstileWidget, { useTurnstileRequired, type TurnstileWidgetHandle } from '@components/Auth/TurnstileWidget'
import { checkRecaptcha, getRecaptchaToken } from '@services/security/recaptcha'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'

type Mode = 'signup' | 'login'

interface GuestCheckoutPanelProps {
  orgslug: string
  orgId: number
  offerUuid: string
  /** Called once a session has been established (either by signup+auto-login, or by direct login). */
  onAuthenticated: () => void
}

/**
 * Inline "create account or log in" panel shown in place of the checkout
 * button when the visitor has no session yet. Only email + password are
 * collected — Bold's checkout only ever uses payer_email (see
 * BoldProvider.create_checkout), so a username is generated automatically
 * (generateUsernameFromEmail), matching the convention already used for
 * JIT-provisioned accounts (Google OAuth / bbbsc SSO) server-side.
 */
export default function GuestCheckoutPanel({ orgslug, orgId, offerUuid, onAuthenticated }: GuestCheckoutPanelProps) {
  const { t } = useTranslation()
  const { signIn } = useAuth() as any
  const { track } = useLHAnalytics('learner')
  const turnstileRef = useRef<TurnstileWidgetHandle>(null)
  const turnstileRequired = useTurnstileRequired()
  const shownRef = useRef(false)

  const [mode, setMode] = useState<Mode>('signup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [accountJustCreated, setAccountJustCreated] = useState(false)

  if (!shownRef.current) {
    shownRef.current = true
    track(AnalyticsEvent.GuestCheckoutFormShown, { offer_uuid: offerUuid, mode })
  }

  const switchMode = (next: Mode) => {
    setMode(next)
    setError('')
    track(AnalyticsEvent.GuestCheckoutModeToggled, { direction: next === 'login' ? 'to_login' : 'to_signup' })
  }

  const emailValid = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(email)
  const passwordValid = mode === 'login' ? password.length > 0 : validatePasswordStrength(password).isValid

  const doLogin = async (): Promise<boolean> => {
    const res = await signIn('credentials', { redirect: false, email, password })
    if (res?.error) {
      let message = t('auth.wrong_email_password')
      try {
        const parsed = JSON.parse(res.error)
        if (parsed?.message) message = parsed.message
      } catch {
        // keep default message
      }
      setError(message)
      return false
    }
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!emailValid) {
      setError(t('validation.invalid_email'))
      return
    }
    if (!passwordValid) {
      setError(mode === 'login' ? t('validation.required') : t('auth.password_requirements_not_met'))
      return
    }
    if (turnstileRequired && !turnstileToken) {
      setError(t('auth.turnstile_failed'))
      return
    }

    setIsSubmitting(true)
    try {
      if (mode === 'login') {
        // Login has no server-side gateway to verify inline (NextAuth's
        // credentials provider) — pre-verify here, same as login.tsx.
        if (!(await checkRecaptcha('GUEST_CHECKOUT_LOGIN'))) {
          setError(t('auth.turnstile_failed'))
          return
        }
        const ok = await doLogin()
        if (ok) onAuthenticated()
        else turnstileRef.current?.reset()
        return
      }

      // mode === 'signup' — /api/signup verifies the token inline (single
      // verification; a v3 token can only be checked once), so just fetch
      // it here and pass it along, same as turnstileToken below.
      const recaptchaToken = await getRecaptchaToken('GUEST_CHECKOUT_SIGNUP')
      const res = await signup({
        email,
        password,
        username: generateUsernameFromEmail(email),
        org_slug: orgslug,
        org_id: String(orgId),
        turnstileToken,
        recaptchaToken,
      })
      const body = await res.json().catch(() => ({}))

      if (res.status !== 200) {
        // Backend returns a deliberately generic conflict message for an
        // already-used email/username (anti-enumeration) — treat any 4xx
        // here as "you may already have an account" rather than guessing.
        if (res.status === 400 || res.status === 409) {
          setError(t('payments.guest_checkout.maybe_registered_message'))
          setMode('login')
        } else {
          setError(getErrorMessage(body?.detail, t('common.something_went_wrong')))
        }
        turnstileRef.current?.reset()
        return
      }

      // Single-tenant, non-SaaS deployment: email_verified is set true
      // immediately on create_user, so login right after signup always
      // succeeds — but handle the defensive case anyway (SaaS mode) rather
      // than assume.
      if (body?.email_verified === false) {
        setError('')
        setAccountJustCreated(true)
        return
      }

      setAccountJustCreated(true)
      const ok = await doLogin()
      if (ok) {
        onAuthenticated()
      } else {
        // Account exists server-side but the immediate login failed
        // (network blip, etc.) — let the user retry without re-submitting
        // signup (which would now 409).
        setMode('login')
      }
    } catch {
      setError(t('common.something_went_wrong'))
      turnstileRef.current?.reset()
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mt-1">
      <p className="mb-3 text-sm font-semibold text-[#1c1c1c]">Crea tu cuenta para continuar</p>
      <div className="flex rounded-xl bg-[#1c1c1c]/5 p-1 mb-4 text-sm font-bold">
        <button
          type="button"
          onClick={() => switchMode('signup')}
          className={`flex-1 py-2 rounded-lg transition-colors ${mode === 'signup' ? 'bg-white text-[#1c1c1c] shadow-sm' : 'text-[#1c1c1c]/50'}`}
        >
          {t('payments.guest_checkout.create_tab_label')}
        </button>
        <button
          type="button"
          onClick={() => switchMode('login')}
          className={`flex-1 py-2 rounded-lg transition-colors ${mode === 'login' ? 'bg-white text-[#1c1c1c] shadow-sm' : 'text-[#1c1c1c]/50'}`}
        >
          {t('payments.guest_checkout.login_tab_label')}
        </button>
      </div>

      {accountJustCreated && (
        <p className="text-xs text-center text-[#007b8d] mb-3">
          {t('payments.guest_checkout.account_created_continue')}
        </p>
      )}

      {error && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-xl text-red-600 p-3 mb-3 text-xs">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-2.5">
        <input
          type="email"
          required
          autoComplete="email"
          placeholder={t('auth.email')}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-[#fbfeff] text-[#1c1c1c] rounded-xl px-3.5 border border-[#1c1c1c]/15 h-[46px] text-sm outline-none focus:ring-2 focus:ring-[#00a9bf]/20 focus:border-[#00a9bf] transition-all"
        />
        <div>
          <input
            type="password"
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            placeholder={t('auth.password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-[#fbfeff] text-[#1c1c1c] rounded-xl px-3.5 border border-[#1c1c1c]/15 h-[46px] text-sm outline-none focus:ring-2 focus:ring-[#00a9bf]/20 focus:border-[#00a9bf] transition-all"
          />
          {mode === 'signup' && <PasswordStrengthIndicator password={password} showRequirements={false} />}
        </div>

        <TurnstileWidget ref={turnstileRef} onToken={setTurnstileToken} className="flex justify-center pt-1" />

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full flex items-center justify-center gap-2 py-3.5 px-5 rounded-xl font-black text-sm bg-[#00a9bf] hover:bg-[#008da0] text-white shadow-[0_8px_18px_rgba(0,169,191,0.25)] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <Loader2 size={15} className="animate-spin" />
          ) : mode === 'signup' ? (
            t('payments.guest_checkout.cta_create_and_pay')
          ) : (
            t('payments.guest_checkout.cta_login_and_pay')
          )}
        </button>
      </form>

      <p className="text-xs text-center text-[#1c1c1c]/50 mt-3">
        <LockKeyhole size={11} className="inline mr-1 text-[#00a9bf]" />
        {t('payments.guest_checkout.stuck_fallback_message')}{' '}
        <Link
          href={getUriWithOrg(orgslug, `/login?redirect=/store/offers/${offerUuid}`)}
          className="underline text-[#007b8d] hover:text-[#00a9bf]"
          onClick={() => track(AnalyticsEvent.GuestCheckoutStuckFallbackShown, { offer_uuid: offerUuid })}
        >
          {t('payments.guest_checkout.stuck_fallback_link')}
        </Link>
      </p>
    </div>
  )
}
