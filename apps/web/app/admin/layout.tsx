import type { Metadata } from 'next'
import AdminProviders from './providers'
import React from 'react'

export const metadata: Metadata = {
  title: {
    template: '%s | BBB Academia Admin',
    default: 'BBB Academia Admin',
  },
}

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <AdminProviders>{children}</AdminProviders>
}
