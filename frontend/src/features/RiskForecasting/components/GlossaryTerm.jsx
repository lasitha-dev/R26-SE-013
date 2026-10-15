import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import PropTypes from 'prop-types';

const CARD_WIDTH = 320;
const GAP = 10;

/**
 * A word with a dotted underline that explains itself in a small card on hover, keyboard focus or tap.
 * The card is drawn above the page (portal, fixed position) so tables and scroll areas never clip it.
 */
export function GlossaryTerm({ term, children, align = 'center', className = '' }) {
  const triggerRef = useRef(null);
  const closeTimer = useRef(null);
  const id = useId();
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);
  const [position, setPosition] = useState({ left: 12, top: 0, above: false });

  const place = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const centre = align === 'left' ? rect.left : rect.left + rect.width / 2 - CARD_WIDTH / 2;
    const left = Math.max(12, Math.min(centre, viewportWidth - CARD_WIDTH - 12));
    const below = rect.bottom + GAP;
    const above = below + 300 > window.innerHeight && rect.top > 320;
    setPosition({ left, top: above ? rect.top - GAP : below, above });
  }, [align]);

  const show = useCallback(() => {
    clearTimeout(closeTimer.current);
    place();
    setOpen(true);
  }, [place]);

  const hide = useCallback(() => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => { setShown(false); setOpen(false); }, 80);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const frame = requestAnimationFrame(() => setShown(true));
    const onKey = (event) => { if (event.key === 'Escape') { setShown(false); setOpen(false); } };
    const onScroll = () => { setShown(false); setOpen(false); };
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  return (
    <>
      <span
        ref={triggerRef}
        tabIndex={0}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={() => (open ? hide() : show())}
        onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); if (open) hide(); else show(); } }}
        aria-describedby={open ? id : undefined}
        className={`cursor-help border-b border-dotted border-slate-500 pb-px font-[inherit] text-inherit transition-colors duration-150 hover:border-emerald-400 hover:text-emerald-300 focus:outline-none focus-visible:border-emerald-400 focus-visible:text-emerald-300 ${className}`}
      >
        {term}
      </span>
      {open && createPortal(
        <div
          id={id}
          role="tooltip"
          style={{ position: 'fixed', left: position.left, top: position.top, width: CARD_WIDTH, transform: position.above ? 'translateY(-100%)' : undefined }}
          className={`pointer-events-none z-[1000] rounded-2xl border border-emerald-500/20 bg-slate-900/95 p-4 text-left text-xs font-normal normal-case tracking-normal text-slate-200 shadow-2xl backdrop-blur-md transition duration-200 ${shown ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'}`}
        >
          {children}
        </div>,
        document.body,
      )}
    </>
  );
}

GlossaryTerm.propTypes = {
  term: PropTypes.node.isRequired,
  children: PropTypes.node.isRequired,
  align: PropTypes.oneOf(['center', 'left']),
  className: PropTypes.string,
};
