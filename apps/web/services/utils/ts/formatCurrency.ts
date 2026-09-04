// Intl.NumberFormat throws "Currency code is required with currency style"
// for ANY falsy currency — not just null/undefined but also '' (empty
// string), which `?? 'USD'` does not catch since `??` only falls back on
// null/undefined. An offer/enrollment with a missing or blank currency
// (misconfigured in the dashboard, or a legacy row from before currency was
// required) would crash the whole page render. Always funnel a price
// through this instead of calling Intl.NumberFormat directly.
export function formatCurrency(amount: number, currency: string | null | undefined, locale = 'en-US'): string {
  const safeCurrency = currency && currency.trim() ? currency : 'USD'
  return new Intl.NumberFormat(locale, { style: 'currency', currency: safeCurrency }).format(amount)
}
