'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getStudents, createStudent, deleteStudent } from '@/lib/api'
import { useState } from 'react'

export default function StudentsPage() {
  const qc = useQueryClient()
  const { data: students = [], isLoading } = useQuery({
    queryKey: ['students'],
    queryFn: getStudents
  })

  const emptyForm = {
    first_name: '', last_name: '', email: '', parent_name: '', parent_email: '', parent_phone: ''
  }
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState('')

  const createMutation = useMutation({
    mutationFn: () => createStudent({
      full_name: `${form.first_name.trim()} ${form.last_name.trim()}`.trim(),
      email:        form.email       || undefined,
      parent_name:  form.parent_name || undefined,
      parent_email: form.parent_email || undefined,
      parent_phone: form.parent_phone || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['students'] })
      setForm(emptyForm)
      setShowForm(false)
      setError('')
    },
    onError: (e: any) => setError(e.response?.data?.detail || 'Failed to create student')
  })

  const deleteMutation = useMutation({
    mutationFn: deleteStudent,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['students'] })
      setConfirmDelete(null)
      setDeleteError('')
    },
    onError: (e: any) => setDeleteError(e.response?.data?.detail || 'Failed to delete. Please try again.')
  })

  function handleSubmit() {
    if (!form.first_name.trim()) return setError('First name is required.')
    if (!form.last_name.trim()) return setError('Last name is required.')
    setError('')
    createMutation.mutate()
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold">Students</h2>
          <p className="text-slate-500 text-sm mt-1">Manage registered students</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-500 text-white border-none px-5 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
        >
          + Add Student
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl p-6 shadow-sm mb-6">
          <h3 className="text-base font-semibold mb-4">New Student</h3>
          {error && (
            <div className="bg-red-50 text-red-600 px-3.5 py-2.5 rounded-lg mb-4 text-sm">{error}</div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[13px] font-medium text-gray-700 block mb-1.5">
                First Name <span className="text-red-500">*</span>
              </label>
              <input
                value={form.first_name}
                onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))}
                placeholder="e.g. Ali"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none"
              />
            </div>
            <div>
              <label className="text-[13px] font-medium text-gray-700 block mb-1.5">
                Last Name <span className="text-red-500">*</span>
              </label>
              <input
                value={form.last_name}
                onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))}
                placeholder="e.g. Khan"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none"
              />
            </div>
            {[
              { key: 'email',        label: 'Student Email' },
              { key: 'parent_name',  label: 'Parent Name'   },
              { key: 'parent_email', label: 'Parent Email'  },
              { key: 'parent_phone', label: 'Parent Phone'  },
            ].map(field => (
              <div key={field.key}>
                <label className="text-[13px] font-medium text-gray-700 block mb-1.5">
                  {field.label}
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
              onClick={handleSubmit}
              disabled={createMutation.isPending}
              className="bg-blue-500 text-white border-none px-6 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
            >
              {createMutation.isPending ? 'Saving...' : 'Save Student'}
            </button>
            <button
              onClick={() => { setShowForm(false); setError('') }}
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
                {['Name', 'Email', 'Parent', 'Parent Email', 'Parent Phone', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[13px] font-semibold text-gray-700">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400 text-sm">
                    No students yet. Add your first student above.
                  </td>
                </tr>
              ) : students.map((s: any) => (
                <tr key={s.id} className="border-b border-slate-50">
                  <td className="px-4 py-3.5 text-sm font-medium">{s.full_name}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{s.email || '—'}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{s.parent_name || '—'}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{s.parent_email || '—'}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-500">{s.parent_phone || '—'}</td>
                  <td className="px-4 py-3.5">
                    <button
                      onClick={() => { setConfirmDelete(s.id); setDeleteError('') }}
                      className="text-slate-400 hover:text-red-500 border-none bg-transparent cursor-pointer text-base leading-none"
                      title="Delete student"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[1000]">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
            <h3 className="text-base font-semibold mb-2">Delete Student</h3>
            <p className="text-sm text-slate-500 mb-4">
              Are you sure you want to delete{' '}
              <span className="font-medium text-gray-700">
                {students.find((s: any) => s.id === confirmDelete)?.full_name}
              </span>
              ? This action cannot be undone.
            </p>
            {deleteError && (
              <div className="bg-red-50 text-red-600 px-3 py-2 rounded-lg mb-4 text-sm">{deleteError}</div>
            )}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setConfirmDelete(null); setDeleteError('') }}
                className="px-4 py-2 text-sm bg-slate-100 text-gray-700 rounded-lg border-none cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(confirmDelete)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg border-none cursor-pointer"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
