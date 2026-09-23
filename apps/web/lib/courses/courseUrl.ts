// Public course URLs use the name-derived slug (/course/<slug>); the uuid is
// only a fallback for courses that don't have a slug yet. Legacy uuid URLs
// still work — the proxy redirects them to the slug.
export function getCourseUrlSegment(
  course: { course_uuid?: string | null; slug?: string | null } | null | undefined,
  fallbackUuid?: string
): string {
  if (course?.slug) return course.slug
  return (course?.course_uuid ?? fallbackUuid ?? '').replace('course_', '')
}
