import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useOrg, useOrgMembership } from '@components/Contexts/OrgContext'
import { getUriWithOrg, withBasePathOnRelative } from '@services/config/config'
import { getOffersByResource } from '@services/payments/offers'
import { LogIn, LogOut, ShoppingCart, Lock, UserPlus } from 'lucide-react'
import { removeCourse, startCourse } from '@services/courses/activity'
import { revalidateTags } from '@services/utils/ts/requests'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import Link from 'next/link'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'
import { useTranslation } from 'react-i18next'

interface CourseRun {
  status: string
  course_id: string
}

interface Course {
  id: string
  course_uuid: string
  trail?: {
    runs: CourseRun[]
  }
  chapters?: Array<{
    name: string
    activities: Array<{
      activity_uuid: string
      name: string
      activity_type: string
    }>
  }>
}

interface CourseActionsMobileProps {
  courseuuid: string
  orgslug: string
  course: Course & {
    org_id: number
  }
  trailData?: any
}

const CourseActionsMobile = ({ courseuuid, orgslug, course, trailData }: CourseActionsMobileProps) => {
  const router = useRouter()
  const session = useLHSession() as any
  const { isUserPartOfTheOrg } = useOrgMembership()
  const org = useOrg() as any
  const queryClient = useQueryClient()
  const { track } = useLHAnalytics('learner')
  const [isActionLoading, setIsActionLoading] = useState(false)
  // Clean up course UUID by removing 'course_' prefix if it exists
  const cleanCourseUuid = course.course_uuid?.replace('course_', '');
  const resourceUuid = cleanCourseUuid ? `course_${cleanCourseUuid}` : null;
    const { t } = useTranslation()

  const isStarted = trailData?.runs?.find(
    (run: any) => {
      const cleanRunCourseUuid = run.course?.course_uuid?.replace('course_', '');
      return cleanRunCourseUuid === cleanCourseUuid;
    }
  ) ?? false;

  // Public endpoint — no auth needed, works for unauthenticated visitors too
  const { data: offersResult, isLoading } = useQuery({
    queryKey: ['offers', 'by-resource', org?.id, resourceUuid],
    queryFn: () => getOffersByResource(org.id, resourceUuid!),
    enabled: !!org && !!resourceUuid,
    staleTime: 60_000,
  });
  const linkedOffers: any[] = offersResult?.data ?? [];

  const handleCourseAction = async () => {
    if (!session.data?.user) {
      track(AnalyticsEvent.CourseSignupPrompted, {
        reason: 'unauthenticated',
        intended_action: isStarted ? 'leave_course' : 'start_course',
      })
      router.push(getUriWithOrg(orgslug, '/signup'))
      return
    }

    // Check if user is part of the organization
    if (!isUserPartOfTheOrg) {
      router.push(getUriWithOrg(orgslug, '/signup'))
      return
    }

    setIsActionLoading(true)
    try {
      if (isStarted) {
        await removeCourse('course_' + courseuuid, orgslug, session.data?.tokens?.access_token)
        await revalidateTags(['courses'], orgslug)
        queryClient.invalidateQueries({ queryKey: queryKeys.trail.org(org.id) })
        track(AnalyticsEvent.CourseLeft, { course_uuid: cleanCourseUuid })
        router.refresh()
      } else {
        await startCourse('course_' + courseuuid, orgslug, session.data?.tokens?.access_token)
        await revalidateTags(['courses'], orgslug)
        queryClient.invalidateQueries({ queryKey: queryKeys.trail.org(org.id) })
        track(AnalyticsEvent.CourseStarted, {
          course_uuid: cleanCourseUuid,
          total_activities: course.chapters?.reduce((acc: number, chapter: any) => acc + chapter.activities.length, 0) || 0,
          has_offers: linkedOffers.length > 0,
        })

        // Get the first activity from the first chapter
        const firstChapter = course.chapters?.[0]
        const firstActivity = firstChapter?.activities?.[0]
        
        if (firstActivity) {
          // Redirect to the first activity
          await revalidateTags(['activities'], orgslug)
          router.push(
            getUriWithOrg(orgslug, '') +
            `/course/${courseuuid}/activity/${firstActivity.activity_uuid.replace('activity_', '')}`
          )
        } else {
          router.refresh()
        }
      }
    } catch (error) {
      console.error('Failed to perform course action:', error)
    } finally {
      setIsActionLoading(false)
      await revalidateTags(['courses'], orgslug)
    }
  }

  if (isLoading) {
    return (
      <div className="fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-sm shadow-[0_-4px_16px_rgba(0,0,0,0.08)] pt-3 px-4" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 0.75rem)' }}>
        <div className="animate-pulse h-16 bg-gray-100 rounded-lg" />
      </div>
    )
  }

  // Show join organization prompt for authenticated users who are not part of the org
  if (session.data?.user && !isUserPartOfTheOrg) {
    return (
      <div
        className="fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-sm shadow-[0_-4px_16px_rgba(0,0,0,0.08)] outline outline-1 outline-neutral-200/40 rounded-t-xl overflow-hidden p-4"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 1rem)' }}
      >
        <div className="flex flex-col space-y-3">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-amber-800" />
              <span className="text-amber-800 text-sm font-semibold">{t('courses.join_org_required')}</span>
            </div>
            <p className="text-amber-700 text-xs mt-1">
              {t('courses.join_org_required_description')}
            </p>
          </div>
          <a
            href={withBasePathOnRelative(getUriWithOrg(orgslug, '/signup'))}
            className="w-full py-2 px-4 rounded-lg bg-neutral-900 text-white font-semibold text-sm hover:bg-neutral-800 transition-colors flex items-center justify-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            {t('courses.join_organization')}
          </a>
        </div>
      </div>
    )
  }

  return (
    <div
      className="fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-sm shadow-[0_-4px_16px_rgba(0,0,0,0.08)] outline outline-1 outline-neutral-200/40 rounded-t-xl overflow-hidden p-4"
      style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 1rem)' }}
    >
      <div className="flex flex-col space-y-4">
        {linkedOffers.length > 0 ? (() => {
          const offer = linkedOffers[0];
          const formattedPrice = offer?.amount != null
            ? new Intl.NumberFormat('en-US', { style: 'currency', currency: offer.currency ?? 'USD' }).format(offer.amount)
            : null;
          const storeHref = org?.slug ? getUriWithOrg(org.slug, `/store/offers/${offer.offer_id}`) : '#';

          return (
            <div className="space-y-3">
              {isStarted ? (
                <>
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                      <span className="text-green-800 text-sm font-semibold">{t('courses.you_own_this_course')}</span>
                    </div>
                  </div>
                  <button
                    onClick={handleCourseAction}
                    disabled={isActionLoading}
                    className="w-full py-2 px-4 rounded-lg bg-red-500 text-white font-semibold text-sm hover:bg-red-600 transition-colors flex items-center justify-center gap-2 disabled:bg-red-400"
                  >
                    {isActionLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <LogOut className="w-4 h-4" />
                        {t('courses.leave_course')}
                      </>
                    )}
                  </button>
                </>
              ) : (
                <>
                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <Lock className="w-4 h-4 text-gray-600 shrink-0" />
                        <span className="text-gray-900 text-sm font-semibold truncate">{offer.offer_name}</span>
                      </div>
                      {formattedPrice && (
                        <div className="text-right shrink-0 leading-none">
                          <span className="text-2xl font-black text-gray-900">{formattedPrice}</span>
                          {offer.offer_type === 'subscription' && (
                            <span className="text-xs text-gray-400 ml-0.5">/mo</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <Link href={storeHref}>
                    <button
                      onClick={() => track(AnalyticsEvent.CourseOfferCtaClicked, {
                        offer_uuid: offer.offer_uuid,
                        offer_type: offer.offer_type,
                        amount: offer.amount,
                        currency: offer.currency,
                      })}
                      className="w-full py-2 px-4 rounded-lg bg-[#00a9bf] text-white font-semibold text-sm hover:bg-[#008da0] transition-colors flex items-center justify-center gap-2"
                    >
                      <ShoppingCart className="w-4 h-4" />
                      {formattedPrice ? 'Get Access' : 'Purchase Course'}
                    </button>
                  </Link>
                </>
              )}
            </div>
          );
        })() : (
          <button
            onClick={handleCourseAction}
            disabled={isActionLoading}
            className={`w-full py-2 px-4 rounded-lg font-semibold text-sm transition-colors flex items-center justify-center gap-2 ${
              isStarted
                ? 'bg-red-500 text-white hover:bg-red-600 disabled:bg-red-400'
                : 'bg-neutral-900 text-white hover:bg-neutral-800 disabled:bg-neutral-700'
            }`}
          >
            {isActionLoading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : !session.data?.user ? (
              <>
                <LogIn className="w-4 h-4" />
                {t('onboarding.welcome.get_started')}
              </>
            ) : isStarted ? (
              <>
                <LogOut className="w-4 h-4" />
                {t('courses.leave_course')}
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                {t('courses.start_course')}
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

export default CourseActionsMobile 