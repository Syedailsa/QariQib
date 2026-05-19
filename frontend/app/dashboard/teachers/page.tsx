'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getTeachers, createTeacher, updateConsent } from '@/lib/api'
import { useState } from 'react'

export default function TeachersPage() {
  const qc = useQueryClient()
  const { data: teachers = [], isLoading } = useQuery({
    queryKey: ['teachers'],
    queryFn: getTeachers
  })

  const [form, setForm] = useState({
    full_name: '', email: '', phone: '', zoom_user_id: ''
  })
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')

  const createMutation = useMutation({
    mutationFn: createTeacher,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['teachers'] })
      setForm({ full_name: '', email: '', phone: '', zoom_user_id: '' })
      setShowForm(false)
      setError('')
    },
    onError: (e: any) => setError(e.response?.data?.detail || 'Failed to create teacher')
  })

  const consentMutation = useMutation({
    mutationFn: ({ id, consent }: { id: string, consent: boolean }) =>
      updateConsent(id, consent),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teachers'] })
  })

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: '700' }}>Teachers</h2>
          <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
            Manage teacher accounts and consent
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '14px', fontWeight: '500'
          }}
        >
          + Add Teacher
        </button>
      </div>

      {showForm && (
        <div style={{
          background: '#fff', borderRadius: '12px', padding: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)', marginBottom: '24px'
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>New Teacher</h3>
          {error && (
            <div style={{ background: '#fef2f2', color: '#dc2626', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }}>
              {error}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {[
              { key: 'full_name', label: 'Full Name', required: true },
              { key: 'email', label: 'Email', required: true },
              { key: 'phone', label: 'Phone', required: false },
              { key: 'zoom_user_id', label: 'Zoom User ID', required: false },
            ].map(field => (
              <div key={field.key}>
                <label style={{ fontSize: '13px', fontWeight: '500', color: '#374151', display: 'block', marginBottom: '6px' }}>
                  {field.label} {field.required && <span style={{ color: '#ef4444' }}>*</span>}
                </label>
                <input
                  value={(form as any)[field.key]}
                  onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))}
                  style={{
                    width: '100%', padding: '8px 12px', border: '1px solid #e2e8f0',
                    borderRadius: '8px', fontSize: '14px', outline: 'none'
                  }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={createMutation.isPending}
              style={{
                background: '#3b82f6', color: '#fff', border: 'none',
                padding: '10px 24px', borderRadius: '8px', cursor: 'pointer',
                fontSize: '14px', fontWeight: '500'
              }}
            >
              {createMutation.isPending ? 'Saving...' : 'Save Teacher'}
            </button>
            <button
              onClick={() => setShowForm(false)}
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
      )}

      {isLoading ? (
        <p style={{ color: '#94a3b8' }}>Loading...</p>
      ) : (
        <div style={{ background: '#fff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                {['Name', 'Email', 'Phone', 'Zoom ID', 'Consent'].map(h => (
                  <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '13px', fontWeight: '600', color: '#374151' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {teachers.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '14px' }}>
                    No teachers yet. Add your first teacher above.
                  </td>
                </tr>
              ) : teachers.map((t: any) => (
                <tr key={t.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '14px 16px', fontSize: '14px', fontWeight: '500' }}>{t.full_name}</td>
                  <td style={{ padding: '14px 16px', fontSize: '14px', color: '#64748b' }}>{t.email}</td>
                  <td style={{ padding: '14px 16px', fontSize: '14px', color: '#64748b' }}>{t.phone || '—'}</td>
                  <td style={{ padding: '14px 16px', fontSize: '13px', color: '#94a3b8', fontFamily: 'monospace' }}>
                    {t.zoom_user_id || '—'}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <button
                      onClick={() => consentMutation.mutate({ id: t.id, consent: !t.consent_given })}
                      style={{
                        fontSize: '12px', fontWeight: '500', padding: '4px 12px',
                        borderRadius: '99px', border: 'none', cursor: 'pointer',
                        background: t.consent_given ? '#dcfce7' : '#fee2e2',
                        color: t.consent_given ? '#16a34a' : '#dc2626'
                      }}
                    >
                      {t.consent_given ? '✓ Given' : '✗ Pending'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}