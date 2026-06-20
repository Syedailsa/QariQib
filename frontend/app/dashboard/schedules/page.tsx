'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSchedules, deleteSchedule } from '@/lib/api'
import { formatTime, formatDateHeader } from '@/lib/time'
import { format } from 'date-fns'
import Link from 'next/link'
import { useState } from 'react'

const STATUS_CONFIG: Record<string, { card: string; badge: string; text: string; viewBtn: string }> = {
  scheduled: {
    card:    'bg-yellow-50 border-[1.5px] border-yellow-300',
    badge:   'bg-yellow-800/10 text-yellow-800',
    text:    'text-yellow-900',
    viewBtn: 'border border-yellow-300 text-yellow-800',
  },
  live: {
    card:    'bg-green-50 border-[1.5px] border-green-300',
    badge:   'bg-green-700/10 text-green-700',
    text:    'text-green-900',
    viewBtn: 'border border-green-300 text-green-700',
  },
  completed: {
    card:    'bg-green-50 border-[1.5px] border-green-400',
    badge:   'bg-green-800/10 text-green-800',
    text:    'text-green-900',
    viewBtn: 'border border-green-400 text-green-800',
  },
  missed: {
    card:    'bg-red-50 border-[1.5px] border-red-300',
    badge:   'bg-red-600/10 text-red-600',
    text:    'text-red-900',
    viewBtn: 'border border-red-300 text-red-600',
  },
}

export default function SchedulesPage() {
  const qc = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState('')

  const { data: schedules = [], isLoading, isError } = useQuery({
    queryKey: ['schedules'],
    queryFn: getSchedules,
    refetchInterval: 30000
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      setConfirmDelete(null)
      setDeleteError('')
    },
    onError: (e: any) => setDeleteError(e.response?.data?.detail || 'Failed to delete. Please try again.')
  })

  const grouped = schedules.reduce((acc: Record<string, any[]>, s: any) => {
    const date = format(new Date(s.scheduled_start), 'yyyy-MM-dd')
    if (!acc[date]) acc[date] = []
    acc[date].push(s)
    return acc
  }, {} as Record<string, any[]>)

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold">All Schedules</h2>
          <p className="text-slate-500 text-sm mt-1">{schedules.length} total classes</p>
        </div>
        <Link href="/dashboard/schedules/new">
          <button className="bg-blue-500 text-white border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm font-medium">
            + New Class
          </button>
        </Link>
      </div>

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[1000]">
          <div className="bg-white rounded-xl p-7 w-[380px] shadow-2xl">
            <h3 className="text-[17px] font-semibold mb-2">Delete this class?</h3>
            <p className="text-sm text-slate-500 mb-3">
              This will delete the Zoom meeting and all attendance records. This cannot be undone.
            </p>
            {deleteError && (
              <p className="text-[13px] text-red-600 mb-3">{deleteError}</p>
            )}
            <div className="flex gap-2.5">
              <button
                onClick={() => deleteMutation.mutate(confirmDelete)}
                disabled={deleteMutation.isPending}
                className="bg-red-500 text-white border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm font-medium flex-1"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
              </button>
              <button
                onClick={() => setConfirmDelete(null)}
                className="bg-slate-100 text-gray-700 border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm flex-1"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-slate-400">Loading...</p>
      ) : isError ? (
        <div className="bg-red-50 rounded-xl p-8 text-center shadow-sm">
          <p className="text-red-600 text-sm">Failed to load schedules. Check your backend connection.</p>
        </div>
      ) : schedules.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center shadow-sm">
          <p className="text-slate-400 text-[15px]">
            No classes scheduled yet.{' '}
            <Link href="/dashboard/schedules/new" className="text-blue-500">
              Create your first class →
            </Link>
          </p>
        </div>
      ) : (
        (Object.entries(grouped) as [string, any[]][])
          .sort(([a], [b]) => b.localeCompare(a))
          .map(([date, daySchedules]: [string, any[]]) => (
            <div key={date} className="mb-8">
              {/* Date header */}
              <div className="text-[13px] font-semibold text-slate-500 uppercase tracking-[0.06em] mb-3 pb-2 border-b border-slate-200">
                {formatDateHeader(date + 'T12:00:00')}
              </div>

              {/* Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {daySchedules.map((s: any) => {
                  const cfg = STATUS_CONFIG[s.status] || STATUS_CONFIG.scheduled
                  const alertCount = s.alerts?.filter((a: any) => !a.is_resolved).length || 0

                  return (
                    <div key={s.id} className={`${cfg.card} rounded-xl p-[18px] relative`}>
                      {/* Status badge row */}
                      <div className="flex justify-between items-start mb-2.5">
                        <span className={`text-[11px] font-bold px-2.5 py-[3px] rounded-full tracking-[0.04em] ${cfg.badge}`}>
                          {s.status === 'live' ? '🟢 LIVE' : s.status.toUpperCase()}
                        </span>
                        {alertCount > 0 && (
                          <span className="text-[11px] font-bold px-2.5 py-[3px] rounded-full bg-red-50 text-red-600">
                            🔔 {alertCount} alert{alertCount > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>

                      {/* Teacher */}
                      <div className={`text-[15px] font-semibold mb-1 ${cfg.text}`}>
                        {s.teachers?.full_name}
                      </div>

                      {/* Time */}
                      <div className="text-[13px] text-slate-500 mb-2">
                        {formatTime(s.scheduled_start)} →{' '}
                        {formatTime(s.scheduled_end)}
                        {' · '}{s.scheduled_duration_mins} mins
                      </div>

                      {/* Students count */}
                      <div className="text-xs text-slate-400 mb-3">
                        👥 {s.class_students?.length || 0} students enrolled
                      </div>

                      {/* Actual duration diff */}
                      {s.actual_duration_mins && (
                        <div className="text-xs mb-3">
                          <span className="text-slate-500">Actual: </span>
                          <span className={`font-semibold ${cfg.text}`}>{s.actual_duration_mins} mins</span>
                          {s.duration_diff_mins !== null && s.duration_diff_mins !== 0 && (
                            <span className={`ml-1.5 font-semibold ${s.duration_diff_mins < 0 ? 'text-red-500' : 'text-green-500'}`}>
                              · {s.duration_diff_mins < 0
                                ? `ended ${Math.abs(s.duration_diff_mins)} mins early`
                                : `ran ${s.duration_diff_mins} mins over`}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2">
                        <Link href={`/dashboard/schedules/${s.id}`} className="flex-1 no-underline">
                          <button className={`w-full py-[7px] rounded-[7px] bg-white cursor-pointer text-xs font-medium ${cfg.viewBtn}`}>
                            View Details
                          </button>
                        </Link>

                        {s.status === 'scheduled' && (
                          <>
                            <Link href={`/dashboard/schedules/${s.id}/edit`} className="no-underline">
                              <button className="px-3 py-[7px] rounded-[7px] border border-slate-200 bg-white cursor-pointer text-xs text-gray-700">
                                ✏️
                              </button>
                            </Link>
                            <button
                              onClick={() => setConfirmDelete(s.id)}
                              className="px-3 py-[7px] rounded-[7px] border border-red-300 bg-white cursor-pointer text-xs text-red-600"
                            >
                              🗑️
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))
      )}
    </div>
  )
}
