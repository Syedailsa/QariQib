// app/dashboard/page.tsx
'use client'
import { useQuery } from '@tanstack/react-query'
import { getTodaySchedules, getAlerts } from '@/lib/api'
import { formatTime } from '@/lib/time'
import { format } from 'date-fns'
import Link from 'next/link'

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

export default function DashboardPage() {
  const { data: schedules = [], isLoading: loadingSchedules, isError: errorSchedules } =
    useQuery({ queryKey: ['today-schedules'], queryFn: getTodaySchedules })

  const { data: alerts = [], isLoading: loadingAlerts, isError: errorAlerts } =
    useQuery({ queryKey: ['alerts'], queryFn: () => getAlerts(false) })

  return (
    <div>
      <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '8px' }}>
        Today's Overview
      </h2>
      <p style={{ color: '#64748b', marginBottom: '32px' }}>
        {format(new Date(), 'EEEE, MMMM d yyyy')}
      </p>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '32px' }}>
        {[
          { label: 'Total Classes Today', value: schedules.length, color: '#3b82f6' },
          { label: 'Live Now', value: schedules.filter((s: any) => s.status === 'live').length, color: '#22c55e' },
          { label: 'Completed', value: schedules.filter((s: any) => s.status === 'completed').length, color: '#64748b' },
          { label: 'Unresolved Alerts', value: alerts.length, color: '#ef4444' },
        ].map(stat => (
          <div key={stat.label} style={{
            background: '#fff',
            borderRadius: '12px',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            borderLeft: `4px solid ${stat.color}`
          }}>
            <div style={{ fontSize: '28px', fontWeight: '700', color: stat.color }}>
              {stat.value}
            </div>
            <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Today's schedule */}
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
            Today's Classes
          </h3>
          {loadingSchedules ? (
            <p style={{ color: '#94a3b8' }}>Loading...</p>
          ) : errorSchedules ? (
            <p style={{ color: '#ef4444', fontSize: '14px' }}>Failed to load schedules. Check backend connection.</p>
          ) : schedules.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>No classes scheduled today.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {schedules.map((s: any) => (
                <Link
                  key={s.id}
                  href={`/dashboard/schedules/${s.id}`}
                  style={{ textDecoration: 'none' }}
                >
                  <div style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: '500', color: '#0f172a' }}>
                          {s.teachers?.full_name}
                        </div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                          {formatTime(s.scheduled_start)} →{' '}
                          {formatTime(s.scheduled_end)}
                          {' · '}{s.scheduled_duration_mins} mins
                        </div>
                      </div>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: '500',
                        padding: '3px 10px',
                        borderRadius: '99px',
                        background: STATUS_COLORS[s.status] + '20',
                        color: STATUS_COLORS[s.status]
                      }}>
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
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>
            Active Alerts
          </h3>
          {loadingAlerts ? (
            <p style={{ color: '#94a3b8' }}>Loading...</p>
          ) : errorAlerts ? (
            <p style={{ color: '#ef4444', fontSize: '14px' }}>Failed to load alerts.</p>
          ) : alerts.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>No active alerts.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {alerts.slice(0, 8).map((a: any) => (
                <div key={a.id} style={{
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: `1px solid ${SEVERITY_COLORS[a.severity]}40`,
                  background: SEVERITY_COLORS[a.severity] + '08'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '13px', fontWeight: '500', color: '#0f172a' }}>
                      {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span style={{
                      fontSize: '11px',
                      color: SEVERITY_COLORS[a.severity],
                      fontWeight: '600'
                    }}>
                      {a.severity.toUpperCase()}
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
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '3px' }}>
                    {a.notes}
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '3px' }}>
                    {formatTime(a.triggered_at)}
                  </div>
                </div>
              ))}
              {alerts.length > 8 && (
                <Link href='/dashboard/alerts' style={{ fontSize: '13px', color: '#3b82f6' }}>
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