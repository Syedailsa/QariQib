'use client'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getTeachers, getStudents, createSchedule } from '@/lib/api'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function NewSchedulePage() {
  const router = useRouter()
  const { data: teachers = [] } = useQuery({ queryKey: ['teachers'], queryFn: getTeachers })
  const { data: students = [] } = useQuery({ queryKey: ['students'], queryFn: getStudents })

  const [form, setForm] = useState({
    teacher_id: '',
    student_ids: [] as string[],
    scheduled_start: '',
    scheduled_end: '',
    scheduled_duration_mins: 30,
    session_type: 'group'
  })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: createSchedule,
    onSuccess: (data) => {
      router.push(`/dashboard/schedules/${data.schedule_id}`)
    },
    onError: (e: any) => setError(e.response?.data?.detail || 'Failed to create class')
  })

  const toggleStudent = (id: string) => {
    setForm(f => ({
      ...f,
      student_ids: f.student_ids.includes(id)
        ? f.student_ids.filter(s => s !== id)
        : [...f.student_ids, id]
    }))
  }

  const handleSubmit = () => {
    if (!form.teacher_id) return setError('Please select a teacher')
    if (form.student_ids.length === 0) return setError('Please select at least one student')
    if (!form.scheduled_start || !form.scheduled_end) return setError('Please set start and end time')
    setError('')
    mutation.mutate(form)
  }

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: '700' }}>Schedule New Class</h2>
        <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
          Creates a Zoom meeting and registers all participants automatically
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Teacher selection */}
          <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px' }}>
              Select Teacher <span style={{ color: '#ef4444' }}>*</span>
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {teachers.length === 0 ? (
                <p style={{ color: '#94a3b8', fontSize: '14px' }}>No teachers found. Add teachers first.</p>
              ) : teachers.map((t: any) => (
                <label key={t.id} style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '10px 14px', borderRadius: '8px', cursor: 'pointer',
                  border: `1px solid ${form.teacher_id === t.id ? '#3b82f6' : '#e2e8f0'}`,
                  background: form.teacher_id === t.id ? '#eff6ff' : '#fff'
                }}>
                  <input
                    type='radio'
                    name='teacher'
                    value={t.id}
                    checked={form.teacher_id === t.id}
                    onChange={() => setForm(f => ({ ...f, teacher_id: t.id }))}
                  />
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: '500' }}>{t.full_name}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>{t.email}</div>
                    {!t.consent_given && (
                      <div style={{ fontSize: '11px', color: '#ef4444', marginTop: '2px' }}>
                        ⚠ Consent not given
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Date & Time */}
          <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px' }}>
              Date & Time <span style={{ color: '#ef4444' }}>*</span>
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
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
                  Duration (mins)
                </label>
                <input
                  type='number'
                  value={form.scheduled_duration_mins}
                  onChange={e => setForm(f => ({ ...f, scheduled_duration_mins: parseInt(e.target.value) }))}
                  style={{
                    width: '100%', padding: '8px 12px', border: '1px solid #e2e8f0',
                    borderRadius: '8px', fontSize: '14px', outline: 'none'
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right column — student selection */}
        <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '4px' }}>
            Select Students <span style={{ color: '#ef4444' }}>*</span>
          </h3>
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
            {form.student_ids.length} selected
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '480px', overflowY: 'auto' }}>
            {students.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '14px' }}>No students found. Add students first.</p>
            ) : students.map((s: any) => (
              <label key={s.id} style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '10px 14px', borderRadius: '8px', cursor: 'pointer',
                border: `1px solid ${form.student_ids.includes(s.id) ? '#3b82f6' : '#e2e8f0'}`,
                background: form.student_ids.includes(s.id) ? '#eff6ff' : '#fff'
              }}>
                <input
                  type='checkbox'
                  checked={form.student_ids.includes(s.id)}
                  onChange={() => toggleStudent(s.id)}
                />
                <div>
                  <div style={{ fontSize: '14px', fontWeight: '500' }}>{s.full_name}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>{s.email || 'No email'}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <button
          onClick={handleSubmit}
          disabled={mutation.isPending}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '12px 32px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '15px', fontWeight: '600'
          }}
        >
          {mutation.isPending ? 'Creating Class...' : 'Create Class & Schedule Zoom'}
        </button>
        <button
          onClick={() => router.back()}
          style={{
            background: '#f1f5f9', color: '#374151', border: 'none',
            padding: '12px 24px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}