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
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold">Teachers</h2>
          <p className="text-slate-500 text-sm mt-1">Manage teacher accounts and consent</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-500 text-white border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
        >
          + Add Teacher
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl p-6 shadow-sm mb-6">
          <h3 className="text-base font-semibold mb-4">New Teacher</h3>
          {error && (
            <div className="bg-red-50 text-red-600 px-3.5 py-2.5 rounded-lg mb-4 text-sm">{error}</div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { key: 'full_name',    label: 'Full Name',    required: true  },
              { key: 'email',        label: 'Email',        required: true  },
              { key: 'phone',        label: 'Phone',        required: false },
              { key: 'zoom_user_id', label: 'Zoom User ID', required: false },
            ].map(field => (
              <div key={field.key}>
                <label className="text-[13px] font-medium text-gray-700 block mb-1.5">
                  {field.label} {field.required && <span className="text-red-500">*</span>}
                </label>
                <input
                  value={(form as any)[field.key]}
                  onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-5">
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={createMutation.isPending}
              className="bg-blue-500 text-white border-none px-6 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
            >
              {createMutation.isPending ? 'Saving...' : 'Save Teacher'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="bg-slate-100 text-gray-700 border-none px-6 py-2.5 rounded-lg cursor-pointer text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-slate-400">Loading...</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {['Name', 'Email', 'Phone', 'Zoom ID', 'Consent'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[13px] font-semibold text-gray-700">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {teachers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-400 text-sm">
                    No teachers yet. Add your first teacher above.
                  </td>
                </tr>
              ) : teachers.map((t: any) => (
                <tr key={t.id} className="border-b border-slate-50">
                  <td className="px-4 py-3.5 text-sm font-medium">{t.full_name}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{t.email}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{t.phone || '—'}</td>
                  <td className="px-4 py-3.5 text-[13px] text-slate-400 font-mono">{t.zoom_user_id || '—'}</td>
                  <td className="px-4 py-3.5">
                    <button
                      onClick={() => consentMutation.mutate({ id: t.id, consent: !t.consent_given })}
                      className={`text-xs font-medium px-3 py-1 rounded-full border-none cursor-pointer ${
                        t.consent_given ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                      }`}
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
