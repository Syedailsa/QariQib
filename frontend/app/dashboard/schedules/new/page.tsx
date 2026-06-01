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
    session_type: 'group'
  })
  const [error, setError] = useState('')

  const calcDuration = (() => {
    if (!form.scheduled_start || !form.scheduled_end) return 0
    const mins = Math.round(
      (new Date(form.scheduled_end).getTime() - new Date(form.scheduled_start).getTime()) / 60000
    )
    return mins > 0 ? mins : 0
  })()

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
    if (new Date(form.scheduled_end) <= new Date(form.scheduled_start))
      return setError('End time must be after start time')
    if (calcDuration < 15)
      return setError('Class duration cannot be less than 15 minutes. Please set a later end time.')
    setError('')
    mutation.mutate({
      ...form,
      scheduled_start: new Date(form.scheduled_start).toISOString(),
      scheduled_end: new Date(form.scheduled_end).toISOString(),
      scheduled_duration_mins: calcDuration,
    })
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Schedule New Class</h2>
        <p className="text-slate-500 text-sm mt-1">
          Creates a Zoom meeting and registers all participants automatically
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-5 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column */}
        <div className="flex flex-col gap-5">

          {/* Teacher selection */}
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-[15px] font-semibold mb-4">
              Select Teacher <span className="text-red-500">*</span>
            </h3>
            <div className="flex flex-col gap-2">
              {teachers.length === 0 ? (
                <p className="text-slate-400 text-sm">No teachers found. Add teachers first.</p>
              ) : teachers.map((t: any) => (
                <label key={t.id} className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg cursor-pointer border ${
                  form.teacher_id === t.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'
                }`}>
                  <input
                    type="radio"
                    name="teacher"
                    value={t.id}
                    checked={form.teacher_id === t.id}
                    onChange={() => setForm(f => ({ ...f, teacher_id: t.id }))}
                  />
                  <div>
                    <div className="text-sm font-medium">{t.full_name}</div>
                    <div className="text-xs text-slate-500">{t.email}</div>
                    {!t.consent_given && (
                      <div className="text-[11px] text-red-500 mt-0.5">⚠ Consent not given</div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Date & Time */}
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h3 className="text-[15px] font-semibold mb-4">
              Date & Time <span className="text-red-500">*</span>
            </h3>
            <div className="flex flex-col gap-3.5">
              <div>
                <label className="text-[13px] font-medium text-gray-700 block mb-1.5">Start Time</label>
                <input
                  type="datetime-local"
                  value={form.scheduled_start}
                  onChange={e => setForm(f => ({ ...f, scheduled_start: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none"
                />
              </div>
              <div>
                <label className="text-[13px] font-medium text-gray-700 block mb-1.5">End Time</label>
                <input
                  type="datetime-local"
                  value={form.scheduled_end}
                  onChange={e => setForm(f => ({ ...f, scheduled_end: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none"
                />
              </div>
              <div>
                <label className="text-[13px] font-medium text-gray-700 block mb-1.5">Duration</label>
                <div className={`px-3 py-2 rounded-lg text-sm bg-slate-50 flex items-center justify-between border ${
                  calcDuration > 0 && calcDuration < 15
                    ? 'border-red-300 text-red-500'
                    : calcDuration === 0
                      ? 'border-slate-200 text-slate-400'
                      : 'border-slate-200 text-slate-900'
                }`}>
                  <span>
                    {calcDuration === 0 ? 'Set start and end time' : `${calcDuration} minutes`}
                  </span>
                  {calcDuration > 0 && calcDuration < 15 && (
                    <span className="text-xs text-red-500 font-medium">⚠ Minimum 15 mins</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right column — student selection */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <h3 className="text-[15px] font-semibold mb-1">
            Select Students <span className="text-red-500">*</span>
          </h3>
          <p className="text-[13px] text-slate-500 mb-4">{form.student_ids.length} selected</p>
          <div className="flex flex-col gap-2 max-h-[480px] overflow-y-auto">
            {students.length === 0 ? (
              <p className="text-slate-400 text-sm">No students found. Add students first.</p>
            ) : students.map((s: any) => (
              <label key={s.id} className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg cursor-pointer border ${
                form.student_ids.includes(s.id) ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'
              }`}>
                <input
                  type="checkbox"
                  checked={form.student_ids.includes(s.id)}
                  onChange={() => toggleStudent(s.id)}
                />
                <div>
                  <div className="text-sm font-medium">{s.full_name}</div>
                  <div className="text-xs text-slate-500">{s.email || 'No email'}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={handleSubmit}
          disabled={mutation.isPending}
          className="bg-blue-500 text-white border-none px-8 py-3 rounded-lg cursor-pointer text-[15px] font-semibold"
        >
          {mutation.isPending ? 'Creating Class...' : 'Create Class & Schedule Zoom'}
        </button>
        <button
          onClick={() => router.back()}
          className="bg-slate-100 text-gray-700 border-none px-6 py-3 rounded-lg cursor-pointer text-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
