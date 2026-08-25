'use client';
import { use, useEffect, type ReactNode } from "react";
import '@styles/globals.css'
import { SessionGate } from '@components/Contexts/LHSessionContext'
import { OrgMenu } from '@components/Objects/Menus/OrgMenu'
import { useOrg } from '@components/Contexts/OrgContext'
import { OrgJoinBanner, OrgJoinBannerProvider } from '@components/Objects/Banners/OrgJoinBanner'
import { PodcastPlayerProvider } from '@components/Contexts/PodcastPlayerContext'
import dynamic from 'next/dynamic'
const PodcastPlayer = dynamic(() => import('@components/Objects/Podcasts/PodcastPlayer'), { ssr: false })
import { PageViewTracker } from '@components/Analytics/PageViewTracker'
import { usePathname, useSearchParams } from 'next/navigation'
import { getGoogleFontUrl, DEFAULT_FONT } from '@/lib/fonts'
import Image from 'next/image'
import Link from 'next/link'
import { withBasePath } from '@services/config/config'
import { getOrgLogoMediaDirectory } from '@services/media/media'
import {
  MapPin,
  Phone,
  EnvelopeSimple,
  FacebookLogo,
  YoutubeLogo,
  InstagramLogo,
  SpotifyLogo,
  WhatsappLogo,
  LinkedinLogo,
  PaperPlaneTilt,
} from '@phosphor-icons/react'

const SOCIAL_LINKS = [
  { name: 'Facebook', href: 'https://www.instagram.com/bbb_academia', Icon: FacebookLogo },
  { name: 'Youtube', href: 'https://www.youtube.com/@BBBStudentCenter', Icon: YoutubeLogo },
  { name: 'Instagram', href: 'https://www.instagram.com/bbb_academia', Icon: InstagramLogo },
  { name: 'Spotify', href: 'https://open.spotify.com/show/2cc0yNVMG5VcGBNQ30GFdj?si=a04bd769ec14443c', Icon: SpotifyLogo },
  { name: 'Whatsapp', href: 'http://wa.me/573115462972', Icon: WhatsappLogo },
  { name: 'Linkedin', href: 'https://co.linkedin.com/company/bbbsc', Icon: LinkedinLogo },
]

// Helper to convert hex to rgba
const hexToRgba = (hex: string, alpha: number): string => {
  if (!hex || hex.length < 7) return 'transparent'
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function OrgFooter() {
  const org = useOrg() as any
  const primaryColor = org?.config?.config?.customization?.general?.color || org?.config?.config?.general?.color || '#00A9BF'
  const organizationName = org?.name || 'BBB Academia'
  const currentYear = new Date().getFullYear()

  return (
    <footer className="relative isolate mt-14 overflow-hidden border-t border-slate-200/70 bg-white text-slate-700">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 -top-24 size-96 rounded-full blur-3xl"
        style={{ backgroundColor: hexToRgba(primaryColor, 0.16) }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-40 right-0 size-96 rounded-full blur-3xl"
        style={{ backgroundColor: hexToRgba(primaryColor, 0.1) }}
      />

      <div className="relative mx-auto grid w-full max-w-(--breakpoint-2xl) gap-10 px-6 py-12 sm:px-8 lg:grid-cols-[minmax(0,1.2fr)_repeat(2,minmax(0,0.8fr))] lg:px-10">
        <div className="max-w-md">
          <Link href="https://bbbacademia.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-3 rounded-2xl transition-opacity hover:opacity-85">
            <span className="flex size-11 items-center justify-center rounded-xl shadow-sm ring-1 ring-black/5" style={{ backgroundColor: primaryColor }}>
              {org?.logo_image ? (
                <img
                  src={getOrgLogoMediaDirectory(org.org_uuid, org.logo_image)}
                  alt={organizationName}
                  className="size-10 rounded-md object-contain"
                />
              ) : (
                <Image src={withBasePath('/bbb_academia_logo.webp')} alt={organizationName} width={40} height={40} className="size-10 object-contain" />
              )}
            </span>
            <span>
              <span className="block text-base font-bold tracking-tight text-slate-900">BBB Academia</span>
              <span className="block text-xs text-slate-500">Aprendizaje que abre oportunidades</span>
            </span>
          </Link>
          <p className="mt-5 text-sm leading-6 text-slate-500">
            Somos el lugar donde aprender se vuelve una experiencia real. Con un enfoque dinámico y práctico, te ayudamos a desarrollar nuevas habilidades, fortalecer tu confianza y abrir puertas a oportunidades que transforman tu futuro.
          </p>
          <p className="mt-4 text-sm leading-6 font-semibold text-slate-700">
            ¿Listo para aprender sin miedo y avanzar a tu ritmo? ¡Nosotros te acompañamos en cada paso del camino!
          </p>
          <div className="mt-6 flex items-center gap-2">
            {SOCIAL_LINKS.map(({ name, href, Icon }) => (
              <a
                key={name}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={name}
                className="flex size-9 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition-all hover:-translate-y-px hover:text-white"
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = primaryColor; e.currentTarget.style.borderColor = primaryColor }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ''; e.currentTarget.style.borderColor = '' }}
              >
                <Icon size={17} weight="fill" />
              </a>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em]" style={{ color: primaryColor }}>Visítanos</p>
          <nav className="mt-4 flex flex-col gap-3 text-sm text-slate-500">
            <a
              href="https://maps.app.goo.gl/mDyJa9MJDCUYh4HTA"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2.5 transition-colors hover:text-slate-900"
            >
              <MapPin size={18} weight="fill" className="mt-0.5 shrink-0" style={{ color: primaryColor }} />
              <span>Cl. 11 #4-24 4to Piso, Ibagué, Tolima</span>
            </a>
            <a href="http://wa.me/573152165996" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2.5 transition-colors hover:text-slate-900">
              <Phone size={18} weight="fill" className="shrink-0" style={{ color: primaryColor }} />
              <span>+57 315 216 5996</span>
            </a>
            <a href="mailto:info@bbbacademia.com" className="flex items-center gap-2.5 transition-colors hover:text-slate-900">
              <EnvelopeSimple size={18} weight="fill" className="shrink-0" style={{ color: primaryColor }} />
              <span>info@bbbacademia.com</span>
            </a>
          </nav>
          <Link
            href="https://bbbacademia.com/terminos-y-condiciones/"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-5 inline-block text-xs text-slate-400 underline decoration-slate-300 underline-offset-2 transition-colors hover:text-slate-700"
          >
            Términos y condiciones
          </Link>
        </div>

        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em]" style={{ color: primaryColor }}>Únete al Club</p>
          <p className="mt-4 text-sm leading-6 text-slate-500">Suscríbete a nuestro Newsletter</p>
          <form
            className="mt-4 flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50/70 p-1 pl-4 focus-within:border-transparent focus-within:ring-2"
            style={{ ['--tw-ring-color' as any]: hexToRgba(primaryColor, 0.35) }}
            onSubmit={(e) => e.preventDefault()}
          >
            <input
              type="email"
              required
              placeholder="tu@email.com"
              aria-label="Correo electrónico"
              className="w-full min-w-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              aria-label="Suscribirme"
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-white shadow-sm transition hover:-translate-y-px"
              style={{ backgroundColor: primaryColor }}
            >
              <PaperPlaneTilt size={15} weight="fill" />
            </button>
          </form>
        </div>
      </div>

      <div className="relative border-t border-slate-200/70">
        <div className="mx-auto flex w-full max-w-(--breakpoint-2xl) flex-col gap-2 px-6 py-5 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
          <p>© {currentYear} {organizationName}. Todos los derechos reservados.</p>
          <Link href="https://bbbacademia.com/terminos-y-condiciones/" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-slate-600">Términos y condiciones</Link>
        </div>
      </div>
    </footer>
  )
}

