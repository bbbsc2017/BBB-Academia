'use client'
import React, { useEffect, useState } from 'react'
import CopilotBubble from '@components/Copilot/CopilotBubble'
import Image from 'next/image'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import { getUriWithOrg, withBasePath } from '@services/config/config'
import { fetchRAGChatSessions, RAGChatSession } from '@services/ai/ai'
import { HeaderProfileBox } from '@components/Security/HeaderProfileBox'
import MenuLinks from './OrgMenuLinks'
import { getOrgLogoMediaDirectory } from '@services/media/media'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useOrg } from '@components/Contexts/OrgContext'
import { SearchBar } from '@components/Objects/Search/SearchBar'
import { usePathname } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import useAdminStatus from '@components/Hooks/useAdminStatus'
import {
  Question,
  Globe,
  ChatCircleDots,
  ChatCircle,
  SquaresFour,
  ChalkboardSimple,
  Signpost,
} from '@phosphor-icons/react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@components/ui/dropdown-menu"
import { FeedbackModal } from '@components/Objects/Modals/FeedbackModal'
import { DASHBOARD_MENU_ITEMS, DashboardMenuItem } from '@/lib/dashboard-menu-items'
import { isFeatureAvailable } from '@services/plans/plans'
import { getMenuColorClasses } from '@services/utils/ts/colorUtils'
import AuthenticatedClientElement from '@components/Security/AuthenticatedClientElement'
import { useJoinBannerVisible, JOIN_BANNER_HEIGHT } from '@components/Objects/Banners/OrgJoinBanner'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@components/ui/tooltip'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'

