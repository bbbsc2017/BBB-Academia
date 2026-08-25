'use client'
import React, { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import GeneralWrapperStyled from '@components/Objects/StyledElements/Wrappers/GeneralWrapper'
import { getUriWithOrg } from '@services/config/config'
import { getCourseThumbnailMediaDirectory } from '@services/media/media'
import { getOfferCheckoutSession } from '@services/payments/offers'
import { fromApiProviderValue, getPaymentProvider } from '@services/payments/providers'
import {
  ArrowLeft, RefreshCcw, SquareCheck, Sparkles, BookOpen,
  Mic, Puzzle, AlertCircle, Loader2, CheckCircle2,
  ShieldCheck, LockKeyhole, CreditCard, CircleCheckBig
} from 'lucide-react'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useLHAnalytics, useTrackView, AnalyticsEvent } from '@services/analytics'
import { meaningfulMessage } from '@lib/errors/classify'
import toast from 'react-hot-toast'
import GuestCheckoutPanel from '@components/Payments/GuestCheckoutPanel'

interface Resource {
  resource_uuid: string
  resource_type: string
  name: string
  description: string
  thumbnail_image: string
  org_uuid: string
}

interface OfferDetailClientProps {
  orgslug: string
  orgId: number
  offerUuid: string
  offer: any
  access_token: string | null
}

function resourceIcon(type: string, size = 14) {
  switch (type) {
    case 'course': return <BookOpen size={size} className="text-[#00a9bf]" />
    case 'podcast': return <Mic size={size} className="text-[#00a9bf]" />
    default: return <Puzzle size={size} className="text-[#00a9bf]" />
  }
}

function stripTypePrefix(uuid: string): string {
  return uuid.replace(/^[a-z]+_/, '')
}

function getResourceUrl(orgslug: string, resource: Resource): string | null {
  const id = stripTypePrefix(resource.resource_uuid)
  switch (resource.resource_type) {
    case 'course': return getUriWithOrg(orgslug, `/course/${id}`)
    case 'podcast': return getUriWithOrg(orgslug, `/podcast/${id}`)
    case 'playground': return getUriWithOrg(orgslug, `/playground/${id}`)
    default: return null
  }
}

