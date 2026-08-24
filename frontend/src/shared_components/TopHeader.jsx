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
      className="w-full sticky top-0 z-30 bg-surface-container-low/80 backdrop-blur-xl border-b border-outline-variant/10 flex justify-between items-center px-4 md:px-8 h-16 transition-colors"
      id="top-header"
      role="banner"
    >
      <div className="flex items-center gap-3 md:gap-4">
        {/* Hamburger menu — visible on mobile/tablet only */}
        <button
          className="lg:hidden p-2 text-tertiary hover:text-on-surface hover:bg-surface-container-high rounded-lg transition-colors"
          onClick={onMenuToggle}
          aria-label="Toggle navigation menu"
          id="hamburger-menu-btn"
        >
          <span className="material-symbols-outlined text-xl">menu</span>
        </button>

        {/* Title & Clinical Node Badge */}
        <div className="flex items-center gap-2.5">
          <span className="text-primary font-headline uppercase font-bold text-xs md:text-sm tracking-wider flex items-center gap-1.5">
            <span className="material-symbols-outlined text-base">monitor_heart</span>
            {title}
          </span>
          <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-3xs font-mono font-medium">
            <span className="w-1 h-1 rounded-full bg-primary animate-ping" />
            LIVE NODE
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2.5 md:gap-4">
        {/* Clinical Search Input */}
        <div className="hidden sm:flex relative items-center bg-surface-container-lowest/80 rounded-lg px-3 py-1.5 border border-outline-variant/20 focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/20 transition-all">
          <span className="material-symbols-outlined text-outline text-base mr-2">search</span>
          <input
            className="bg-transparent border-none focus:ring-0 text-xs text-on-surface placeholder:text-outline/60 w-36 md:w-56 focus:w-64 transition-all duration-300 outline-none font-sans"
            placeholder="Search case ID or tag..."
            type="text"
            id="header-search-input"
          />
          <kbd className="hidden md:inline-block text-3xs font-mono text-outline/60 bg-surface-container px-1.5 py-0.5 rounded border border-outline-variant/30">
            /
          </kbd>
        </div>

        {/* Action icons & Clinical profile avatar */}
        <div className="flex items-center gap-1.5 md:gap-2">
          {/* Notifications button with indicator badge */}
          <button
            className="relative p-2 text-tertiary hover:text-on-surface hover:bg-surface-container-high rounded-lg transition-colors"
            aria-label="Notifications"
            id="notifications-btn"
          >
            <span className="material-symbols-outlined text-xl">notifications</span>
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-error border-2 border-surface-container-low" />
          </button>

          {/* Quick Help / Info */}
          <div className="h-4 w-px bg-outline-variant/20 mx-1 hidden sm:block" />

          {/* Account profile button */}
          <button
            className="flex items-center gap-2 p-1.5 pl-2 text-tertiary hover:text-on-surface hover:bg-surface-container-high rounded-lg transition-colors group"
            aria-label="Account"
            id="account-btn"
          >
            <div className="w-7 h-7 rounded-lg bg-surface-container-highest flex items-center justify-center border border-primary/30 text-primary font-bold text-xs group-hover:border-primary transition-colors">
              <span className="material-symbols-outlined text-lg">clinical_notes</span>
            </div>
            <div className="hidden lg:flex flex-col items-start text-left">
              <span className="text-2xs font-semibold text-on-surface leading-tight">Dr. Vet Sentinel</span>
              <span className="text-3xs text-outline leading-tight">Lead Pathologist</span>
            </div>
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
