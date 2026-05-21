export function formatTime(utcString: string | null | undefined) {
  if (!utcString) return '—'
  return new Date(utcString).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDateTime(utcString: string | null | undefined) {
  if (!utcString) return '—'
  return new Date(utcString).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDateHeader(utcString: string | null | undefined) {
  if (!utcString) return '—'
  return new Date(utcString).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}