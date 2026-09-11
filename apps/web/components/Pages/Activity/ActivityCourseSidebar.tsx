'use client'

import { ArrowRight, Backpack, Check, FileText, ListTree, PlayCircle, StickyNote } from 'lucide-react'
import Link from 'next/link'
import React from 'react'
import { useTranslation } from 'react-i18next'
import { getUriWithOrg } from '@services/config/config'

interface Props {
  course: any
  currentActivityId: string
  orgslug: string
  trailData?: any
}

export default function ActivityCourseSidebar({ course, currentActivityId, orgslug, trailData }: Props) {
  const { t } = useTranslation()
  const courseId = course.course_uuid?.replace('course_', '')
  const currentId = currentActivityId.replace('activity_', '')
  const cleanCourseId = course.course_uuid?.replace('course_', '')
  const run = trailData?.runs?.find((item: any) => item.course?.course_uuid?.replace('course_', '') === cleanCourseId)
  const activities = course.chapters.flatMap((chapter: any) => chapter.activities || [])
  const completed = activities.filter((activity: any) => run?.steps?.some((step: any) => step.activity_id === activity.id && step.complete === true)).length
  const progress = activities.length ? Math.round((completed / activities.length) * 100) : 0

  const iconFor = (type: string) => {
    if (type === 'TYPE_VIDEO') return <PlayCircle size={14} />
    if (type === 'TYPE_DOCUMENT') return <FileText size={14} />
    if (type === 'TYPE_ASSIGNMENT') return <Backpack size={14} />
    return <StickyNote size={14} />
  }

  return (
    <aside className="activity-course-sidebar activity-glass w-full lg:w-[280px] shrink-0 self-start rounded-2xl p-3 sm:p-4">
      <div className="flex items-center justify-between gap-3 px-1 pb-3">
        <div className="flex items-center gap-2">
          <ListTree size={17} className="text-[#00a9bf]" />
          <h2 className="text-sm font-bold text-slate-800">{t('courses.course_content')}</h2>
        </div>
        <span className="text-xs font-semibold text-[#00a9bf]">{completed}/{activities.length}</span>
      </div>
      <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-200/70">
        <div className="h-full rounded-full bg-[#00a9bf] transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <div className="activity-course-sidebar-scroll space-y-2">
        {course.chapters.map((chapter: any, index: number) => {
          const chapterCompleted = (chapter.activities || []).filter((activity: any) => run?.steps?.some((step: any) => step.activity_id === activity.id && step.complete === true)).length
          return (
            <details key={chapter.id} open={chapter.activities?.some((activity: any) => activity.activity_uuid?.replace('activity_', '') === currentId)} className="group overflow-hidden rounded-xl border border-white/70 bg-white/35">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-semibold text-slate-700 hover:bg-white/45">
                <span className="flex min-w-0 items-center gap-2"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#00a9bf] text-[10px] font-bold text-white">{index + 1}</span><span className="truncate">{chapter.name}</span></span>
                <span className="shrink-0 text-[10px] text-slate-500">{chapterCompleted}/{chapter.activities?.length || 0}</span>
              </summary>
              <div className="border-t border-white/70 px-1.5 py-1">
                {(chapter.activities || []).map((activity: any) => {
                  const id = activity.activity_uuid?.replace('activity_', '')
                  const isCurrent = id === currentId
                  const isDone = run?.steps?.some((step: any) => step.activity_id === activity.id && step.complete === true)
                  return <Link key={activity.activity_uuid} href={`${getUriWithOrg(orgslug, '')}/course/${courseId}/activity/${id}`} prefetch={false} className={`group/item flex items-center gap-2 rounded-lg px-2 py-2 text-xs transition-colors ${isCurrent ? 'bg-[#00a9bf] text-white shadow-sm' : 'text-slate-600 hover:bg-white/70'}`}><span className={`${isDone ? 'text-[#00a9bf]' : isCurrent ? 'text-white' : 'text-slate-300'}`}>{isDone ? <Check size={14} /> : iconFor(activity.activity_type)}</span><span className="min-w-0 flex-1 truncate">{activity.name}</span><ArrowRight size={12} className={`${isCurrent ? 'opacity-100' : 'opacity-0 group-hover/item:opacity-60'}`} /></Link>
                })}
              </div>
            </details>
          )
        })}
      </div>
    </aside>
  )
}
