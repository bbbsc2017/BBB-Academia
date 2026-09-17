'use client'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { useOrg } from '@components/Contexts/OrgContext'
import useAdminStatus from '@components/Hooks/useAdminStatus'
import LearnHouseSpinner from '@components/Objects/Loaders/LearnHouseSpinner'
import Toast from '@components/Objects/StyledElements/Toast/Toast'
import { importBbbscParticipants, listBbbscParticipants } from '@services/bbbsc/bbbscImport'
import { linkUsersToUserGroup } from '@services/usergroups/usergroups'
import { apiFetch } from '@services/utils/ts/requests'
import { getAPIUrl } from '@services/config/config'
import { CheckCircle2, ChevronLeft, ChevronRight, Download, Search, Users } from 'lucide-react'
import React, { useState } from 'react'
import toast from 'react-hot-toast'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import { useTranslation } from 'react-i18next'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'

const ITEMS_PER_PAGE = 20

function OrgBbbscImport() {
  const { t } = useTranslation()
  const org = useOrg() as any
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token
  const queryClient = useQueryClient()
  const { canManageOrg } = useAdminStatus()

  const [page, setPage] = useState(1)
  const [searchValue, setSearchValue] = useState('')
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set())
  const [isImporting, setIsImporting] = useState(false)
  const [justImportedIds, setJustImportedIds] = useState<number[] | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string>('')
  const [isAddingToGroup, setIsAddingToGroup] = useState(false)

  const { data, isFetching, isError } = useQuery({
    queryKey: ['bbbsc-participants', org?.id, page, searchValue],
    queryFn: () => listBbbscParticipants(org.id, page, ITEMS_PER_PAGE, searchValue, access_token),
    enabled: !!org?.id && !!access_token && canManageOrg,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })

  const { data: usergroups } = useQuery({
    queryKey: queryKeys.usergroups.list(org?.id),
    queryFn: () => apiFetch(`${getAPIUrl()}usergroups/org/${org.id}?org_id=${org.id}`, access_token),
    enabled: !!org?.id && !!access_token,
    staleTime: 60_000,
  })

  const participants = data?.data?.items || []
  const total = data?.data?.total ?? 0
  const isInitialLoading = !data && isFetching

  const importableEmails: string[] = participants
    .filter((p: any) => !p.already_exists_in_learnhouse)
    .map((p: any) => p.email)
  const allImportableSelected =
    importableEmails.length > 0 && importableEmails.every((e) => selectedEmails.has(e))

  const toggleSelectAll = () => {
    setSelectedEmails((prev) => {
      const next = new Set(prev)
      if (allImportableSelected) {
        importableEmails.forEach((e) => next.delete(e))
      } else {
        importableEmails.forEach((e) => next.add(e))
      }
      return next
    })
  }

  const toggleSelectOne = (email: string) => {
    setSelectedEmails((prev) => {
      const next = new Set(prev)
      if (next.has(email)) {
        next.delete(email)
      } else {
        next.add(email)
      }
      return next
    })
  }

  const handleSearchChange = (value: string) => {
    setSearchValue(value)
    setPage(1)
    setSelectedEmails(new Set())
    setJustImportedIds(null)
  }

  const handleImport = async () => {
    const toImport = participants.filter((p: any) => selectedEmails.has(p.email))
    if (toImport.length === 0) return
    setIsImporting(true)
    const toastId = toast.loading(
      t('dashboard.users.bbbsc_import.actions.importing', { count: toImport.length }) ||
        `Importing ${toImport.length} participant(s)...`
    )
    try {
      const res = await importBbbscParticipants(org.id, toImport, access_token)
      if (res.status === 200) {
        setSelectedEmails(new Set())
        setJustImportedIds(res.data?.imported_user_ids || [])
        queryClient.invalidateQueries({ queryKey: ['bbbsc-participants', org.id] })
        queryClient.invalidateQueries({ queryKey: queryKeys.org.users(org.id) })
        toast.success(res.data?.detail || 'Participants imported', { id: toastId })
      } else {
        toast.error(res.data?.detail || 'Error importing participants', { id: toastId })
      }
    } finally {
      setIsImporting(false)
    }
  }

  const handleAddImportedToGroup = async () => {
    if (!selectedGroupId || !justImportedIds || justImportedIds.length === 0) return
    setIsAddingToGroup(true)
    const toastId = toast.loading('Adding imported users to group...')
    try {
      const res = await linkUsersToUserGroup(selectedGroupId, justImportedIds, org.id, access_token)
      if (res.status === 200 || res.status === 201) {
        queryClient.invalidateQueries({ queryKey: queryKeys.org.users(org.id) })
        setJustImportedIds(null)
        setSelectedGroupId('')
        toast.success('Users added to group — course access granted', { id: toastId })
      } else {
        toast.error('Error adding users to group', { id: toastId })
      }
    } finally {
      setIsAddingToGroup(false)
    }
  }

  if (!canManageOrg) {
    return (
      <div className="mx-4 sm:mx-10 bg-white rounded-xl nice-shadow p-10 text-center">
        <p className="text-gray-400 text-sm font-medium">
          {t('dashboard.users.bbbsc_import.no_permission') ||
            'Only administrators and maintainers can import bbbsc participants.'}
        </p>
      </div>
    )
  }

  return (
    <div>
      <Toast></Toast>
      <div className="h-6"></div>
      <div className="mx-4 sm:mx-10 bg-white rounded-xl nice-shadow">
        {/* Header */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between px-4 sm:px-6 py-5 border-b border-gray-100">
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-xl text-gray-800">
              {t('dashboard.users.bbbsc_import.title') || 'Import from bbbsc'}
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {t('dashboard.users.bbbsc_import.subtitle') ||
                'Bring in participants already registered in bbbsc and create their LearnHouse accounts.'}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {total > 0 && (
              <div className="text-sm text-gray-500 bg-gray-50 px-3 py-1.5 rounded-lg font-medium">
                {total} {total === 1 ? 'participant' : 'participants'}
              </div>
            )}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                placeholder={t('dashboard.users.bbbsc_import.search_placeholder') || 'Search participants...'}
                className="pl-10 pr-4 py-2 w-full sm:w-[220px] border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#00a9bf]/20 focus:border-[#00a9bf] transition-all"
                value={searchValue}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Post-import success bar: assign the just-imported users to a group */}
        {justImportedIds && justImportedIds.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 px-6 py-3 bg-emerald-50 border-b border-emerald-100">
            <span className="text-sm font-medium text-emerald-700 inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              {justImportedIds.length} {t('dashboard.users.bbbsc_import.actions.imported_now', { defaultValue: 'user(s) imported.' })}
            </span>
            <div className="flex items-center gap-2">
              <Select value={selectedGroupId || undefined} onValueChange={setSelectedGroupId}>
                <SelectTrigger className="h-8 w-[190px] text-xs border-emerald-200 bg-white">
                  <SelectValue placeholder={t('dashboard.users.bbbsc_import.actions.pick_group', { defaultValue: 'Grant access via group...' })} />
                </SelectTrigger>
                <SelectContent>
                  {usergroups?.map((group: any) => (
                    <SelectItem key={group.id} value={group.id.toString()}>
                      {group.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <button
                onClick={handleAddImportedToGroup}
                disabled={!selectedGroupId || isAddingToGroup}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-md text-xs font-medium transition-all"
              >
                <Users className="w-3.5 h-3.5" />
                <span>{t('dashboard.users.bbbsc_import.actions.add_to_group', { defaultValue: 'Add to group' })}</span>
              </button>
              <button
                onClick={() => setJustImportedIds(null)}
                className="text-xs text-emerald-700 hover:text-emerald-900 font-medium px-2 py-1.5"
              >
                {t('common.dismiss', { defaultValue: 'Dismiss' })}
              </button>
            </div>
          </div>
        )}

        {/* Selection action bar */}
        {selectedEmails.size > 0 && (
          <div className="flex items-center justify-between px-6 py-3 bg-[#00a9bf]/10 border-b border-[#00a9bf]/15">
            <span className="text-sm font-medium text-[#007b8d]">
              {selectedEmails.size} {t('dashboard.users.bbbsc_import.selected', { defaultValue: 'selected' })}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedEmails(new Set())}
                className="text-xs text-[#00a9bf] hover:text-[#007b8d] font-medium px-3 py-1.5 rounded-md hover:bg-[#00a9bf]/10 transition-all"
              >
                {t('common.clear_selection', { defaultValue: 'Clear selection' })}
              </button>
              <button
                onClick={handleImport}
                disabled={isImporting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#00a9bf] text-white hover:bg-[#008da0] disabled:opacity-40 disabled:cursor-not-allowed rounded-md text-xs font-medium transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{t('dashboard.users.bbbsc_import.actions.import_selected', { defaultValue: 'Import selected' })}</span>
              </button>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="overflow-x-auto relative">
          {isInitialLoading ? (
            <div className="flex items-center justify-center py-16">
              <LearnHouseSpinner size={28} />
            </div>
          ) : isError ? (
            <div className="py-16 text-center">
              <p className="text-gray-400 text-sm font-medium">
                {t('dashboard.users.bbbsc_import.unreachable') ||
                  'bbbsc is unreachable right now — try again in a moment.'}
              </p>
            </div>
          ) : participants.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-gray-400 text-sm font-medium">
                {searchValue
                  ? t('dashboard.users.bbbsc_import.no_results') || 'No participants found matching your search'
                  : t('dashboard.users.bbbsc_import.no_participants') || 'No participants found in bbbsc'}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-6 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={allImportableSelected}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 text-[#00a9bf] focus:ring-[#00a9bf] cursor-pointer"
                    />
                  </th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">
                    {t('dashboard.users.bbbsc_import.table.name') || 'Name'}
                  </th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">
                    {t('dashboard.users.bbbsc_import.table.email') || 'Email'}
                  </th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">
                    {t('dashboard.users.bbbsc_import.table.student_code') || 'Code'}
                  </th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-3">
                    {t('dashboard.users.bbbsc_import.table.status') || 'Status'}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {participants.map((p: any) => (
                  <tr
                    key={p.id || p.email}
                    className={`transition-colors ${
                      p.already_exists_in_learnhouse
                        ? 'opacity-50'
                        : selectedEmails.has(p.email)
                        ? 'bg-[#00a9bf]/10'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <td className="px-6 py-4 w-10">
                      <input
                        type="checkbox"
                        checked={selectedEmails.has(p.email)}
                        disabled={p.already_exists_in_learnhouse}
                        onChange={() => toggleSelectOne(p.email)}
                        className="w-4 h-4 rounded border-gray-300 text-[#00a9bf] focus:ring-[#00a9bf] cursor-pointer disabled:cursor-not-allowed"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-semibold text-gray-800 text-sm">
                        {[p.firstName, p.lastName].filter(Boolean).join(' ') || '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs text-gray-500">{p.email}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs text-gray-400">{p.studentCode || '—'}</span>
                    </td>
                    <td className="px-6 py-4">
                      {p.already_exists_in_learnhouse ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-600" title="Already has a LearnHouse account">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>{t('dashboard.users.bbbsc_import.table.already_in_learnhouse', { defaultValue: 'Already in LearnHouse' })}</span>
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">
                          {t('dashboard.users.bbbsc_import.table.not_imported', { defaultValue: 'Not imported' })}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {total > ITEMS_PER_PAGE && (
          <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-t border-gray-100 bg-gray-50/50">
            <div className="text-xs text-gray-500 font-medium">
              {`Showing ${(page - 1) * ITEMS_PER_PAGE + 1}-${Math.min(page * ITEMS_PER_PAGE, total)} of ${total}`}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setPage((p) => Math.max(1, p - 1)); setSelectedEmails(new Set()) }}
                disabled={page === 1}
                className="p-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                <ChevronLeft className="w-4 h-4 text-gray-600" />
              </button>
              <span className="text-sm text-gray-600 font-medium min-w-[80px] text-center bg-white px-3 py-2 rounded-lg border border-gray-200">
                {`Page ${page} of ${Math.ceil(total / ITEMS_PER_PAGE)}`}
              </span>
              <button
                onClick={() => { setPage((p) => p + 1); setSelectedEmails(new Set()) }}
                disabled={page * ITEMS_PER_PAGE >= total}
                className="p-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default OrgBbbscImport
