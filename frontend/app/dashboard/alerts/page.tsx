'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlerts, resolveAlert } from '@/lib/api'
import { formatTime } from '@/lib/time'
import { format } from 'date-fns'
import { useState } from 'react'
import Link from 'next/link'

const SEVERITY: Record<string, { border: string; text: string; badge: string }> = {
  high:   { border: 'border-l-red-500',    text: 'text-red-500',    badge: 'bg-red-500/10 text-red-500'       },
  medium: { border: 'border-l-orange-500', text: 'text-orange-500', badge: 'bg-orange-500/10 text-orange-500' },
  low:    { border: 'border-l-yellow-500', text: 'text-yellow-500', badge: 'bg-yellow-500/10 text-yellow-500' },
}

export default function AlertsPage() {
  const qc = useQueryClient()
  const [showResolved, setShowResolved] = useState(false)

  const { data: alerts = [], isLoading, isError } = useQuery({
    queryKey: ['alerts', showResolved],
    queryFn: () => getAlerts(showResolved),
    refetchInterval: 15000
  })

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] })
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold">Alerts</h2>
          <p className="text-slate-500 text-sm mt-1">
            {alerts.length} {showResolved ? 'resolved' : 'active'} alerts
          </p>
        </div>
        <button
          onClick={() => setShowResolved(!showResolved)}
          className="bg-slate-100 text-gray-700 border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
        >
          {showResolved ? 'Show Active' : 'Show Resolved'}
        </button>
      </div>

      {isLoading ? (
        <p className="text-slate-400">Loading...</p>
      ) : isError ? (
        <div className="bg-red-50 rounded-xl p-6 text-center shadow-sm">
          <p className="text-red-600 text-sm">Failed to load alerts. Check your backend connection.</p>
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center shadow-sm">
          <p className="text-slate-400 text-[15px]">
            {showResolved ? 'No resolved alerts.' : '✓ No active alerts.'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {alerts.map((a: any) => {
            const sev = SEVERITY[a.severity] ?? { border: 'border-l-slate-400', text: 'text-slate-500', badge: 'bg-slate-100 text-slate-500' }
            return (
              <div key={a.id} className={`bg-white rounded-xl px-6 py-5 shadow-sm border-l-4 ${sev.border}`}>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <span className={`text-[13px] font-bold ${sev.text}`}>
                        {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className={`text-[11px] px-2 py-px rounded-full font-semibold ${sev.badge}`}>
                        {a.severity.toUpperCase()}
                      </span>
                      {(a.teachers || a.students) && (
                        <span className={`text-[11px] px-2.5 py-px rounded-full font-semibold border ${
                          a.teachers
                            ? 'bg-blue-50 text-blue-500 border-blue-200'
                            : 'bg-green-50 text-green-600 border-green-200'
                        }`}>
                          {a.teachers
                            ? `👨‍🏫 Teacher · ${a.teachers.full_name}`
                            : `👨‍🎓 Student · ${a.students?.full_name ?? 'Unknown'}`
                          }
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 mb-2">{a.notes}</p>
                    <div className="flex gap-4 text-xs text-slate-400">
                      <span>{formatTime(a.triggered_at)}</span>
                      {a.class_schedules && (
                        <Link
                          href={`/dashboard/schedules/${a.class_schedules.id}`}
                          className="text-blue-500 no-underline"
                        >
                          View Class →
                        </Link>
                      )}
                    </div>
                  </div>
                  {!a.is_resolved && (
                    <button
                      onClick={() => resolveMutation.mutate(a.id)}
                      disabled={resolveMutation.isPending}
                      className="text-[13px] font-medium px-[18px] py-2 rounded-lg border border-slate-200 bg-white cursor-pointer text-gray-700 shrink-0 ml-5"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
