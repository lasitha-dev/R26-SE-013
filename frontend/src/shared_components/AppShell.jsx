// TEMPORARY COPY from component/ai-smart-diagnosis — switch to shared import when merged to main
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import SideNavBar from './SideNavBar';
import TopHeader from './TopHeader';

/**
 * AppShell — shared page-level layout composing SideNavBar + TopHeader + content area.
 * Manages responsive sidebar state (open/close on mobile).
 *
 * @param {string}    activeNavItem - Passed to SideNavBar to highlight the current feature.
 * @param {string}    headerTitle   - Displayed in the TopHeader.
 * @param {ReactNode} children      - The main page content.
 */
const AppShell = ({ activeNavItem = 'forecasting', headerTitle = 'Seasonal Risk Forecasting', children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toggleSidebar = () => setSidebarOpen((prev) => !prev);

  return (
    <div className="flex min-h-screen bg-surface font-body text-on-surface selection:bg-primary selection:text-on-primary">
      <SideNavBar
        activeItem={activeNavItem}
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <TopHeader
          title={headerTitle}
          onMenuToggle={toggleSidebar}
        />

        <div className="p-4 md:p-8 max-w-7xl mx-auto w-full flex-1">
          {children}
        </div>
      </main>
    </div>
  );
};

AppShell.propTypes = {
  activeNavItem: PropTypes.string,
  headerTitle: PropTypes.string,
  children: PropTypes.node,
};

export default AppShell;
