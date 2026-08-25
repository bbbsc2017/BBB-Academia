'use client';

import React from 'react';
import { Banknote, Building2, CreditCard } from 'lucide-react';
import { getStripeOnboardingLink } from './stripe';

export type PaymentProviderId = 'stripe' | 'openpay' | 'bold';
export type PaymentProviderApiValue = 'STRIPE' | 'OPENPAY' | 'BOLD';

export interface PaymentProviderDefinition {
  id: PaymentProviderId;
  name: string;
  Icon: React.ComponentType<{ size?: number; className?: string }>;
  tagline: string;
  docsUrl: string;
  callbackPath?: string;
  connectButtonLabel: string;
  connectedLabel: string;
  checkoutCopy: string;
  getConnectUrl?: (orgId: number, accessToken: string, redirectUri: string) => Promise<string>;
  /** True for providers with no OAuth "Connect" step (Bold has no such flow —
   * see developers.bold.co) that instead need their API keys entered directly.
   * Drives whether PaymentsConfigurationPage renders the inline credentials form. */
  hasCredentialsForm?: boolean;
}

export const PAYMENT_PROVIDERS: PaymentProviderDefinition[] = [
  {
    id: 'stripe',
    name: 'Stripe',
    Icon: CreditCard,
    tagline: 'Accept one-time payments and subscriptions via Stripe Connect.',
    docsUrl: 'https://stripe.com/docs',
    callbackPath: '/payments/stripe/connect/oauth',
    connectButtonLabel: 'Connect Stripe',
    connectedLabel: 'Connected',
    checkoutCopy: 'Secure checkout powered by Stripe.',
    async getConnectUrl(orgId, accessToken, redirectUri) {
      const { connect_url } = await getStripeOnboardingLink(orgId, accessToken, redirectUri);
      return connect_url;
    },
  },
  {
    id: 'openpay',
    name: 'OpenPay',
    Icon: Banknote,
    tagline: 'Platform-managed checkout for one-time payments in Colombia.',
    docsUrl: 'https://www.openpay.co/',
    connectButtonLabel: 'Use OpenPay',
    connectedLabel: 'Ready',
    checkoutCopy: 'Secure checkout powered by OpenPay.',
  },
  {
    id: 'bold',
    name: 'Bold',
    Icon: Building2,
    tagline: 'Single-merchant checkout for fast local payment flows.',
    docsUrl: 'https://developers.bold.co/pagos-en-linea/llaves-de-integracion',
    connectButtonLabel: 'Configure keys',
    connectedLabel: 'Ready',
    checkoutCopy: 'Secure checkout powered by Bold.',
    hasCredentialsForm: true,
  },
];

export function getPaymentProvider(providerId: PaymentProviderId) {
  return PAYMENT_PROVIDERS.find((provider) => provider.id === providerId);
}

export function toApiProviderValue(providerId: PaymentProviderId): PaymentProviderApiValue {
  return providerId.toUpperCase() as PaymentProviderApiValue;
}

export function fromApiProviderValue(provider: string | null | undefined): PaymentProviderId | null {
  if (!provider) return null;
  const normalized = provider.toLowerCase();
  if (normalized === 'stripe' || normalized === 'openpay' || normalized === 'bold') {
    return normalized;
  }
  return null;
}