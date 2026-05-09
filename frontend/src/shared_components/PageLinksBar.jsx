import React from 'react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/health/dashboard', label: 'Dashboard' },
  { to: '/health/login', label: 'Login' },
  { to: '/health/registration', label: 'Registration' },
  { to: '/health/registration-success', label: 'Reg Success' },
  { to: '/health/password-reset', label: 'Password Reset' },
  { to: '/health/settings', label: 'Settings' },
  { to: '/health/herd-registry', label: 'Herd Registry' },
  { to: '/health/animal-profile-bt-8842', label: 'Animal Profile' },
  { to: '/health/add-new-animal', label: 'Add Animal' },
  { to: '/health/wellness-data-intake', label: 'Data Intake' },
  { to: '/health/7-day-triage-scan', label: '7-Day Triage' },
  { to: '/health/ai-wellness-report', label: 'AI Report' },
  { to: '/health/notifications', label: 'Notifications' },
]

export default function PageLinksBar() {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-[100] border-t border-outline-variant/20 bg-surface/80 backdrop-blur-md">
      <div className="mx-auto max-w-screen-2xl px-3 py-2">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <span className="text-[10px] font-black tracking-[0.2em] uppercase text-slate-500 whitespace-nowrap pr-2">
            Pages
          </span>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                [
                  'whitespace-nowrap rounded-full border px-3 py-1 text-[11px] font-bold tracking-wide transition-colors',
                  isActive
                    ? 'bg-primary/15 text-primary border-primary/30'
                    : 'bg-surface-container text-slate-300 border-outline-variant/20 hover:text-primary-fixed hover:border-primary/30',
                ].join(' ')
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  )
}
