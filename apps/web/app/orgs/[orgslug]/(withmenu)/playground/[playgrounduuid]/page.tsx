import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { getServerSession } from '@/lib/auth/server'
import { getPlayground } from '@services/playgrounds/playgrounds'
import PaymentWall from '@components/Payments/PaymentWall'
import PlaygroundViewClient from './view'

type PageParams = Promise<{ orgslug: string; playgrounduuid: string }>

export async function generateMetadata({ params }: { params: PageParams }): Promise<Metadata> {
  const { playgrounduuid } = await params
  try {
    const pg = await getPlayground(playgrounduuid)
    return {
      title: pg.name,
      description: pg.description || `Interactive playground: ${pg.name}`,
    }
  } catch {
    return { title: 'Playground' }
  }
}

export default async function PlaygroundViewPage({ params }: { params: PageParams }) {
  const { orgslug, playgrounduuid } = await params
  const session = await getServerSession()
  const access_token = session?.tokens?.access_token

  let playground
  try {
    playground = await getPlayground(playgrounduuid, access_token ?? undefined)
  } catch (error: any) {
    if (error?.status === 402 && error?.detail?.code === 'PAYMENT_REQUIRED') {
      return (
        <div className="flex items-center justify-center min-h-[50vh]">
          <PaymentWall offer={error.detail} orgslug={orgslug} />
        </div>
      )
    }
    notFound()
  }

  if (!playground.published && !access_token) {
    notFound()
  }

  return (
    <PlaygroundViewClient
      playground={playground}
      orgslug={orgslug}
      canEdit={!!access_token}
    />
  )
}
