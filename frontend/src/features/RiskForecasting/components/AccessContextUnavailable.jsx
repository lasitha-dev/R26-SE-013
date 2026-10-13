import React from 'react';

/**
 * AccessContextUnavailable Component
 * Displayed when trusted ViewerContext is missing or invalid.
 * Fails closed safely without exposing fallback triggers or role selectors.
 * Refined visual alert card utilizing error tokens and clear typographic contrast.
 *
 * @param {object} props
 * @param {string} [props.title='Access context unavailable']
 * @param {string} [props.message='Your forecasting access scope could not be verified. Please sign in again or contact the system administrator.']
 * @param {string|null} [props.reason=null]
 */
export function AccessContextUnavailable({
  title = 'Access context unavailable',
  message = 'Your forecasting access scope could not be verified. Please sign in again or contact the system administrator.',
  reason = null,
  headingLevel,
}) {
  const allowedTags = ['h1', 'h2', 'h3'];

  let resolvedHeading = 'h1';
  if (typeof headingLevel === 'string' && allowedTags.includes(headingLevel.toLowerCase())) {
    resolvedHeading = headingLevel.toLowerCase();
  } else if (headingLevel === undefined && reason !== null && reason !== undefined && String(reason).trim() !== '') {
    resolvedHeading = 'h3';
  }

  const HeadingTag = resolvedHeading;

  return (
    <div
      role="alert"
      aria-live="polite"
      className="max-w-2xl mx-4 sm:mx-auto my-8 p-6 rounded-2xl bg-surface-container border border-error/30 shadow-xl text-on-surface"
    >
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-xl bg-error-container/20 text-error border border-error/30 shrink-0">
          <span className="material-symbols-outlined text-2xl" aria-hidden="true">
            gpp_maybe
          </span>
        </div>
        <div className="space-y-2">
          <HeadingTag className="text-lg font-semibold text-error tracking-wide">{title}</HeadingTag>
          <p className="text-sm text-on-surface-variant leading-relaxed">{message}</p>
          {reason && typeof reason === 'string' && reason.trim() !== '' && (
            <p className="text-xs font-mono text-on-surface-variant bg-surface-container-lowest/80 p-2.5 rounded-lg border border-outline-variant/30">
              Reason: {reason.trim()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
