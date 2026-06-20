// frontend/lib/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' }
})

// ─── Teachers ────────────────────────────────────────────────
export const getTeachers = () =>
  api.get('/api/v1/teachers').then(r => r.data)

export const createTeacher = (data: {
  full_name: string
  email: string
  phone?: string
  zoom_user_id?: string
}) => api.post('/api/v1/teachers', data).then(r => r.data)

export const updateConsent = (teacher_id: string, consent_given: boolean) =>
  api.patch(`/api/v1/teachers/${teacher_id}/consent`, null, {
    params: { consent_given }
  }).then(r => r.data)

export const deleteTeacher = (teacher_id: string) =>
  api.delete(`/api/v1/teachers/${teacher_id}`).then(r => r.data)

// ─── Students ────────────────────────────────────────────────
export const getStudents = () =>
  api.get('/api/v1/students').then(r => r.data)

export const createStudent = (data: {
  full_name: string
  email?: string
  parent_name?: string
  parent_email?: string
  parent_phone?: string
}) => api.post('/api/v1/students', data).then(r => r.data)

export const deleteStudent = (student_id: string) =>
  api.delete(`/api/v1/students/${student_id}`).then(r => r.data)

// ─── Schedules ───────────────────────────────────────────────
export const getSchedules = () =>
  api.get('/api/v1/schedules').then(r => r.data)

export const getTodaySchedules = () =>
  api.get('/api/v1/schedules/today').then(r => r.data)

export const getSchedule = (id: string) =>
  api.get(`/api/v1/schedules/${id}`).then(r => r.data)

export const createSchedule = (data: {
  teacher_id: string
  student_ids: string[]
  scheduled_start: string
  scheduled_end: string
  scheduled_duration_mins: number
  session_type?: string
}) => api.post('/api/v1/schedules', data).then(r => r.data)

// ─── Alerts ──────────────────────────────────────────────────
export const getAlerts = (resolved = false) =>
  api.get('/api/v1/alerts', { params: { resolved } }).then(r => r.data)

export const resolveAlert = (alert_id: string) =>
  api.post(`/api/v1/alerts/${alert_id}/resolve`).then(r => r.data)

export const updateSchedule = (id: string, data: {
  scheduled_start?: string
  scheduled_end?: string
  scheduled_duration_mins?: number
}) => api.patch(`/api/v1/schedules/${id}`, data).then(r => r.data)

export const deleteSchedule = (id: string) =>
  api.delete(`/api/v1/schedules/${id}`).then(r => r.data)