import React from 'react'

import { ACTION_BASIS_KIND } from '../adapters/areaExplainer'

const BASIS_COLOUR = {
  [ACTION_BASIS_KIND.REPORTS]: '#f87171',
  [ACTION_BASIS_KIND.MODEL]: '#a78bfa',
  [ACTION_BASIS_KIND.GUIDANCE]: '#38bdf8',
  [ACTION_BASIS_KIND.DATA]: '#94a3b8',
}

/** AI Explainer card (prototype v4 look): summary text, suggested actions
 * A-E (collapsed, with their basis), limitations. Content from
 * adapters/areaExplainer.js only. */
export default function MyAreaAiExplainer({ explainer }) {
  if (!explainer) return null
  return (
    <section className="flex flex-col rounded-xl border border-violet-400/35 bg-gradient-to-b from-violet-600/10 to-surface-container/60 p-3.5 shadow-card-subtle" aria-labelledby="ai-explainer-title">
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-violet-400/20 text-[12px] text-violet-200" aria-hidden="true">✦</span>
        <span id="ai-explainer-title" className="text-[14px] font-bold text-on-surface">AI Explainer</span>
        <span className="ml-auto rounded border border-violet-300/50 px-1.5 py-0.5 font-mono text-[9px] font-bold tracking-widest text-violet-200">ADVISORY</span>
      </div>

      {explainer.actions.length > 0 && (
        <>
          <div className="mt-2.5 text-[10.5px] font-bold uppercase tracking-wider text-on-surface-variant/70">Suggested actions</div>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {explainer.actions.map((group) => (
              <details key={group.id} className="group overflow-hidden rounded-lg border border-outline-variant/25 bg-surface-container-lowest/55" data-action-group={group.id}>
                <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3 py-2 text-[12.5px] font-bold text-on-surface">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/15 font-mono text-[10.5px] font-extrabold text-primary">{group.id}</span>
                  <span className="min-w-0 flex-1">{group.title}</span>
                  <span className="font-mono text-[10px] text-on-surface-variant/55">{group.items.length}</span>
                  <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-on-surface-variant/60 transition-transform group-open:rotate-180">expand_more</span>
                </summary>
                <ul className="flex flex-col gap-2 border-t border-outline-variant/20 px-3 py-2">
                  {group.items.map((item) => (
                    <li key={item.title}>
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[12px] font-semibold text-on-surface">{item.title}</span>
                        <span className="shrink-0 rounded border px-1 py-0.5 text-[8.5px] font-semibold uppercase tracking-wide" style={{ color: BASIS_COLOUR[item.basis], borderColor: `${BASIS_COLOUR[item.basis]}66` }}>{item.basis}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] leading-snug text-on-surface-variant/80">{item.why}</p>
                      {item.farms?.length > 0 && <p className="mt-0.5 text-[10.5px] text-on-surface-variant/55">Farms: {item.farms.join(', ')}</p>}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </>
      )}

    </section>
  )
}
