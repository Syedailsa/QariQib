'use client'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getSchedule, updateSchedule } from '@/lib/api'
import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { format } from 'date-fns'

export default function EditSchedulePage() {
  const { id } = useParams()
  const router = useRouter()

  const { data: schedule, isLoading } = useQuery({
    queryKey: ['schedule', id],
    queryFn: () => getSchedule(id as string)
  })

  const [form, setForm] = useState({
    scheduled_start: '',
    scheduled_end: '',
  })
  const [error, setError] = useState('')

  const calcDuration = (() => {
    if (!form.scheduled_start || !form.scheduled_end) return 0
    const mins = Math.round(
      (new Date(form.scheduled_end).getTime() - new Date(form.scheduled_start).getTime()) / 60000
    )
    return mins > 0 ? mins : 0
  })()

  useEffect(() => {
    if (schedule) {
      // Convert to local datetime-local format
      const toLocal = (iso: string) => {
        const d = new Date(iso)
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
      }
      setForm({
        scheduled_start: toLocal(schedule.scheduled_start),
        scheduled_end: toLocal(schedule.scheduled_end),
      })
    }
  }, [schedule])

  const mutation = useMutation({
    mutationFn: (data: typeof form) => updateSchedule(id as string, {
      scheduled_start: new Date(data.scheduled_start).toISOString(),
      scheduled_end: new Date(data.scheduled_end).toISOString(),
      scheduled_duration_mins: calcDuration,
    }),
    onSuccess: () => router.push(`/dashboard/schedules/${id}`),
    onError: (e: any) => setError(e.response?.data?.detail || 'Failed to update')
  })

  if (isLoading) return <p style={{ color: '#94a3b8' }}>Loading...</p>
  if (!schedule) return <p style={{ color: '#ef4444' }}>Schedule not found</p>

  if (schedule.status !== 'scheduled') {
    return (
      <div style={{ background: '#fef2f2', borderRadius: '12px', padding: '24px' }}>
        <p style={{ color: '#dc2626', fontSize: '15px' }}>
          Cannot edit a class with status: <strong>{schedule.status}</strong>
        </p>
        <button
          onClick={() => router.back()}
          style={{ marginTop: '16px', padding: '8px 20px', borderRadius: '8px', border: '1px solid #e2e8f0', cursor: 'pointer', background: '#fff' }}
        >
          Go Back
        </button>
      </div>
    )
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: '700' }}>Edit Class</h2>
        <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
          Teacher: {schedule.teachers?.full_name}
        </p>
      </div>

      {error && (
        <div style={{
          background: '#fef2f2', color: '#dc2626', padding: '12px 16px',
          borderRadius: '8px', marginBottom: '20px', fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      <div style={{ background: '#fff', borderRadius: '12px', padding: '28px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', maxWidth: '480px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div>
            <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '6px' }}>
              Start Time
            </label>
            <input
              type='datetime-local'
              value={form.scheduled_start}
              onChange={e => setForm(f => ({ ...f, scheduled_start: e.target.value }))}
              style={{
                width: '100%', padding: '8px 12px', border: '1px solid #e2e8f0',
                borderRadius: '8px', fontSize: '14px', outline: 'none'
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '6px' }}>
              End Time
            </label>
            <input
              type='datetime-local'
              value={form.scheduled_end}
              onChange={e => setForm(f => ({ ...f, scheduled_end: e.target.value }))}
              style={{
                width: '100%', padding: '8px 12px', border: '1px solid #e2e8f0',
                borderRadius: '8px', fontSize: '14px', outline: 'none'
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '6px' }}>
              Duration
            </label>
            <div style={{
              padding: '8px 12px',
              border: `1px solid ${calcDuration > 0 && calcDuration < 15 ? '#fca5a5' : '#e2e8f0'}`,
              borderRadius: '8px', fontSize: '14px',
              background: '#f8fafc',
              color: calcDuration === 0 ? '#94a3b8' : calcDuration < 15 ? '#ef4444' : '#0f172a',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}>
              <span>
                {calcDuration === 0 ? 'Set start and end time' : `${calcDuration} minutes`}
              </span>
              {calcDuration > 0 && calcDuration < 15 && (
                <span style={{ fontSize: '12px', color: '#ef4444', fontWeight: '500' }}>
                  ⚠ Minimum 15 mins
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
          <button
            onClick={() => {
              if (calcDuration < 15) return setError('Class duration cannot be less than 15 minutes. Please set a later end time.')
              mutation.mutate(form)
            }}
            disabled={mutation.isPending}
            style={{
              background: '#3b82f6', color: '#fff', border: 'none',
              padding: '10px 28px', borderRadius: '8px', cursor: 'pointer',
              fontSize: '14px', fontWeight: '500'
            }}
          >
            {mutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={() => router.back()}
            style={{
              background: '#f1f5f9', color: '#374151', border: 'none',
              padding: '10px 24px', borderRadius: '8px', cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}