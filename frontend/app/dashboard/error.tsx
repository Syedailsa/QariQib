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
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="bg-red-50 border border-red-300 rounded-xl px-10 py-9 max-w-[480px] text-center">
        <div className="text-[32px] mb-3">⚠️</div>
        <h2 className="text-red-600 text-lg font-bold mb-2">Something went wrong</h2>
        <p className="text-slate-500 text-sm mb-5">
          {error.message || 'An unexpected error occurred. Your live classes are unaffected.'}
        </p>
        <button
          onClick={reset}
          className="bg-blue-500 text-white border-none px-7 py-2.5 rounded-lg cursor-pointer text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    </div>
  )
}
