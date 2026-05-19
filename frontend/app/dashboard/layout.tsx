// app/dashboard/layout.tsx
import Link from 'next/link'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: '220px',
        background: '#1e293b',
        color: '#f1f5f9',
        padding: '24px 0',
        flexShrink: 0,
        position: 'fixed',
        height: '100vh',
        overflowY: 'auto'
      }}>
        <div style={{ padding: '0 20px 24px', borderBottom: '1px solid #334155' }}>
          <h1 style={{ fontSize: '18px', fontWeight: '700', color: '#38bdf8' }}>
            QaraQib
          </h1>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
            Admin Dashboard
          </p>
        </div>

        <nav style={{ padding: '16px 0' }}>
          {[
            { href: '/dashboard', label: '📊 Overview' },
            { href: '/dashboard/schedules', label: '📅 Schedules' },
            { href: '/dashboard/schedules/new', label: '➕ New Class' },
            { href: '/dashboard/teachers', label: '👨‍🏫 Teachers' },
            { href: '/dashboard/students', label: '👩‍🎓 Students' },
            { href: '/dashboard/alerts', label: '🔔 Alerts' },
          ].map(item => (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: 'block',
                padding: '10px 20px',
                color: '#cbd5e1',
                textDecoration: 'none',
                fontSize: '14px',
                transition: 'background 0.15s'
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main style={{
        marginLeft: '220px',
        flex: 1,
        padding: '32px',
        minHeight: '100vh'
      }}>
        {children}
      </main>
    </div>
  )
}