const hexToRgba = (hex: string, alpha: number): string => {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return 'rgba(0, 169, 191, 0.12)'
  const numeric = parseInt(hex.slice(1), 16)
  const red = (numeric >> 16) & 255
  const green = (numeric >> 8) & 255
  const blue = numeric & 255
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

export const OrgMenu = (props: any) => {
  const orgslug = props.orgslug
  const session = useLHSession() as any;
  const _access_token = session?.data?.tokens?.access_token;
  const org = useOrg() as any;
  const [isMenuOpen, setIsMenuOpen] = React.useState(false)
  const [isFocusMode, setIsFocusMode] = useState(false)
  const pathname = usePathname()
  const { t } = useTranslation()
  const { rights } = useAdminStatus()
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)
  const { isVisible: isJoinBannerVisible } = useJoinBannerVisible()
  const { track } = useLHAnalytics()

  // Copilot bubble state
  const [bubbleOpen, setBubbleOpen] = useState(false)
  const [bubbleSessionToLoad, setBubbleSessionToLoad] = useState<string | null>(null)
  const [isBubbleMode, setIsBubbleMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    const stored = localStorage.getItem('copilot-bubble-mode')
    return stored === 'true'
  })

  const toggleBubbleMode = (value: boolean) => {
    setIsBubbleMode(value)
    localStorage.setItem('copilot-bubble-mode', String(value))
    if (!value) setBubbleOpen(false)
  }

  const openBubbleWithSession = (sessionUuid?: string) => {
    if (sessionUuid) setBubbleSessionToLoad(sessionUuid)
    setBubbleOpen(true)
  }
  const topOffset = isJoinBannerVisible ? JOIN_BANNER_HEIGHT : 0

  // Get primary color from org config (v2: customization.general.color, v1: general.color)
  const config = org?.config?.config
  const primaryColor = config?.customization?.general?.color || config?.general?.color || ''
  // The navigation always sits on a light glass surface. Keep its controls
  // readable even when the organization color is a saturated dark tone.
  const colors = getMenuColorClasses(primaryColor || '#00A9BF')
  const navIconClass = 'rounded-full border border-white/25 bg-white/10 text-white shadow-sm transition-all hover:-translate-y-px hover:bg-white/20 hover:border-white/40'
  const navBackground = primaryColor || '#00A9BF'

  // Filter dashboard menu items by resolved_features from API
  const rf = config?.resolved_features
  const visibleDashboardItems = DASHBOARD_MENU_ITEMS.filter((item: DashboardMenuItem) => {
    if (!item.featureKey) return true
    if (rf?.[item.featureKey]) return rf[item.featureKey].enabled
    return isFeatureAvailable(item.featureKey)
  })

  useEffect(() => {
    // Only check focus mode if we're in an activity page
    if (typeof window !== 'undefined' && pathname?.includes('/activity/')) {
      const saved = localStorage.getItem('globalFocusMode');
      setIsFocusMode(saved === 'true');
    } else {
      setIsFocusMode(false);
    }

    // Add storage event listener for cross-window changes
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'globalFocusMode' && pathname?.includes('/activity/')) {
        setIsFocusMode(e.newValue === 'true');
      }
    };

    // Add custom event listener for same-window changes
    const handleFocusModeChange = (e: CustomEvent) => {
      if (pathname?.includes('/activity/')) {
        setIsFocusMode(e.detail.isFocusMode);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('focusModeChange', handleFocusModeChange as EventListener);

    // Cleanup
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('focusModeChange', handleFocusModeChange as EventListener);
    };
  }, [pathname]);

  function toggleMenu() {
    setIsMenuOpen(!isMenuOpen)
  }

  // Only hide menu if we're in an activity page and focus mode is enabled
  if (pathname?.includes('/activity/') && isFocusMode) {
    return null;
  }

  return (
    <>
      <div aria-hidden="true" className="h-[80px]" />
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-8 h-24 rounded-full blur-3xl"
        style={{ zIndex: 'var(--z-behind)', top: topOffset - 8, backgroundColor: hexToRgba(primaryColor, 0.16) }}
      />
      <nav
        aria-label="Top navigation"
        className="fixed left-1/2 -translate-x-1/2 w-[calc(100%-24px)] sm:w-[calc(100%-40px)] max-w-(--breakpoint-2xl) h-[64px] rounded-3xl shadow-[0_20px_45px_-22px_rgba(0,100,115,0.55)]"
        style={{
          zIndex: 'var(--z-nav)',
          background: navBackground,
          top: topOffset + 8
        }}
      >
        <div className="flex items-center justify-between w-full px-4 sm:px-6 lg:px-8 h-full">
          <div className="flex items-center space-x-5 md:w-auto w-full">
            <div className="logo flex md:w-auto w-full justify-center">
              <Link href={getUriWithOrg(orgslug, '/')} className="flex items-center gap-2.5">
                {org?.logo_image ? (
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-white/25 bg-white/15 shadow-sm">
                    <img
                      src={`${getOrgLogoMediaDirectory(org.org_uuid, org?.logo_image)}`}
                      alt={org?.name || 'BBB Learning'}
                      className="size-8 rounded-md object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex size-11 shrink-0 items-center justify-center">
                    <BBBAcademiaLogo />
                  </div>
                )}
                <span className="text-base sm:text-lg font-extrabold tracking-tight text-white">BBB Learning</span>
              </Link>
            </div>
            <div className="hidden md:flex">
              <MenuLinks orgslug={orgslug} compact primaryColor={primaryColor || '#00A9BF'} />
            </div>
          </div>

          {/* Search Section */}
          <div className="hidden md:flex flex-1 justify-center max-w-lg px-4">
            <SearchBar orgslug={orgslug} className="w-full" primaryColor={primaryColor || '#00A9BF'} />
          </div>

          <div className="flex items-center space-x-2">
            {/* Progress / Trail */}
            <AuthenticatedClientElement checkMethod="authentication">
              <div className="hidden md:flex">
                <TooltipProvider delayDuration={0}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link
                        href={getUriWithOrg(orgslug, '/trail')}
                        className={`p-2 ${navIconClass}`}
                        aria-label={t('courses.progress')}
                      >
                        <Signpost size={20} weight="fill" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="text-xs">
                      {t('courses.progress')}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </AuthenticatedClientElement>
            {/* Boards */}
            {rf?.boards?.enabled && (
              <AuthenticatedClientElement checkMethod="authentication">
                <div className="hidden md:flex">
                  <TooltipProvider delayDuration={0}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Link
                          href={getUriWithOrg(orgslug, '/boards')}
                          className={`p-2 ${navIconClass}`}
                          aria-label="Boards"
                        >
                          <ChalkboardSimple size={20} weight="fill" />
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="text-xs">
                        Boards
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </AuthenticatedClientElement>
            )}
            {/* AI Copilot */}
            {rf?.ai?.enabled && config?.admin_toggles?.ai?.copilot_enabled !== false && (
              <AuthenticatedClientElement checkMethod="authentication">
                <div className="hidden md:flex">
                  <CopilotMenuButton
                    orgslug={orgslug}
                    iconBtnClass={colors.iconBtn}
                    isBubbleMode={isBubbleMode}
                    onToggleBubbleMode={toggleBubbleMode}
                    bubbleOpen={bubbleOpen}
                    onOpenBubble={openBubbleWithSession}
                  />
                </div>
              </AuthenticatedClientElement>
            )}
            {/* Dashboard Dropdown - Only visible to admins */}
            {session?.status === 'authenticated' && rights?.dashboard?.action_access && (
              <div className="hidden md:flex">
                <DropdownMenu>
                  <TooltipProvider delayDuration={0}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <button
                            className={`p-2 ${navIconClass}`}
                            aria-label={t('common.dashboard')}
                          >
                            <SquaresFour size={20} weight="fill" />
                          </button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="text-xs">
                        {t('common.dashboard')}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel className="flex items-center gap-2">
                      <SquaresFour size={16} weight="fill" />
                      <span>{t('common.dashboard')}</span>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {visibleDashboardItems.map((item) => {
                      const IconComponent = item.icon
                      return (
                        <DropdownMenuItem key={item.id} asChild>
                          <Link
                            href={item.href}
                            className="flex items-center gap-2"
                            onClick={() => track(AnalyticsEvent.DashboardEntered, { source: 'org_menu' })}
                          >
                            <IconComponent size={16} weight="fill" />
                            <span>{t(item.labelKey)}</span>
                          </Link>
                        </DropdownMenuItem>
                      )
                    })}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}

            {/* Help Dropdown - Only visible to admins/maintainers/instructors */}
            {session?.status === 'authenticated' && rights?.dashboard?.action_access && (
              <div className="hidden md:flex">
                <DropdownMenu>
                  <TooltipProvider delayDuration={0}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <button
                            className={`p-2 ${navIconClass}`}
                            aria-label={t('common.help')}
                          >
                            <Question size={20} weight="fill" />
                          </button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="text-xs">
                        {t('common.help')}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel className="flex items-center gap-2">
                      <Question size={16} weight="fill" />
                      <span>{t('common.help')}</span>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <a
                        href="https://bbbacademia.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2"
                      >
                        <Globe size={16} weight="fill" />
                        <span>{t('common.help_menu.website')}</span>
                      </a>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => setFeedbackModalOpen(true)}
                      className="flex items-center gap-2"
                    >
                      <ChatCircleDots size={16} weight="fill" />
                      <span>{t('common.help_menu.report_feedback')}</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}

            <div className="hidden md:flex">
              <HeaderProfileBox primaryColor={primaryColor || '#00A9BF'} />
            </div>
            <button
              className={`md:hidden focus:outline-hidden ${colors.text}`}
              onClick={toggleMenu}
            >
              {isMenuOpen ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </nav>
      <div
        className={`fixed inset-x-3 rounded-3xl shadow-[0_20px_45px_-22px_rgba(0,100,115,0.55)] md:hidden transition-all duration-300 ease-in-out ${
          isMenuOpen ? 'opacity-100' : '-top-full opacity-0'
        }`}
        style={{
          zIndex: 'var(--z-nav-menu)',
          top: isMenuOpen ? topOffset + 80 : undefined,
          background: navBackground,
        }}
      >
        <div className="flex flex-col px-4 py-3 space-y-4 justify-center items-center">
          {/* Mobile Search */}
          <div className="w-full px-2">
            <SearchBar orgslug={orgslug} isMobile={true} primaryColor={primaryColor || '#00A9BF'} />
          </div>
          <div className='py-4'>
            <MenuLinks orgslug={orgslug} primaryColor={primaryColor || '#00A9BF'} />
          </div>
          <div className="border-t border-white/20">
            <HeaderProfileBox primaryColor={primaryColor || '#00A9BF'} />
          </div>
        </div>
      </div>

      {/* Feedback Modal */}
      <FeedbackModal
        open={feedbackModalOpen}
        onOpenChange={setFeedbackModalOpen}
        theme="light"
        userName={session?.data?.user?.username}
        userEmail={session?.data?.user?.email}
      />

      {/* Copilot floating bubble */}
      {isBubbleMode && (
        <CopilotBubble
          orgslug={orgslug}
          open={bubbleOpen}
          onOpenChange={setBubbleOpen}
          sessionToLoad={bubbleSessionToLoad}
        />
      )}
    </>
  )
}

const CopilotMenuButton = ({
  orgslug,
  isBubbleMode,
  onToggleBubbleMode,
  bubbleOpen,
  onOpenBubble,
}: {
  orgslug: string
  iconBtnClass: string
  isBubbleMode: boolean
  onToggleBubbleMode: (_v: boolean) => void
  bubbleOpen: boolean
  onOpenBubble: (_sessionUuid?: string) => void
}) => {
  const session = useLHSession() as any
  const accessToken = session?.data?.tokens?.access_token
  const [isOpen, setIsOpen] = useState(false)

  // Only fetch when the dropdown is open — avoids firing on every page load
  const { data: sessions } = useQuery<RAGChatSession[]>({
    queryKey: queryKeys.ai.ragSessions(orgslug),
    queryFn: () => fetchRAGChatSessions(accessToken, orgslug),
    enabled: isOpen && !!accessToken && !!orgslug,
    staleTime: 60_000,
  })

  const recentSessions = (sessions || []).slice(0, 5)

  return (
    <DropdownMenu onOpenChange={setIsOpen}>
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button
                className="relative p-2 rounded-lg transition-colors hover:bg-[#00A9BF]/10"
                aria-label="Copilot"
              >
                <ChatCircle size={20} weight="fill" className="text-[#00A9BF]" />
                {/* Active indicator dot */}
                {isBubbleMode && bubbleOpen && (
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#00A9BF] ring-2 ring-white dark:ring-neutral-900" />
                )}
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="text-xs">
            Copilot
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="flex items-center gap-2">
          <ChatCircle size={16} weight="fill" className="text-[#00A9BF]" />
          <span>Copilot</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {recentSessions.length > 0 ? (
          <>
            {recentSessions.map((s) => (
              isBubbleMode ? (
                <DropdownMenuItem
                  key={s.aichat_uuid}
                  onSelect={() => onOpenBubble(s.aichat_uuid)}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <ChatCircleDots size={14} weight="fill" className="shrink-0 text-neutral-400" />
                  <span className="truncate text-sm">{s.title || 'Untitled'}</span>
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem key={s.aichat_uuid} asChild>
                  <Link href={getUriWithOrg(orgslug, `/copilot?chat=${s.aichat_uuid}`)} className="flex items-center gap-2">
                    <ChatCircleDots size={14} weight="fill" className="shrink-0 text-neutral-400" />
                    <span className="truncate text-sm">{s.title || 'Untitled'}</span>
                  </Link>
                </DropdownMenuItem>
              )
            ))}
            <DropdownMenuSeparator />
          </>
        ) : (
          <div className="px-2 py-3 text-center">
            <p className="text-xs text-neutral-400">No conversations yet</p>
          </div>
        )}

        {/* Primary action */}
        {isBubbleMode ? (
          <DropdownMenuItem
            onSelect={() => onOpenBubble()}
            className="flex items-center gap-2 font-medium cursor-pointer"
          >
            <ChatCircle size={14} weight="fill" className="text-[#00A9BF]" />
            <span>{recentSessions.length > 0 ? 'New conversation' : 'Start a conversation'}</span>
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem asChild>
            <Link href={getUriWithOrg(orgslug, '/copilot')} className="flex items-center gap-2 font-medium">
              <ChatCircle size={14} weight="fill" className="text-[#00A9BF]" />
              <span>{recentSessions.length > 0 ? 'View all conversations' : 'Start a conversation'}</span>
            </Link>
          </DropdownMenuItem>
        )}

        <DropdownMenuSeparator />

        {/* Bubble mode toggle */}
        <button
          onClick={() => onToggleBubbleMode(!isBubbleMode)}
          className="w-full flex items-center justify-between px-2 py-2 rounded-md hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors group"
        >
          <span className="text-xs text-neutral-500 group-hover:text-neutral-700 dark:group-hover:text-neutral-300 transition-colors">
            Open in bubble
          </span>
          <span
            className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors flex-shrink-0 ${
              isBubbleMode ? 'bg-[#00A9BF]' : 'bg-neutral-200 dark:bg-neutral-600'
            }`}
          >
            <span
              className={`inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${
                isBubbleMode ? 'translate-x-3.5' : 'translate-x-0.5'
              }`}
            />
          </span>
        </button>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const BBBAcademiaLogo = () => {
  return (
    <Image
      src={withBasePath('/bbb_academia_logo_white.png')}
      alt="BBB Academia"
      width={40}
      height={40}
      style={{ height: '80%', width: 'auto' }}
      unoptimized
    />
  )
}
