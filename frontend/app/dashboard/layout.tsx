// app/dashboard/layout.tsx
import Link from 'next/link'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-[220px] bg-slate-800 text-slate-100 py-6 shrink-0 fixed h-screen overflow-y-auto">
        <div className="px-5 pb-6 border-b border-slate-700">
          <h1 className="text-lg font-bold text-sky-400">QaraQib</h1>
          <p className="text-xs text-slate-400 mt-1">Admin Dashboard</p>
        </div>

        <nav className="py-4">
          {[
            { href: '/dashboard',              label: '📊 Overview'   },
            { href: '/dashboard/schedules',    label: '📅 Schedules'  },
            { href: '/dashboard/schedules/new',label: '➕ New Class'   },
            { href: '/dashboard/teachers',     label: '👨‍🏫 Teachers'  },
            { href: '/dashboard/students',     label: '👩‍🎓 Students'  },
            { href: '/dashboard/alerts',       label: '🔔 Alerts'     },
          ].map(item => (
            <Link
              key={item.href}
              href={item.href}
              className="block px-5 py-2.5 text-slate-300 no-underline text-sm hover:bg-slate-700 transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="ml-[220px] flex-1 p-8 min-h-screen">
        {children}
      </main>
    </div>
  )
}
