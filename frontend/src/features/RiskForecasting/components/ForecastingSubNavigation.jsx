import React from 'react';

/**
 * Reusable role-aware sub-navigation bar for Risk Forecasting.
 * Implements the Stitch horizontal pill-navigation pattern.
 * Uses verified surface and border design tokens with accessible touch targets,
 * visual active state distinctions, and keyboard focus treatment.
 *
 * @param {object} props
 * @param {Array<{ id: string, label: string, icon: string }>} props.items
 * @param {string} props.activeItem
 * @param {Function} props.onSelect
 * @param {string} [props.ariaLabel='Risk Forecasting sub-navigation']
 */
export function ForecastingSubNavigation({
  items = [],
  activeItem = '',
  onSelect = () => {},
  ariaLabel = 'Risk Forecasting sub-navigation',
}) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  return (
    <nav
      aria-label={ariaLabel}
      className="w-full bg-surface-container-low/90 backdrop-blur-md border-b border-outline-variant/30 px-4 sm:px-6 py-2.5"
    >
      <div className="relative flex items-center gap-2 overflow-x-auto scrollbar-none scroll-smooth motion-reduce:scroll-auto py-0.5">
        {items.map((item) => {
          const isActive = item.id === activeItem;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                isActive
                  ? 'bg-primary-container/20 text-primary border border-primary-container/40 shadow-sm font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
            >
              {item.icon && (
                <span className="material-symbols-outlined text-lg" aria-hidden="true">
                  {item.icon}
                </span>
              )}
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
