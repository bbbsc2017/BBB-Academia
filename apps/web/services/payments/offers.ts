'use server';
import { getAPIUrl } from '@services/config/config';
import { RequestBodyWithAuthHeader, getResponseMetadata, secureFetch } from '@services/utils/ts/requests';

export async function getOffers(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function createOffer(orgId: number, data: any, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers`,
    RequestBodyWithAuthHeader('POST', data, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function updateOffer(orgId: number, offerId: string, data: any, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerId)}`,
    RequestBodyWithAuthHeader('PUT', data, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function archiveOffer(orgId: number, offerId: string, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerId)}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function getOfferDetails(orgId: number, offerId: string, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerId)}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function getPublicOffer(orgId: number, offerId: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerId)}/public`,
    RequestBodyWithAuthHeader('GET', null, null, '')
  );
  return getResponseMetadata(result);
}

export async function getPublicOffers(orgId: number) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/public-listing`,
    RequestBodyWithAuthHeader('GET', null, null, '')
  );
  return getResponseMetadata(result);
}

/**
 * access_token is optional — this stays callable for anonymous visitors
 * (they just get has_access: false on every offer, which is correct) — but
 * MUST be passed by any authenticated caller, or the backend has no way to
 * tell who's asking and always resolves has_access to false even for a
 * buyer who already paid. (This was the actual bug: both call sites were
 * omitting it entirely.)
 */
export async function getOffersByResource(orgId: number, resourceUuid: string, access_token?: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/by-resource?resource_uuid=${encodeURIComponent(resourceUuid)}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || '')
  );
  return getResponseMetadata(result);
}

// Provider-agnostic: the backend selects the correct payment provider
// based on the org's active PaymentsConfig.
export async function getOfferCheckoutSession(
  orgId: number,
  offerUuid: string,
  redirect_uri: string,
  access_token: string,
  recaptcha_token?: string | null
) {
  const params = new URLSearchParams({ redirect_uri })
  if (recaptcha_token) params.set('recaptcha_token', recaptcha_token)
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerUuid)}/checkout?${params.toString()}`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  );
  return getResponseMetadata(result);
}

/**
 * Safety-net re-check for when the buyer's browser returns from the
 * provider's checkout page — the backend re-verifies with the provider's own
 * API rather than trusting anything in the return URL. See
 * api_confirm_payment in routers/payments/payments.py.
 */
export async function confirmOfferPayment(orgId: number, offerUuid: string, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/offers/${encodeURIComponent(offerUuid)}/confirm-payment`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function getBillingPortalSession(orgId: number, return_url: string, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/billing/portal?return_url=${encodeURIComponent(return_url)}`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  );
  return getResponseMetadata(result);
}

export async function getUserEnrollments(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/enrollments/mine`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const metadata = await getResponseMetadata(result);
  if (!metadata.success) throw new Error(metadata.HTTPmessage || 'Failed to fetch enrollments')
  return metadata;
}
