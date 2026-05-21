'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlerts, resolveAlert } from '@/lib/api'
import { formatTime } from '@/lib/time'
import { format } from 'date-fns'
import { useState } from 'react'
import Link from 'next/link'

const SEVERITY_COLORS: Record<string, string> = {
  high:   '#ef4444',
  medium: '#f97316',
  low:    '#eab308',
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: '700' }}>Alerts</h2>
          <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
            {alerts.length} {showResolved ? 'resolved' : 'active'} alerts
          </p>
        </div>
        <button
          onClick={() => setShowResolved(!showResolved)}
          style={{
            background: '#f1f5f9', color: '#374151', border: 'none',
            padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '14px', fontWeight: '500'
          }}
        >
          {showResolved ? 'Show Active' : 'Show Resolved'}
        </button>
      </div>

      {isLoading ? (
        <p style={{ color: '#94a3b8' }}>Loading...</p>
      ) : isError ? (
        <div style={{
          background: '#fef2f2', borderRadius: '12px', padding: '24px',
          textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <p style={{ color: '#dc2626', fontSize: '14px' }}>
            Failed to load alerts. Check your backend connection.
          </p>
        </div>
      ) : alerts.length === 0 ? (
        <div style={{
          background: '#fff', borderRadius: '12px', padding: '48px',
          textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <p style={{ color: '#94a3b8', fontSize: '15px' }}>
            {showResolved ? 'No resolved alerts.' : '✓ No active alerts.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {alerts.map((a: any) => (
            <div key={a.id} style={{
              background: '#fff', borderRadius: '12px', padding: '20px 24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              borderLeft: `4px solid ${SEVERITY_COLORS[a.severity]}`
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                    {/* Alert type */}
                    <span style={{
                      fontSize: '13px', fontWeight: '700',
                      color: SEVERITY_COLORS[a.severity]
                    }}>
                      {a.alert_type.replace(/_/g, ' ').toUpperCase()}
                    </span>

                    {/* Severity badge */}
                    <span style={{
                      fontSize: '11px', padding: '2px 8px', borderRadius: '99px',
                      background: SEVERITY_COLORS[a.severity] + '20',
                      color: SEVERITY_COLORS[a.severity], fontWeight: '600'
                    }}>
                      {a.severity.toUpperCase()}
                    </span>

                    {(a.teachers || a.students) && (
                      <span style={{
                        fontSize: '11px', padding: '2px 10px', borderRadius: '99px',
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
                  <p style={{ fontSize: '14px', color: '#374151', marginBottom: '8px' }}>
                    {a.notes}
                  </p>
                  <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#94a3b8' }}>
                    <span>{formatTime(a.triggered_at)}</span>
                    {a.class_schedules && (
                      <Link
                        href={`/dashboard/schedules/${a.class_schedules.id}`}
                        style={{ color: '#3b82f6', textDecoration: 'none' }}
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
                    style={{
                      fontSize: '13px', fontWeight: '500', padding: '8px 18px',
                      borderRadius: '8px', border: '1px solid #e2e8f0',
                      background: '#fff', cursor: 'pointer', color: '#374151',
                      flexShrink: 0, marginLeft: '20px'
                    }}
                  >
                    Resolve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}