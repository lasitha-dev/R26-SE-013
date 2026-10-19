import React from 'react';
import PropTypes from 'prop-types';
import { describeTierBasis } from './forecastPresentation';

/** One short line saying why a record is MEDIUM/HIGH and how strong the evidence is (v2 records only). */
export function TierBasisNote({ record, className = 'text-xs text-on-surface-variant' }) {
  const basis = describeTierBasis(record);
  if (!basis) return null;
  return (
    <p className={className} data-testid="tier-basis">
      {basis.text}
      {basis.evidence && <span className="block">{basis.evidence}</span>}
    </p>
  );
}

TierBasisNote.propTypes = {
  record: PropTypes.object,
  className: PropTypes.string,
};
