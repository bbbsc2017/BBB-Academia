'use client'
import React from 'react'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useCourses } from '@/hooks/queries/useCourses'
import CourseThumbnail from '@components/Objects/Thumbnails/CourseThumbnail'
import { useTranslation } from 'react-i18next'

interface RelatedCoursesCarouselProps {
  orgslug: string
  /** The course currently being viewed — excluded from the list. */
  currentCourseUuid: string
}

/**
 * "Other courses on this site" — signed-in visitors only (by design: this
 * renders nothing at all for anonymous visitors, not just a filtered list).
 * Reuses the same public+published semantics as the org's own course catalog
 * (Course.public && Course.published — see EditCourseAccess's "Acceso al
 * curso" toggle) rather than inventing a separate visibility flag.
 */
function RelatedCoursesCarousel({ orgslug, currentCourseUuid }: RelatedCoursesCarouselProps) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const isAuthenticated = !!session?.data?.user

  const { data: coursesData } = useCourses(orgslug)
  const allCourses: any[] = Array.isArray(coursesData) ? coursesData : []

  const otherCourses = allCourses.filter(
    (c) => c.course_uuid !== currentCourseUuid && c.public === true && c.published === true
  )

  if (!isAuthenticated || otherCourses.length === 0) {
    return null
  }

  return (
    <div className="w-full mt-8 mb-4">
      <h2 className="py-5 text-xl md:text-2xl font-bold">{t('courses.other_courses', 'Other courses')}</h2>
      <div className="flex gap-4 overflow-x-auto pb-3 -mx-1 px-1 snap-x snap-mandatory">
        {otherCourses.map((c) => (
          <div key={c.course_uuid} className="w-[260px] md:w-[280px] flex-shrink-0 snap-start">
            <CourseThumbnail course={c} orgslug={orgslug} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default RelatedCoursesCarousel