function ResourceCard({ resource, orgslug }: { resource: Resource; orgslug: string }) {
  const src = resource.thumbnail_image && resource.resource_type === 'course'
    ? getCourseThumbnailMediaDirectory(resource.org_uuid, resource.resource_uuid, resource.thumbnail_image)
    : null

  const url = getResourceUrl(orgslug, resource)
  const card = (
    <div className={`bg-white/65 backdrop-blur-md border border-white/80 rounded-2xl overflow-hidden flex flex-col shadow-[0_12px_35px_rgba(28,28,28,0.07)] ${url ? 'cursor-pointer hover:-translate-y-0.5 hover:border-[#00a9bf]/35 hover:shadow-[0_18px_40px_rgba(0,169,191,0.12)] transition-all duration-300' : ''}`}>
      {/* Thumbnail */}
      <div
        className="w-full aspect-video overflow-hidden bg-[#f4fbfc]"
        style={{
          backgroundImage: src ? `url(${src})` : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        {!src && (
          <div className="w-full h-full flex items-center justify-center bg-[#e6f8fa]">
            {resourceIcon(resource.resource_type, 28)}
          </div>
        )}
        <div className="p-2">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-[#1c1c1c]/75 backdrop-blur-sm rounded-full px-2 py-0.5 capitalize">
            {resourceIcon(resource.resource_type, 10)}
            {resource.resource_type}
          </span>
        </div>
      </div>
      {/* Details */}
      <div className="p-4 flex flex-col gap-1">
        <p className="font-bold text-sm text-[#1c1c1c] leading-snug">{resource.name}</p>
        {resource.description && (
          <p className="text-xs text-[#1c1c1c]/60 leading-relaxed line-clamp-2">{resource.description}</p>
        )}
      </div>
    </div>
  )

  return url ? <Link href={url}>{card}</Link> : card
}

export default function OfferDetailClient({ orgslug, orgId, offerUuid, offer, access_token }: OfferDetailClientProps) {
  const session = useLHSession() as any
  const token = session?.data?.tokens?.access_token ?? access_token
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const { track } = useLHAnalytics('learner')
  // Set by GuestCheckoutPanel right after signup/login succeeds. `token` is
  // still the stale (null) value captured in that render, so checkout can't
  // be triggered synchronously — this flag lets the effect below fire it as
  // soon as the next render picks up the freshly authenticated session.
  const autoCheckoutRef = useRef(false)

  useTrackView(
    AnalyticsEvent.OfferViewed,
    {
      offer_type: offer?.offer_type,
      included_resources_count: offer?.included_resources?.length ?? 0,
      is_authenticated: !!token,
    },
    !!offer,
    'learner',
  )

  if (!offer) {
    return (
      <GeneralWrapperStyled>
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <AlertCircle size={32} className="text-gray-300 mb-3" />
          <h2 className="font-bold text-gray-600 text-lg">Offer not found</h2>
          <Link href={getUriWithOrg(orgslug, '/store')} className="mt-4 text-sm text-[#00a9bf] hover:underline">
            ← Back to store
          </Link>
        </div>
      </GeneralWrapperStyled>
    )
  }

  const isSubscription = offer.offer_type === 'subscription'
  const benefits: string[] = offer.benefits
    ? offer.benefits.split(',').map((b: string) => b.trim()).filter(Boolean)
    : []
  const resources: Resource[] = offer.included_resources ?? []
  const providerId = fromApiProviderValue(offer?.provider)
  const providerDef = providerId ? getPaymentProvider(providerId) : null

  const handleCheckout = async () => {
    if (!token) {
      // Should be unreachable now that anonymous visitors get
      // GuestCheckoutPanel instead of this button — kept as a defensive
      // fallback rather than assuming the panel always renders first.
      track(AnalyticsEvent.CheckoutLoginRedirected, { redirect_target: `/store/offers/${offerUuid}` })
      router.push(getUriWithOrg(orgslug, `/login?redirect=/store/offers/${offerUuid}`))
      return
    }
    track(AnalyticsEvent.OfferCheckoutStarted, {
      offer_uuid: offerUuid,
      offer_type: offer.offer_type,
      amount: offer.amount,
      currency: offer.currency,
    })
    setLoading(true)
    try {
      const redirectUri = window.location.href
      const result = await getOfferCheckoutSession(orgId, offerUuid, redirectUri, token)
      const url = result?.data?.checkout_url
      if (url) {
        track(AnalyticsEvent.CheckoutSessionCreated, { offer_type: offer.offer_type, amount: offer.amount })
        window.location.href = url
      } else {
        track(AnalyticsEvent.CheckoutSessionFailed, { failure_reason: 'no_checkout_url' })
        toast.error('Could not start checkout. Please try again.')
      }
    } catch (err) {
      track(AnalyticsEvent.CheckoutSessionFailed, { failure_reason: 'exception' })
      toast.error(meaningfulMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Fires once GuestCheckoutPanel authenticates a previously anonymous
  // visitor: `token` flips from falsy to truthy on the next render, at
  // which point handleCheckout() (re-created with the fresh token in its
  // closure) is safe to call.
  useEffect(() => {
    if (token && autoCheckoutRef.current) {
      autoCheckoutRef.current = false
      handleCheckout()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <div className="relative w-full bg-transparent">
      {/* One continuous transparent grid layer; it is fixed to the viewport so
          it never restarts at a section boundary or creates visible seams. */}
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(0,169,191,0.11) 1px, transparent 1px), linear-gradient(90deg, rgba(0,169,191,0.11) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />
      <GeneralWrapperStyled>
        <div className="relative z-10">
        <Link
          href={getUriWithOrg(orgslug, '/store')}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#1c1c1c]/55 hover:text-[#00a9bf] transition-colors mb-6"
        >
          <ArrowLeft size={15} /> Volver a la tienda
        </Link>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_390px] gap-7 xl:gap-12 pb-10">
          {/* Left col */}
          <div className="space-y-7 min-w-0">
            {/* Offer header */}
            <div className="rounded-3xl border border-white/85 bg-white/70 backdrop-blur-xl p-6 sm:p-8 shadow-[0_18px_50px_rgba(28,28,28,0.08)] overflow-hidden relative">
              <div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-[#00a9bf]/20 blur-2xl" />
              <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-[#00a9bf]/45 to-transparent" />
              <div className="relative">
              <div className="flex items-center gap-2 mb-4">
                {isSubscription ? (
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#007b8d] bg-[#00a9bf]/10 rounded-full px-3 py-1.5">
                    <RefreshCcw size={12} /> Suscripción
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#007b8d] bg-[#00a9bf]/10 rounded-full px-3 py-1.5">
                    <SquareCheck size={12} /> Pago único
                  </span>
                )}
              </div>
              <h1 className="max-w-3xl text-3xl sm:text-4xl font-black text-[#1c1c1c] tracking-tight leading-[1.08]">{offer.name}</h1>
              <p className="max-w-3xl mt-4 text-[#1c1c1c]/70 leading-relaxed text-base sm:text-lg">{offer.description}</p>
              <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[#1c1c1c]/70">
                <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={16} className="text-[#00a9bf]" /> Acceso inmediato tras el pago</span>
                <span className="inline-flex items-center gap-1.5"><ShieldCheck size={16} className="text-[#00a9bf]" /> Pago seguro</span>
              </div>
              </div>
            </div>

            {/* Included courses/resources */}
            {resources.length > 0 && (
              <div>
                <h2 className="text-sm font-black text-[#1c1c1c] uppercase tracking-wide mb-4">
                  Incluye · {resources.length} {resources.length === 1 ? 'recurso' : 'recursos'}
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {resources.map((r) => (
                    <ResourceCard key={r.resource_uuid} resource={r} orgslug={orgslug} />
                  ))}
                </div>
              </div>
            )}

            {/* Benefits */}
            {benefits.length > 0 && (
              <div className="bg-white/65 backdrop-blur-xl rounded-2xl border border-white/85 p-5 sm:p-6 shadow-[0_12px_35px_rgba(28,28,28,0.07)]">
                <h2 className="text-sm font-black text-[#1c1c1c] uppercase tracking-wide mb-4">Lo que obtienes</h2>
                <ul className="space-y-2.5">
                  {benefits.map((b, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-[#1c1c1c]/75">
                      <Sparkles size={15} className="text-[#00a9bf] mt-0.5 shrink-0" />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Right col — sticky pricing card */}
          <div>
            <div className="rounded-3xl border border-white/90 bg-white/75 backdrop-blur-xl p-5 sm:p-6 shadow-[0_22px_55px_rgba(0,169,191,0.18)] xl:sticky xl:top-24 overflow-hidden relative">
              <div aria-hidden="true" className="absolute -right-14 -top-14 h-36 w-36 rounded-full bg-[#00a9bf]/15 blur-2xl" />
              <div className="relative">
              <div className="flex items-start justify-between gap-3 pb-5 border-b border-[#1c1c1c]/10">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#00a9bf]">Inscripción</p>
                  <h2 className="mt-1 text-xl font-black text-[#1c1c1c]">Finaliza tu compra</h2>
                </div>
                <div className="h-10 w-10 rounded-xl bg-[#00a9bf]/10 flex items-center justify-center shrink-0">
                  <CreditCard size={20} className="text-[#00a9bf]" />
                </div>
              </div>
              {/* Price */}
              <div className="py-5">
                <p className="text-xs text-[#1c1c1c]/55 font-semibold mb-1">
                  {offer.price_type === 'customer_choice' ? 'Paga lo que quieras (mínimo)' : isSubscription ? 'Precio de suscripción' : 'Precio total'}
                </p>
                <div className="text-4xl font-black text-[#1c1c1c] tracking-tight">
                  {new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: offer.currency,
                  }).format(offer.amount)}
                </div>
                {isSubscription && (
                  <p className="text-sm text-[#00a9bf] font-bold mt-0.5">Cobro recurrente</p>
                )}
                {providerDef && (
                  <p className="text-xs text-[#1c1c1c]/55 mt-2">{providerDef.checkoutCopy}</p>
                )}
              </div>

              {/* Checkout */}
              {token ? (
                <button
                  onClick={handleCheckout}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-3.5 px-5 rounded-xl font-black text-sm bg-[#00a9bf] hover:bg-[#008da0] text-white shadow-[0_8px_18px_rgba(0,169,191,0.25)] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <><Loader2 size={16} className="animate-spin" /> Preparando pago…</>
                  ) : (
                    <>{isSubscription ? 'Suscribirme ahora' : 'Inscribirme y pagar'}</>
                  )}
                </button>
              ) : (
                <GuestCheckoutPanel
                  orgslug={orgslug}
                  orgId={orgId}
                  offerUuid={offerUuid}
                  onAuthenticated={() => { autoCheckoutRef.current = true }}
                />
              )}

              {/* Resource summary */}
              {resources.length > 0 && (
                <div className="mt-5 pt-4 border-t border-[#1c1c1c]/10">
                  <p className="text-xs font-bold text-[#1c1c1c]/55 uppercase tracking-wide mb-3">Tu inscripción incluye</p>
                  <div className="space-y-2">
                    {resources.map((r) => {
                      const src = r.thumbnail_image && r.resource_type === 'course'
                        ? getCourseThumbnailMediaDirectory(r.org_uuid, r.resource_uuid, r.thumbnail_image)
                        : null
                      return (
                        <div key={r.resource_uuid} className="flex items-center gap-2.5">
                          <div
                            className="w-9 h-9 rounded-lg overflow-hidden bg-[#e6f8fa] shrink-0 flex items-center justify-center"
                            style={{
                              backgroundImage: src ? `url(${src})` : undefined,
                              backgroundSize: 'cover',
                              backgroundPosition: 'center',
                            }}
                          >
                            {!src && resourceIcon(r.resource_type, 13)}
                          </div>
                          <p className="text-xs font-semibold text-[#1c1c1c]/80 truncate">{r.name}</p>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Trust signals */}
              <div className="mt-5 pt-4 border-t border-[#1c1c1c]/10 space-y-2">
                <p className="text-xs text-[#1c1c1c]/55 flex items-center gap-2"><LockKeyhole size={13} className="text-[#00a9bf]" /> Checkout seguro procesado por {providerDef?.name ?? 'tu proveedor de pago'}</p>
                {isSubscription && <p className="text-xs text-[#1c1c1c]/55 flex items-center gap-2"><CircleCheckBig size={13} className="text-[#00a9bf]" /> Cancela cuando quieras</p>}
                <p className="text-xs text-[#1c1c1c]/55 flex items-center gap-2"><CircleCheckBig size={13} className="text-[#00a9bf]" /> Acceso inmediato después del pago</p>
              </div>
              </div>
            </div>
          </div>
        </div>
        </div>
      </GeneralWrapperStyled>
    </div>
  )
}
