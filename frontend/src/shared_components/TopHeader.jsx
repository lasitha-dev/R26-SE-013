import React from 'react';
import PropTypes from 'prop-types';

/**
 * TopHeader — shared top header bar with page title, search, and action buttons.
 * Used across all ADRS feature modules.
 *
 * @param {string}   title       - The page/panel title displayed in the header.
 * @param {function} onMenuToggle - Callback for the hamburger menu (mobile only).
 */
const TopHeader = ({ title = 'AI Diagnostics Panel', onMenuToggle }) => {
  return (
    <header
      className="w-full sticky top-0 z-30 bg-surface-container-low flex justify-between items-center px-4 md:px-8 h-16"
      id="top-header"
      role="banner"
    >
      <div className="flex items-center gap-4">
        {/* Hamburger menu — visible on mobile/tablet only */}
        <button
          className="lg:hidden p-2 text-tertiary hover:bg-surface-container-high rounded-lg transition-colors"
          onClick={onMenuToggle}
          aria-label="Toggle navigation menu"
          id="hamburger-menu-btn"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>

        <span className="text-primary font-headline uppercase font-bold text-sm md:text-lg tracking-wider">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-3 md:gap-6">
        {/* Search input — hidden on very small screens */}
        <div className="hidden sm:flex relative items-center bg-background rounded-full px-4 py-1.5 border border-outline-variant/10">
          <span className="material-symbols-outlined text-on-surface-variant text-sm mr-2">search</span>
          <input
            className="bg-transparent border-none focus:ring-0 text-sm text-on-surface placeholder:text-on-surface-variant/50 w-32 md:w-48 outline-none"
            placeholder="Search case ID..."
            type="text"
            id="header-search-input"
          />
        </div>

        <div className="flex items-center gap-1 md:gap-3">
          <button
            className="p-2 text-tertiary opacity-80 hover:bg-surface-container-high rounded-full transition-colors"
            aria-label="Notifications"
            id="notifications-btn"
          >
            <span className="material-symbols-outlined">notifications</span>
          </button>
          <button
            className="p-2 text-tertiary opacity-80 hover:bg-surface-container-high rounded-full transition-colors"
            aria-label="Account"
            id="account-btn"
          >
            <span className="material-symbols-outlined">account_circle</span>
          </button>
        </div>
      </div>
    </header>
  );
};

TopHeader.propTypes = {
  title: PropTypes.string,
  onMenuToggle: PropTypes.func,
};

export default TopHeader;
