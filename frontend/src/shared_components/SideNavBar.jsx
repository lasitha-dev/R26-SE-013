import React from 'react';
import PropTypes from 'prop-types';

/**
 * Navigation items configuration for the ADRS sidebar.
 * Each item maps to a feature module route.
 */
const NAV_ITEMS = [
  { id: 'wellness', icon: 'health_and_safety', label: 'Wellness & BCS', href: '#wellness' },
  { id: 'smart-diagnosis', icon: 'psychology', label: 'AI Smart Diagnosis', href: '#smart-diagnosis' },
  { id: 'geospatial', icon: 'travel_explore', label: 'Geospatial Intelligence', href: '#geospatial' },
  { id: 'forecasting', icon: 'wb_sunny', label: 'Seasonal Forecasting', href: '#forecasting' },
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
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
          aria-hidden="true"
          data-testid="sidebar-backdrop"
        />
      )}

      <aside
        className={`
          fixed lg:sticky top-0 left-0 h-screen w-64 bg-surface-container-low
          flex flex-col py-6 z-50 transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        id="side-nav-bar"
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="px-6 mb-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg primary-gradient flex items-center justify-center shrink-0">
              <span
                className="material-symbols-outlined text-on-primary"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                security
              </span>
            </div>
            <div>
              <h1 className="text-primary font-black text-lg leading-none">ADRS Core</h1>
              <p className="text-tertiary opacity-70 text-[0.6875rem] font-medium tracking-wider mt-1">
                Precision Sentinel
              </p>
            </div>
          </div>
        </div>

        {/* Primary Navigation */}
        <nav className="flex-1 space-y-1 px-3">
          {NAV_ITEMS.map((item) => {
            const isActive = item.id === activeItem;
            return (
              <a
                key={item.id}
                href={item.href}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg
                  transition-all duration-200 ease-in-out
                  font-medium tracking-wider text-[0.6875rem]
                  ${isActive
                    ? 'text-primary border-r-2 border-primary bg-surface-container'
                    : 'text-tertiary opacity-70 hover:bg-surface-container-high hover:text-primary'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
                data-testid={`nav-item-${item.id}`}
              >
                <span
                  className="material-symbols-outlined"
                  style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}
                >
                  {item.icon}
                </span>
                {item.label}
              </a>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="px-4 mt-auto space-y-4">
          <button
            className="w-full primary-gradient text-on-primary py-3 rounded-lg font-bold flex items-center justify-center gap-2 text-sm shadow-lg shadow-primary/10 hover:scale-[1.02] transition-transform"
            id="new-case-report-btn"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New Case Report
          </button>

          <div className="pt-6 border-t border-outline-variant/20 space-y-1">
            {FOOTER_ITEMS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="flex items-center gap-3 px-4 py-3 rounded-lg text-tertiary opacity-70 hover:bg-surface-container-high hover:text-primary transition-all duration-200 font-medium text-[0.6875rem]"
                data-testid={`nav-footer-${item.label.toLowerCase()}`}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                {item.label}
              </a>
            ))}
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
