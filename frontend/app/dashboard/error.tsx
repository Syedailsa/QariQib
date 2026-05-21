'use client'
import { useEffect } from 'react'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[Dashboard Error]', error)
  }, [error])

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '60vh'
    }}>
      <div style={{
        background: '#fef2f2', border: '1px solid #fca5a5',
        borderRadius: '12px', padding: '36px 40px', maxWidth: '480px',
        textAlign: 'center'
      }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
        <h2 style={{ color: '#dc2626', fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>
          Something went wrong
        </h2>
        <p style={{ color: '#64748b', fontSize: '14px', marginBottom: '20px' }}>
          {error.message || 'An unexpected error occurred. Your live classes are unaffected.'}
        </p>
        <button
          onClick={reset}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '10px 28px', borderRadius: '8px', cursor: 'pointer',
            fontSize: '14px', fontWeight: '500'
          }}
        >
          Try Again
        </button>
      </div>
    </div>
  )
}
