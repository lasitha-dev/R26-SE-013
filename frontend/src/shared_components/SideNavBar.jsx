import React from 'react';
import PropTypes from 'prop-types';

/**
 * Navigation items configuration for the ADRS sidebar.
 * Each item maps to a feature module route.
 */
const NAV_ITEMS = [
  { id: 'wellness', icon: 'health_and_safety', label: 'Wellness & BCS', href: '/health/dashboard' },
  { id: 'smart-diagnosis', icon: 'psychology', label: 'AI Smart Diagnosis', href: '/diagnostics' },
  { id: 'geospatial', icon: 'travel_explore', label: 'Geospatial Intelligence', href: '/health/geospatial' },
  { id: 'forecasting', icon: 'wb_sunny', label: 'Seasonal Forecasting', href: '/health/forecasting' },
];

const FOOTER_ITEMS = [
  { icon: 'settings', label: 'Settings', href: '#settings' },
  { icon: 'help', label: 'Support', href: '#support' },
];

/**
 * SideNavBar — shared application sidebar navigation.
 * Used across all ADRS feature modules. On mobile/tablet, it overlays
 * and can be toggled via the `isOpen` / `onToggle` props.
 *
 * @param {string}   activeItem - The `id` of the currently active nav item.
 * @param {boolean}  isOpen     - Whether the sidebar is visible on mobile.
 * @param {function} onToggle   - Callback to toggle sidebar visibility.
 */
const SideNavBar = ({ activeItem = 'smart-diagnosis', isOpen = false, onToggle }) => {
  return (
    <>
      {/* Mobile overlay backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={onToggle}
          aria-hidden="true"
          data-testid="sidebar-backdrop"
        />
      )}

      <aside
        className={`
          fixed lg:sticky top-0 left-0 h-screen w-64 shrink-0 bg-surface-container-low border-r border-outline-variant/10
          flex flex-col py-6 z-40 transition-transform duration-300 ease-in-out select-none overflow-y-auto overflow-x-hidden
          ${isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'}
        `}
        id="side-nav-bar"
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Logo & Clinical Brand Header */}
        <div className="px-6 mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl primary-gradient flex items-center justify-center shrink-0 shadow-glow-sm">
              <span
                className="material-symbols-outlined text-on-primary text-2xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                security
              </span>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-primary font-black text-lg tracking-tight leading-none">ADRS Core</h1>
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              </div>
              <p className="text-tertiary text-2xs font-medium tracking-wider uppercase mt-1">
                Precision Sentinel
              </p>
            </div>
          </div>
        </div>

        {/* Navigation Category Label */}
        <div className="px-6 mb-2">
          <span className="text-3xs uppercase font-bold tracking-widest text-outline">
            Clinical Modules
          </span>
        </div>

        {/* Primary Navigation */}
        <nav className="flex-1 space-y-1.5 px-3">
          {NAV_ITEMS.map((item) => {
            const isActive = item.id === activeItem;
            return (
              <a
                key={item.id}
                href={item.href}
                className={`
                  group flex items-center gap-3 px-3.5 py-2.5 rounded-lg
                  transition-all duration-200 ease-in-out
                  font-medium tracking-wide text-xs
                  ${isActive
                    ? 'text-primary font-bold bg-primary/10 border-l-4 border-primary'
                    : 'text-tertiary hover:text-on-surface hover:bg-surface-container-high/60 border-l-4 border-transparent'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
                data-testid={`nav-item-${item.id}`}
              >
                <span
                  className={`material-symbols-outlined text-xl transition-transform duration-200 ${isActive ? 'text-primary' : 'text-tertiary group-hover:text-primary group-hover:scale-110'}`}
                  style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}
                >
                  {item.icon}
                </span>
                <span className="truncate">{item.label}</span>
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-glow-sm" />
                )}
              </a>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="px-4 mt-auto space-y-4">
          <button
            className="w-full primary-gradient text-on-primary py-3 rounded-lg font-bold flex items-center justify-center gap-2 text-xs uppercase tracking-wider shadow-lg shadow-primary/15 hover:shadow-primary/25 hover:brightness-105 active:scale-[0.98] transition-all"
            id="new-case-report-btn"
          >
            <span className="material-symbols-outlined text-lg font-bold">add</span>
            New Case Report
          </button>

          <div className="pt-4 border-t border-outline-variant/15 space-y-1">
            {FOOTER_ITEMS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-tertiary hover:text-on-surface hover:bg-surface-container-high/60 transition-all duration-200 font-medium text-xs"
                data-testid={`nav-footer-${item.label.toLowerCase()}`}
              >
                <span className="material-symbols-outlined text-lg">{item.icon}</span>
                <span>{item.label}</span>
              </a>
            ))}
          </div>

          {/* System Diagnostic Status Indicator */}
          <div className="pt-2 px-1 flex items-center justify-between text-3xs text-outline font-mono">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
              SYSTEM ACTIVE
            </span>
            <span>v2.4.0</span>
          </div>
        </div>
      </aside>
    </>
  );
};

SideNavBar.propTypes = {
  activeItem: PropTypes.string,
  isOpen: PropTypes.bool,
  onToggle: PropTypes.func,
};

export default SideNavBar;
