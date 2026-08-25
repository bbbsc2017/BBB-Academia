// Auto-generates a username when the signup UI doesn't ask for one (e.g. the
// guest-checkout flow, which only collects email + password because the
// username has no bearing on the purchase). Mirrors the convention already
// used server-side for JIT-provisioned accounts (Google OAuth, bbbsc SSO —
// see apps/api/src/services/auth/bbbsc.py): sanitized local-part of the
// email + a random numeric suffix wide enough to make collisions unlikely.
export function generateUsernameFromEmail(email: string): string {
  const localPart = (email.split('@')[0] || 'user')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
  const base = localPart.length >= 3 ? localPart : 'user'
  const suffix = Math.floor(100000 + Math.random() * 900000)
  return `${base}${suffix}`
}
