'use server';
// Generic payment configuration service.
// Provider-specific connection logic lives in services/payments/providers/<provider>.ts
import { getAPIUrl } from '@services/config/config';
import { RequestBodyWithAuthHeader, errorHandling, secureFetch } from '@services/utils/ts/requests';
import { toApiProviderValue, type PaymentProviderId } from '@services/payments/providers';

export async function getPaymentConfigs(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/config`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function initializePaymentConfig(
  orgId: number,
  data: any,
  provider: PaymentProviderId,
  access_token: string
) {
  const apiProvider = toApiProviderValue(provider);
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/config?provider=${encodeURIComponent(apiProvider)}`,
    RequestBodyWithAuthHeader('POST', data, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

// Write-only: the response never contains the values, only
// `credentials_configured`. See apps/api/src/db/payments/config.py
// BoldCredentialsUpdate for the accepted fields (currently Bold-only).
export async function updatePaymentConfigCredentials(
  orgId: number,
  configId: number,
  credentials: { bold_api_key?: string; bold_webhook_secret?: string },
  access_token: string
) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/config/${encodeURIComponent(String(configId))}/credentials`,
    RequestBodyWithAuthHeader('PUT', credentials, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function deletePaymentConfig(orgId: number, id: string, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/config?id=${encodeURIComponent(id)}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function getOrgCustomers(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/customers`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function getUserEnrollments(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/enrollments/mine`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function getStripeOverview(orgId: number, access_token: string) {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/stripe/overview`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function getStripeCharges(orgId: number, access_token: string, limit = 25, startingAfter?: string) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (startingAfter) params.set('starting_after', startingAfter);
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/stripe/charges?${params}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}

export async function getStripeSubscriptions(orgId: number, access_token: string, status = 'active') {
  const result = await secureFetch(
    `${getAPIUrl()}payments/${encodeURIComponent(String(orgId))}/stripe/subscriptions?status=${encodeURIComponent(status)}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  );
  const res = await errorHandling(result);
  return res;
}
