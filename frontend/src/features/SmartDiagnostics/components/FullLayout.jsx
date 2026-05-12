import React from 'react'

export default function FullLayout({ children }) {
  return (
    <div>
      <div className="background-decor decor-1" />
      <div className="background-decor decor-2" />
      <div className="container">
        <header>
          <h1 style={{ color: 'var(--text-main)', fontSize: '2.5rem', fontWeight: 700 }}>Animal Farm Reporting</h1>
          <div className="logo">
            <i data-lucide="leaf" className="logo-icon" />
            <h1>BoviCare AI</h1>
          </div>
          <p className="subtitle">Automated Cattle Detection & Disease Diagnosis</p>
        </header>

        <main>{children}</main>

        <footer>
          <p>BoviCare AI — Two-Tier Cattle Disease Detection System | Research Prototype</p>
        </footer>
      </div>
    </div>
  )
}
