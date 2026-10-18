import React from 'react'
import { Link } from 'react-router-dom'

/** Evidence-based, non-prescriptive follow-up prompts (`buildFollowUpItems`).
 * Read-only: nothing here changes a farm or case record. */
export default function MyAreaFollowUp({ items = [] }) {
  if (items.length === 0) return null
  return (
    <section className="rounded-xl border border-primary/25 bg-primary/[0.06] p-4 shadow-card-subtle" aria-labelledby="follow-up-title">
      <div id="follow-up-title" className="text-sm font-semibold text-on-surface">Suggested follow-up</div>
      <div className="mt-0.5 text-[10.5px] text-on-surface-variant/60">Prompts based on the records above. Decision support only; your clinical judgement and official procedures apply.</div>
      <ul className="mt-3 flex flex-col gap-2" role="list">
        {items.map((item) => (
          <li key={item.id} className="flex items-start gap-2 text-[11.5px] leading-relaxed text-on-surface">
            <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span>
              {item.text}
              {item.link && (
                <>
                  {' '}
                  <Link to={item.link} className="font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">Open</Link>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
