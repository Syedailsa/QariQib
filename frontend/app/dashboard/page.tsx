// app/dashboard/page.tsx
'use client'
import { useQuery } from '@tanstack/react-query'
import { getTodaySchedules, getAlerts } from '@/lib/api'
import { formatTime } from '@/lib/time'
import { format } from 'date-fns'
import Link from 'next/link'

const STATUS_BADGE: Record<string, string> = {
  scheduled: 'bg-blue-500/10 text-blue-500',
  live:       'bg-green-500/10 text-green-500',
  completed:  'bg-slate-500/10 text-slate-500',
  missed:     'bg-red-500/10 text-red-500',
}

const SEVERITY: Record<string, { card: string; text: string }> = {
  high:   { card: 'border border-red-500/25 bg-red-500/5',       text: 'text-red-500'    },
  medium: { card: 'border border-orange-500/25 bg-orange-500/5', text: 'text-orange-500' },
  low:    { card: 'border border-yellow-500/25 bg-yellow-500/5', text: 'text-yellow-500' },
}

export default function DashboardPage() {
  const { data: schedules = [], isLoading: loadingSchedules, isError: errorSchedules } =
    useQuery({ queryKey: ['today-schedules'], queryFn: getTodaySchedules })

  const { data: alerts = [], isLoading: loadingAlerts, isError: errorAlerts } =
    useQuery({ queryKey: ['alerts'], queryFn: () => getAlerts(false) })

  const stats = [
    { label: 'Total Classes Today', value: schedules.length,                                              border: 'border-l-blue-500',  text: 'text-blue-500'  },
    { label: 'Live Now',            value: schedules.filter((s: any) => s.status === 'live').length,      border: 'border-l-green-500', text: 'text-green-500' },
    { label: 'Completed',           value: schedules.filter((s: any) => s.status === 'completed').length, border: 'border-l-slate-500', text: 'text-slate-500' },
    { label: 'Unresolved Alerts',   value: alerts.length,                                                 border: 'border-l-red-500',   text: 'text-red-500'   },
  ]

  return (
    <div>
      <h2 className="text-2xl font-bold mb-2">Today's Overview</h2>
      <p className="text-slate-500 mb-8">{format(new Date(), 'EEEE, MMMM d yyyy')}</p>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(stat => (
          <div key={stat.label} className={`bg-white rounded-xl p-5 shadow-sm border-l-4 ${stat.border}`}>
            <div className={`text-[28px] font-bold ${stat.text}`}>{stat.value}</div>
            <div className="text-[13px] text-slate-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's schedule */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h3 className="text-base font-semibold mb-4">Today's Classes</h3>
          {loadingSchedules ? (
            <p className="text-slate-400">Loading...</p>
          ) : errorSchedules ? (
            <p className="text-red-500 text-sm">Failed to load schedules. Check backend connection.</p>
          ) : schedules.length === 0 ? (
            <p className="text-slate-400 text-sm">No classes scheduled today.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {schedules.map((s: any) => (
                <Link key={s.id} href={`/dashboard/schedules/${s.id}`} className="no-underline">
                  <div className="px-4 py-3 rounded-lg border border-slate-200 cursor-pointer hover:border-slate-300 transition-colors duration-150">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm font-medium text-slate-900">{s.teachers?.full_name}</div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {formatTime(s.scheduled_start)} →{' '}
                          {formatTime(s.scheduled_end)}
                          {' · '}{s.scheduled_duration_mins} mins
                        </div>
                      </div>
                      <span className={`text-[11px] font-medium px-2.5 py-[3px] rounded-full ${STATUS_BADGE[s.status] ?? 'bg-slate-100 text-slate-500'}`}>
                        {s.status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Unresolved alerts */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h3 className="text-base font-semibold mb-4">Active Alerts</h3>
          {loadingAlerts ? (
            <p className="text-slate-400">Loading...</p>
          ) : errorAlerts ? (
            <p className="text-red-500 text-sm">Failed to load alerts.</p>
          ) : alerts.length === 0 ? (
            <p className="text-slate-400 text-sm">No active alerts.</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {alerts.slice(0, 8).map((a: any) => {
                const sev = SEVERITY[a.severity] ?? { card: 'border border-slate-200', text: 'text-slate-500' }
                return (
                  <div key={a.id} className={`px-3.5 py-2.5 rounded-lg ${sev.card}`}>
                    <div className="flex justify-between">
                      <span className="text-[13px] font-medium text-slate-900">
                        {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className={`text-[11px] font-semibold ${sev.text}`}>
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
                    <div className="text-xs text-slate-500 mt-[3px]">{a.notes}</div>
                    <div className="text-[11px] text-slate-400 mt-[3px]">{formatTime(a.triggered_at)}</div>
                  </div>
                )
              })}
              {alerts.length > 8 && (
                <Link href="/dashboard/alerts" className="text-[13px] text-blue-500">
                  View all {alerts.length} alerts →
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
