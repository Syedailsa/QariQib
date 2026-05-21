'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSchedules, deleteSchedule } from '@/lib/api'
import { formatTime, formatDateHeader } from '@/lib/time'
import { format } from 'date-fns'
import Link from 'next/link'
import { useState } from 'react'

const STATUS_CONFIG: Record<string, { bg: string, border: string, badge: string, text: string }> = {
  scheduled: {
    bg:     '#fefce8',
    border: '#fde047',
    badge:  '#854d0e',
    text:   '#713f12'
  },
  live: {
    bg:     '#f0fdf4',
    border: '#86efac',
    badge:  '#15803d',
    text:   '#14532d'
  },
  completed: {
    bg:     '#f0fdf4',
    border: '#4ade80',
    badge:  '#166534',
    text:   '#14532d'
  },
  missed: {
    bg:     '#fef2f2',
    border: '#fca5a5',
    badge:  '#dc2626',
    text:   '#7f1d1d'
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

  // Group by date
  const grouped = schedules.reduce((acc: Record<string, any[]>, s: any) => {
    const date = format(new Date(s.scheduled_start), 'yyyy-MM-dd')
    if (!acc[date]) acc[date] = []
    acc[date].push(s)
    return acc
  }, {} as Record<string, any[]>)

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: '700' }}>All Schedules</h2>
          <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
            {schedules.length} total classes
          </p>
        </div>
        <Link href='/dashboard/schedules/new'>
          <button style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '14px', fontWeight: '500'
          }}>
            + New Class
          </button>
        </Link>
      </div>

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#fff', borderRadius: '12px', padding: '28px',
            width: '380px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)'
          }}>
            <h3 style={{ fontSize: '17px', fontWeight: '600', marginBottom: '8px' }}>
              Delete this class?
            </h3>
            <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '12px' }}>
              This will delete the Zoom meeting and all attendance records. This cannot be undone.
            </p>
            {deleteError && (
              <p style={{ fontSize: '13px', color: '#dc2626', marginBottom: '12px' }}>{deleteError}</p>
            )}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => deleteMutation.mutate(confirmDelete)}
                disabled={deleteMutation.isPending}
                style={{
                  background: '#ef4444', color: '#fff', border: 'none',
                  padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
                  fontSize: '14px', fontWeight: '500', flex: 1
                }}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
              </button>
              <button
                onClick={() => setConfirmDelete(null)}
                style={{
                  background: '#f1f5f9', color: '#374151', border: 'none',
                  padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
                  fontSize: '14px', flex: 1
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <p style={{ color: '#94a3b8' }}>Loading...</p>
      ) : isError ? (
        <div style={{
          background: '#fef2f2', borderRadius: '12px', padding: '32px',
          textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <p style={{ color: '#dc2626', fontSize: '14px' }}>
            Failed to load schedules. Check your backend connection.
          </p>
        </div>
      ) : schedules.length === 0 ? (
        <div style={{
          background: '#fff', borderRadius: '12px', padding: '48px',
          textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <p style={{ color: '#94a3b8', fontSize: '15px' }}>
            No classes scheduled yet.{' '}
            <Link href='/dashboard/schedules/new' style={{ color: '#3b82f6' }}>
              Create your first class →
            </Link>
          </p>
        </div>
      ) : (
        (Object.entries(grouped) as [string, any[]][])
          .sort(([a], [b]) => b.localeCompare(a))
          .map(([date, daySchedules]: [string, any[]]) => (
            <div key={date} style={{ marginBottom: '32px' }}>
              {/* Date header */}
              <div style={{
                fontSize: '13px', fontWeight: '600', color: '#64748b',
                textTransform: 'uppercase', letterSpacing: '0.06em',
                marginBottom: '12px', paddingBottom: '8px',
                borderBottom: '1px solid #e2e8f0'
              }}>
                {formatDateHeader(date + 'T12:00:00')}
              </div>

              {/* Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '16px'
              }}>
                {daySchedules.map((s: any) => {
                  const cfg = STATUS_CONFIG[s.status] || STATUS_CONFIG.scheduled
                  const alertCount = s.alerts?.filter((a: any) => !a.is_resolved).length || 0

                  return (
                    <div key={s.id} style={{
                      background: cfg.bg,
                      border: `1.5px solid ${cfg.border}`,
                      borderRadius: '12px',
                      padding: '18px',
                      position: 'relative',
                    }}>
                      {/* Status badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                        <span style={{
                          fontSize: '11px', fontWeight: '700', padding: '3px 10px',
                          borderRadius: '99px', background: cfg.badge + '20',
                          color: cfg.badge, letterSpacing: '0.04em'
                        }}>
                          {s.status === 'live' ? '🟢 LIVE' : s.status.toUpperCase()}
                        </span>
                        {alertCount > 0 && (
                          <span style={{
                            fontSize: '11px', fontWeight: '700', padding: '3px 10px',
                            borderRadius: '99px', background: '#fef2f2',
                            color: '#dc2626'
                          }}>
                            🔔 {alertCount} alert{alertCount > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>

                      {/* Teacher */}
                      <div style={{ fontSize: '15px', fontWeight: '600', color: cfg.text, marginBottom: '4px' }}>
                        {s.teachers?.full_name}
                      </div>

                      {/* Time */}
                      <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>
                        {formatTime(s.scheduled_start)} →{' '}
                        {formatTime(s.scheduled_end)}
                        {' · '}{s.scheduled_duration_mins} mins
                      </div>

                      {/* Students count */}
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '12px' }}>
                        👥 {s.class_students?.length || 0} students enrolled
                      </div>

                      {/* Duration diff if completed */}
                      {s.actual_duration_mins && (
                        <div style={{ fontSize: '12px', marginBottom: '12px' }}>
                          <span style={{ color: '#64748b' }}>Actual: </span>
                          <span style={{ fontWeight: '600', color: cfg.text }}>
                            {s.actual_duration_mins} mins
                          </span>
                          {s.duration_diff_mins !== null && (
                            <span style={{
                              marginLeft: '6px',
                              color: s.duration_diff_mins < 0 ? '#ef4444' : '#22c55e',
                              fontWeight: '600'
                            }}>
                              ({s.duration_diff_mins > 0 ? '+' : ''}{s.duration_diff_mins})
                            </span>
                          )}
                        </div>
                      )}

                      {/* Actions */}
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <Link
                          href={`/dashboard/schedules/${s.id}`}
                          style={{ flex: 1, textDecoration: 'none' }}
                        >
                          <button style={{
                            width: '100%', padding: '7px', borderRadius: '7px',
                            border: `1px solid ${cfg.border}`, background: '#fff',
                            cursor: 'pointer', fontSize: '12px', fontWeight: '500',
                            color: cfg.badge
                          }}>
                            View Details
                          </button>
                        </Link>

                        {s.status === 'scheduled' && (
                          <>
                            <Link href={`/dashboard/schedules/${s.id}/edit`} style={{ textDecoration: 'none' }}>
                              <button style={{
                                padding: '7px 12px', borderRadius: '7px',
                                border: '1px solid #e2e8f0', background: '#fff',
                                cursor: 'pointer', fontSize: '12px', color: '#374151'
                              }}>
                                ✏️
                              </button>
                            </Link>
                            <button
                              onClick={() => setConfirmDelete(s.id)}
                              style={{
                                padding: '7px 12px', borderRadius: '7px',
                                border: '1px solid #fca5a5', background: '#fff',
                                cursor: 'pointer', fontSize: '12px', color: '#dc2626'
                              }}
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