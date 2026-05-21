'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSchedule, resolveAlert } from '@/lib/api'
import { formatTime, formatDateTime } from '@/lib/time'
import { useParams } from 'next/navigation'

const STATUS_COLORS: Record<string, string> = {
  scheduled: '#3b82f6',
  live:       '#22c55e',
  completed:  '#64748b',
  missed:     '#ef4444',
}

const SEVERITY_COLORS: Record<string, string> = {
  high:   '#ef4444',
  medium: '#f97316',
  low:    '#eab308',
}

const ATTENDANCE_COLORS: Record<string, string> = {
  present:          '#22c55e',
  late:             '#f97316',
  absent:           '#ef4444',
  early_departure:  '#8b5cf6',
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
      return status === 'live' || status === 'scheduled' ? 15000 : false
    }
  })

  const resolveMutation = useMutation({
    mutationFn: resolveAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedule', id] })
  })

  if (isLoading) return <p style={{ color: '#94a3b8' }}>Loading...</p>
  if (isError) return (
    <div style={{ background: '#fef2f2', borderRadius: '12px', padding: '24px' }}>
      <p style={{ color: '#dc2626', fontSize: '14px' }}>Failed to load schedule. Check your backend connection.</p>
    </div>
  )
  if (!schedule) return <p style={{ color: '#ef4444' }}>Schedule not found</p>

  const unresolvedAlerts = schedule.alerts?.filter((a: any) => !a.is_resolved) || []
  const resolvedAlerts = schedule.alerts?.filter((a: any) => a.is_resolved) || []

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: '700' }}>
            {schedule.teachers?.full_name}
          </h2>
          <span style={{
            fontSize: '12px', fontWeight: '600', padding: '4px 14px',
            borderRadius: '99px',
            background: STATUS_COLORS[schedule.status] + '20',
            color: STATUS_COLORS[schedule.status]
          }}>
            {schedule.status.toUpperCase()}
          </span>
        </div>
        <p style={{ color: '#64748b', fontSize: '14px' }}>
          {formatDateTime(schedule.scheduled_start)} →{' '}
          {formatTime(schedule.scheduled_end)}
          {' · '}{schedule.scheduled_duration_mins} mins scheduled
        </p>
        {schedule.actual_duration_mins && (
          <p style={{ fontSize: '14px', marginTop: '4px' }}>
            <span style={{ color: '#64748b' }}>Actual duration: </span>
            <span style={{ fontWeight: '600' }}>{schedule.actual_duration_mins} mins</span>
            <span style={{
              marginLeft: '8px', fontSize: '13px',
              color: schedule.duration_diff_mins < 0 ? '#ef4444' : '#22c55e'
            }}>
              ({schedule.duration_diff_mins > 0 ? '+' : ''}{schedule.duration_diff_mins} mins)
            </span>
          </p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>

        {/* Attendance */}
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
            Attendance ({schedule.attendance_records?.length || 0})
          </h3>
          {!schedule.attendance_records?.length ? (
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>No attendance records yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {schedule.attendance_records.map((a: any) => (
                <div key={a.id} style={{
                  padding: '12px 14px', borderRadius: '8px',
                  border: '1px solid #f1f5f9', background: '#fafafa'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{
                        fontSize: '11px', fontWeight: '600', padding: '2px 8px',
                        borderRadius: '99px', marginRight: '8px',
                        background: a.participant_type === 'teacher' ? '#dbeafe' : '#f0fdf4',
                        color: a.participant_type === 'teacher' ? '#1d4ed8' : '#15803d'
                      }}>
                        {a.participant_type.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '13px', color: '#374151' }}>
                        {a.join_time ? formatTime(a.join_time) : '—'}
                        {a.leave_time ? ` → ${formatTime(a.leave_time)}` : ' → still in'}
                      </span>
                    </div>
                    <span style={{
                      fontSize: '11px', fontWeight: '600', padding: '2px 10px',
                      borderRadius: '99px',
                      background: ATTENDANCE_COLORS[a.status] + '20',
                      color: ATTENDANCE_COLORS[a.status]
                    }}>
                      {a.status.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  {a.duration_mins !== null && (
                    <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                      Duration: {a.duration_mins} mins
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Enrolled Students */}
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
            Enrolled Students ({schedule.class_students?.length || 0})
          </h3>
          {!schedule.class_students?.length ? (
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>No students enrolled.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {schedule.class_students.map((cs: any) => (
                <div key={cs.id} style={{
                  padding: '10px 14px', borderRadius: '8px',
                  border: '1px solid #f1f5f9', background: '#fafafa',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: '500' }}>
                      {cs.students?.full_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {cs.students?.email || 'No email'}
                    </div>
                  </div>
                  {cs.zoom_join_url && schedule.status !== 'missed' && schedule.status !== 'completed' && (
                    <a
                      href={cs.zoom_join_url}
                      target='_blank'
                      rel='noopener noreferrer'
                      style={{ fontSize: '12px', color: '#3b82f6', textDecoration: 'none' }}
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
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', marginTop: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
            Alerts ({unresolvedAlerts.length} active)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[...unresolvedAlerts, ...resolvedAlerts].map((a: any) => (
              <div key={a.id} style={{
                padding: '12px 16px', borderRadius: '8px',
                border: `1px solid ${a.is_resolved ? '#e2e8f0' : SEVERITY_COLORS[a.severity] + '40'}`,
                background: a.is_resolved ? '#f8fafc' : SEVERITY_COLORS[a.severity] + '08',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                opacity: a.is_resolved ? 0.6 : 1
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      fontSize: '12px', fontWeight: '600',
                      color: a.is_resolved ? '#64748b' : SEVERITY_COLORS[a.severity]
                    }}>
                      {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span style={{
                      fontSize: '11px', padding: '1px 8px', borderRadius: '99px',
                      background: a.is_resolved ? '#e2e8f0' : SEVERITY_COLORS[a.severity] + '20',
                      color: a.is_resolved ? '#64748b' : SEVERITY_COLORS[a.severity]
                    }}>
                      {a.severity}
                    </span>
                    {(a.teachers || a.students) && (
                      <span style={{
                        fontSize: '11px', padding: '1px 10px', borderRadius: '99px',
                        background: a.teachers ? '#eff6ff' : '#f0fdf4',
                        color: a.teachers ? '#3b82f6' : '#16a34a',
                        fontWeight: '600', border: `1px solid ${a.teachers ? '#bfdbfe' : '#bbf7d0'}`
                      }}>
                        {a.teachers
                          ? `👨‍🏫 Teacher · ${a.teachers.full_name}`
                          : `👨‍🎓 Student · ${a.students?.full_name ?? 'Unknown'}`
                        }
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '13px', color: '#64748b', marginTop: '3px' }}>
                    {a.notes}
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '3px' }}>
                    {formatTime(a.triggered_at)}
                    {a.is_resolved && a.resolved_at && ` · Resolved ${formatTime(a.resolved_at)}`}
                  </div>
                </div>
                {!a.is_resolved && (
                  <button
                    onClick={() => resolveMutation.mutate(a.id)}
                    disabled={resolveMutation.isPending}
                    style={{
                      fontSize: '12px', fontWeight: '500', padding: '6px 14px',
                      borderRadius: '8px', border: '1px solid #e2e8f0',
                      background: '#fff', cursor: 'pointer', color: '#374151',
                      flexShrink: 0, marginLeft: '16px'
                    }}
                  >
                    Resolve
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}