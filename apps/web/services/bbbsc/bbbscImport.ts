import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyWithAuthHeader,
  getResponseMetadata,
} from '@services/utils/ts/requests'

export async function listBbbscParticipants(
  org_id: any,
  page: number,
  limit: number,
  search: string,
  access_token: string
) {
  const params = new URLSearchParams()
  params.append('page', page.toString())
  params.append('limit', limit.toString())
  if (search) params.append('search', search)

  const result: any = await fetch(
    `${getAPIUrl()}orgs/${org_id}/bbbsc/participants?${params.toString()}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function importBbbscParticipants(
  org_id: any,
  participants: any[],
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}orgs/${org_id}/bbbsc/import`,
    RequestBodyWithAuthHeader('POST', { participants }, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}
