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

  if (isLoading) return <p className="text-slate-400">Loading...</p>
  if (!schedule) return <p className="text-red-500">Schedule not found</p>

  if (schedule.status !== 'scheduled') {
    return (
      <div className="bg-red-50 rounded-xl p-6">
        <p className="text-red-600 text-[15px]">
          Cannot edit a class with status: <strong>{schedule.status}</strong>
        </p>
        <button
          onClick={() => router.back()}
          className="mt-4 px-5 py-2 rounded-lg border border-slate-200 cursor-pointer bg-white"
        >
          Go Back
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Edit Class</h2>
        <p className="text-slate-500 text-sm mt-1">Teacher: {schedule.teachers?.full_name}</p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-5 text-sm">{error}</div>
      )}

      <div className="bg-white rounded-xl p-7 shadow-sm max-w-[480px]">
        <div className="flex flex-col gap-[18px]">
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

        <div className="flex gap-3 mt-6">
          <button
            onClick={() => {
              if (calcDuration < 15) return setError('Class duration cannot be less than 15 minutes. Please set a later end time.')
              mutation.mutate(form)
            }}
            disabled={mutation.isPending}
            className="bg-blue-500 text-white border-none px-7 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
          >
            {mutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={() => router.back()}
            className="bg-slate-100 text-gray-700 border-none px-6 py-2.5 rounded-lg cursor-pointer text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
