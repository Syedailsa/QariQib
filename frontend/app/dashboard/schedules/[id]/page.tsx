'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSchedule, resolveAlert } from '@/lib/api'
import { formatTime, formatDateTime } from '@/lib/time'
import { useParams } from 'next/navigation'

const STATUS_BADGE: Record<string, string> = {
  scheduled: 'bg-blue-500/10 text-blue-500',
  live:       'bg-green-500/10 text-green-500',
  completed:  'bg-slate-500/10 text-slate-500',
  missed:     'bg-red-500/10 text-red-500',
}

const SEVERITY: Record<string, { card: string; text: string; badge: string }> = {
  high:   { card: 'border border-red-500/25 bg-red-500/5',       text: 'text-red-500',    badge: 'bg-red-500/10 text-red-500'       },
  medium: { card: 'border border-orange-500/25 bg-orange-500/5', text: 'text-orange-500', badge: 'bg-orange-500/10 text-orange-500' },
  low:    { card: 'border border-yellow-500/25 bg-yellow-500/5', text: 'text-yellow-500', badge: 'bg-yellow-500/10 text-yellow-500' },
}

const ATTENDANCE_BADGE: Record<string, string> = {
  present:         'bg-green-500/10 text-green-500',
  late:            'bg-orange-500/10 text-orange-500',
  absent:          'bg-red-500/10 text-red-500',
  early_departure: 'bg-violet-500/10 text-violet-500',
}

export default function ScheduleDetailPage() {
  const { id } = useParams()
  const qc = useQueryClient()

  const { data: schedule, isLoading, isError } = useQuery({
    queryKey: ['schedule', id],
    queryFn: () => getSchedule(id as string),
    // Only poll when the class is active — stop once completed or missed
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'live' || status === 'scheduled' ? 5000 : false
    }
  })

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedule', id] })
  })

  if (isLoading) return <p className="text-slate-400">Loading...</p>
  if (isError) return (
    <div className="bg-red-50 rounded-xl p-6">
      <p className="text-red-600 text-sm">Failed to load schedule. Check your backend connection.</p>
    </div>
  )
  if (!schedule) return <p className="text-red-500">Schedule not found</p>

  const unresolvedAlerts = schedule.alerts?.filter((a: any) => !a.is_resolved) || []
  const resolvedAlerts = schedule.alerts?.filter((a: any) => a.is_resolved) || []

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-2xl font-bold">{schedule.teachers?.full_name}</h2>
          <span className={`text-xs font-semibold px-3.5 py-1 rounded-full ${STATUS_BADGE[schedule.status] ?? 'bg-slate-100 text-slate-500'}`}>
            {schedule.status.toUpperCase()}
          </span>
        </div>
        <p className="text-slate-500 text-sm">
          {formatDateTime(schedule.scheduled_start)} →{' '}
          {formatTime(schedule.scheduled_end)}
          {' · '}{schedule.scheduled_duration_mins} mins scheduled
        </p>
        {schedule.actual_duration_mins && (
          <p className="text-sm mt-1">
            <span className="text-slate-500">Actual duration: </span>
            <span className="font-semibold">{schedule.actual_duration_mins} mins</span>
            {schedule.duration_diff_mins !== null && schedule.duration_diff_mins !== 0 && (
              <span className={`ml-2 text-[13px] font-semibold ${schedule.duration_diff_mins < 0 ? 'text-red-500' : 'text-green-500'}`}>
                · {schedule.duration_diff_mins < 0
                  ? `ended ${Math.abs(schedule.duration_diff_mins)} mins early`
                  : `ran ${schedule.duration_diff_mins} mins over`}
              </span>
            )}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Attendance */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h3 className="text-base font-semibold mb-4">
            Attendance ({schedule.attendance_records?.length || 0})
          </h3>
          {!schedule.attendance_records?.length ? (
            <p className="text-slate-400 text-sm">No attendance records yet.</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {schedule.attendance_records.map((a: any) => (
                <div key={a.id} className="px-3.5 py-3 rounded-lg border border-slate-100 bg-slate-50">
                  <div className="flex justify-between items-center">
                    <div>
                      <span className={`text-[11px] font-semibold px-2 py-px rounded-full mr-2 ${
                        a.participant_type === 'teacher' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                      }`}>
                        {a.participant_type.toUpperCase()}
                      </span>
                      <span className="text-[13px] text-gray-700">
                        {a.join_time ? formatTime(a.join_time) : '—'}
                        {a.leave_time ? ` → ${formatTime(a.leave_time)}` : ' → still in'}
                      </span>
                    </div>
                    <span className={`text-[11px] font-semibold px-2.5 py-px rounded-full ${ATTENDANCE_BADGE[a.status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {a.status.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  {a.duration_mins !== null && (
                    <div className="text-xs text-slate-400 mt-1">Duration: {a.duration_mins} mins</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Enrolled Students */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h3 className="text-base font-semibold mb-4">
            Enrolled Students ({schedule.class_students?.length || 0})
          </h3>
          {!schedule.class_students?.length ? (
            <p className="text-slate-400 text-sm">No students enrolled.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {schedule.class_students.map((cs: any) => (
                <div key={cs.id} className="px-3.5 py-2.5 rounded-lg border border-slate-100 bg-slate-50 flex justify-between items-center">
                  <div>
                    <div className="text-sm font-medium">{cs.students?.full_name}</div>
                    <div className="text-xs text-slate-400">{cs.students?.email || 'No email'}</div>
                  </div>
                  {cs.zoom_join_url && schedule.status !== 'missed' && schedule.status !== 'completed' && (
                    <a
                      href={cs.zoom_join_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-500 no-underline"
                    >
                      Join Link →
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Alerts */}
      {(unresolvedAlerts.length > 0 || resolvedAlerts.length > 0) && (
        <div className="bg-white rounded-xl p-6 shadow-sm mt-6">
          <h3 className="text-base font-semibold mb-4">
            Alerts ({unresolvedAlerts.length} active)
          </h3>
          <div className="flex flex-col gap-2.5">
            {[...unresolvedAlerts, ...resolvedAlerts].map((a: any) => {
              const sev = SEVERITY[a.severity] ?? { card: 'border border-slate-200', text: 'text-slate-500', badge: 'bg-slate-100 text-slate-500' }
              return (
                <div key={a.id} className={`px-4 py-3 rounded-lg flex justify-between items-center ${
                  a.is_resolved ? 'border border-slate-200 bg-slate-50 opacity-60' : sev.card
                }`}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${a.is_resolved ? 'text-slate-500' : sev.text}`}>
                        {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className={`text-[11px] px-2 py-px rounded-full ${a.is_resolved ? 'bg-slate-200 text-slate-500' : sev.badge}`}>
                        {a.severity}
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
                    <div className="text-[13px] text-slate-500 mt-[3px]">{a.notes}</div>
                    <div className="text-[11px] text-slate-400 mt-[3px]">
                      {formatTime(a.triggered_at)}
                      {a.is_resolved && a.resolved_at && ` · Resolved ${formatTime(a.resolved_at)}`}
                    </div>
                  </div>
                  {!a.is_resolved && (
                    <button
                      onClick={() => resolveMutation.mutate(a.id)}
                      disabled={resolveMutation.isPending}
                      className="text-xs font-medium px-3.5 py-1.5 rounded-lg border border-green-500 bg-green-500 cursor-pointer text-white shrink-0 ml-4"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
