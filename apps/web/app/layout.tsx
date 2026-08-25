import '../styles/globals.css'
import React from 'react'
import Providers from '@components/Providers'
import { Poppins } from 'next/font/google'

const poppins = Poppins({
  subsets: ['latin'],
  display: 'swap',
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-default',
})

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html className={poppins.variable} lang="en" suppressHydrationWarning>
      <head>
        {/* Synchronous script — blocks parsing to guarantee window.__RUNTIME_CONFIG__ exists before any JS runs.
            Next.js <Script strategy="beforeInteractive"> is not truly blocking in all browsers (Safari).
            Hardcoded absolute paths don't get Next's automatic basePath prefixing (unlike next/link,
            next/image, or bundled chunks), so basePath is prepended manually here. */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/runtime-config.js`} />
        {/* Prevent white flash on embed routes: set html+body bg before body is painted.
            Reads the optional ?bgcolor param (hex-validated) or defaults to dark. */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/embed-bg.js`} />
      </head>
      <body suppressHydrationWarning>
        <Providers>
          <main className="animate-fade-in">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  )
}