function LayoutContent({ children, orgslug }: { children: ReactNode; orgslug: string }) {
  const org = useOrg() as any
  const primaryColor = org?.config?.config?.customization?.general?.color || org?.config?.config?.general?.color || ''
  const customFont = org?.config?.config?.customization?.general?.font || org?.config?.config?.general?.font || ''
  const pathname = usePathname()
  const searchParams = useSearchParams()
  // chrome=none strips the org navigation/footer so this route can be embedded
  // inside another view (e.g. a Resource activity iframe) without duplicate chrome.
  const chromeless = searchParams?.get('chrome') === 'none'

  // Inject Google Font stylesheet into document head
  useEffect(() => {
    if (!customFont || customFont === DEFAULT_FONT) return

    const fontId = `gfont-${customFont.replace(/\s/g, '-')}`
    if (document.getElementById(fontId)) return

    // Add preconnect hints
    const preconnect1 = document.createElement('link')
    preconnect1.rel = 'preconnect'
    preconnect1.href = 'https://fonts.googleapis.com'
    document.head.appendChild(preconnect1)

    const preconnect2 = document.createElement('link')
    preconnect2.rel = 'preconnect'
    preconnect2.href = 'https://fonts.gstatic.com'
    preconnect2.crossOrigin = 'anonymous'
    document.head.appendChild(preconnect2)

    // Add font stylesheet
    const link = document.createElement('link')
    link.id = fontId
    link.rel = 'stylesheet'
    link.href = getGoogleFontUrl(customFont)
    document.head.appendChild(link)

    return () => {
      document.head.removeChild(preconnect1)
      document.head.removeChild(preconnect2)
      const existing = document.getElementById(fontId)
      if (existing) document.head.removeChild(existing)
    }
  }, [customFont])

  const pathParts = pathname?.split('/').filter(Boolean) || []

  // Pages that use a full-bleed layout (no footer)
  const noFooterPaths = ['copilot']
  const isFullBleedPage = noFooterPaths.some((p) => pathParts.includes(p))

  return (
    <div
      className="flex flex-col min-h-screen"
      style={{
        backgroundColor: primaryColor ? hexToRgba(primaryColor, 0.035) : 'transparent',
        backgroundImage: primaryColor
          ? `radial-gradient(circle at 8% 0%, ${hexToRgba(primaryColor, 0.12)}, transparent 26rem), radial-gradient(circle at 92% 18%, ${hexToRgba(primaryColor, 0.07)}, transparent 30rem)`
          : undefined,
        ...(customFont ? { fontFamily: `'${customFont}', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` } : {}),
      }}
    >
      <div
        aria-hidden="true"
        className="site-grid-bg fixed inset-0 pointer-events-none"
        style={{ zIndex: 'var(--z-behind)' }}
      />
      <PageViewTracker />
      {!chromeless && <OrgJoinBanner />}
      {!chromeless && <OrgMenu orgslug={orgslug} />}
      <div className="flex-1 relative" style={{ zIndex: 'var(--z-content)' }}>
        {children}
      </div>
      {!isFullBleedPage && !chromeless && <OrgFooter />}
    </div>
  )
}

export default function RootLayout(
  props: {
    children: ReactNode
    params: Promise<any>
  }
) {
  const params = use(props.params);

  const {
    children
  } = props;

  return (
    <>
      <SessionGate>
      <OrgJoinBannerProvider>
        <PodcastPlayerProvider>
          <LayoutContent orgslug={params?.orgslug}>
            {children}
          </LayoutContent>
          <PodcastPlayer />
        </PodcastPlayerProvider>
      </OrgJoinBannerProvider>
      </SessionGate>
    </>
  )
}
