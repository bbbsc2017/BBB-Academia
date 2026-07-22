/**
 * Plan utilities for the frontend.
 *
 * All plan data (feature configs, limits, requirements) lives in the API.
 * The frontend reads `resolved_features` from the org config returned by the API.
 *
 * This file only provides:
 *   - PlanLevel type
 *   - Plan hierarchy for UI comparisons (plan badges, upgrade prompts)
 *   - Deployment mode helpers (OSS/EE bypass)
 */

// Plan ids MUST match the backend (src/security/features_utils/plans.py): the
// family tier is 'personal-family', not 'family'. Using 'family' broke
// PLAN_HIERARCHY.indexOf() (→ -1) so planMeetsRequirement() denied every gated
// feature for those orgs.
export type PlanLevel = 'free' | 'personal' | 'personal-family' | 'standard' | 'pro' | 'enterprise' | 'oss'

// Plan hierarchy for SaaS mode (lower index = lower tier).
// 'oss' is kept as a display-only type value (not in hierarchy) for OSS mode label rendering.
export const PLAN_HIERARCHY: PlanLevel[] = ['free', 'personal', 'personal-family', 'standard', 'pro', 'enterprise']

/**
 * Check if the current plan meets or exceeds the required plan level.
 * Only used in SaaS mode — EE/OSS bypass is handled in isFeatureAvailable().
 */
export function planMeetsRequirement(
  currentPlan: PlanLevel,
  requiredPlan: PlanLevel
): boolean {
  // This self-hosted instance runs as a single private org — plan tiers
  // exist to gate a multi-tenant SaaS product, not the owner's own
  // deployment. No feature is restricted here, matching the backend
  // (src/security/features_utils/plans.py).
  if (currentPlan === 'oss') return true
  const currentIndex = PLAN_HIERARCHY.indexOf(currentPlan)
  const requiredIndex = PLAN_HIERARCHY.indexOf(requiredPlan)
  return currentIndex >= requiredIndex
}

/**
 * Check if a feature is available based on deployment mode.
 *
 * In SaaS mode, feature availability is determined by `resolved_features`
 * from the API — this function only handles mode-level bypass:
 * - OSS: all features allowed (see planMeetsRequirement)
 * - EE: all features allowed
 * - SaaS: always returns true (callers should check resolved_features)
 */
export function isFeatureAvailable(_featureKey: string, _currentPlan?: PlanLevel): boolean {
  // SaaS: resolved_features from the API is the source of truth.
  // Callers gate on resolved_features separately; OSS/EE both allow
  // everything at the mode level.
  return true
}
