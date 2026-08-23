import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function VetAssignedFarms() {
  const [farms, setFarms] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Load active farms profile or sample assigned farm networks
    const fetchFarms = async () => {
      try {
        const token = localStorage.getItem("token")
        const response = await fetch("http://127.0.0.1:8000/api/user/profile", {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (response.ok) {
          const data = await response.json()
          setFarms([
            {
              id: 'farm-01',
              name: data.owner_name ? `${data.owner_name}'s Dairy Estate` : 'Highland Dairy Holdings',
              owner: data.owner_name || 'Dr. Julian Vane',
              location: data.location_district || 'Nuwara Eliya / Central District',
              registrationNumber: data.registration_number || 'REG-SL-9902',
              totalAnimals: 24,
              status: 'Active Synchronization'
            },
            {
              id: 'farm-02',
              name: 'Greenfield Pastures & Breeding Node',
              owner: 'Rohan Jayawardena',
              location: 'Kandy / Western Province',
              registrationNumber: 'REG-LK-7741',
              totalAnimals: 18,
              status: 'Active Synchronization'
            },
            {
              id: 'farm-03',
              name: 'Lanka Agro Farmstead',
              owner: 'Anura Bandara',
              location: 'Kurunegala / North Western',
              registrationNumber: 'REG-NW-3312',
              totalAnimals: 35,
              status: 'Pending Health Intake'
            }
          ])
        }
      } catch (err) {
        console.error("Error fetching farms:", err)
      } finally {
        setLoading(false)
      }
    }
    fetchFarms()
  }, [])

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold uppercase tracking-wider">
              Assigned Herd Networks
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400 text-xs font-mono">Veterinary Jurisdiction</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Assigned Farms &amp; Agricultural Estates
          </h1>
          <p className="text-slate-400 text-xs md:text-sm mt-1">
            Registered livestock farms linked to your veterinary license for diagnostic oversight and care protocols.
          </p>
        </div>

        <Link
          to="/vet/diagnostics"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-xs flex items-center gap-2 shadow-lg shadow-primary/20 hover:brightness-110 active:scale-95 transition-all uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-base">psychology</span>
          Diagnose Livestock
        </Link>
      </div>

      {/* Farms Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {farms.map((farm) => (
          <div
            key={farm.id}
            className="glass-card rounded-xl p-6 border border-white/5 hover:border-emerald-500/30 transition-all flex flex-col justify-between space-y-4 group"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <span className="material-symbols-outlined text-xl">agriculture</span>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {farm.registrationNumber}
                </span>
              </div>

              <h3 className="text-base font-bold text-white group-hover:text-emerald-400 transition-colors">
                {farm.name}
              </h3>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">person</span>
                Owner: <span className="text-slate-300 font-semibold">{farm.owner}</span>
              </p>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">location_on</span>
                {farm.location}
              </p>
            </div>

            <div className="pt-4 border-t border-white/5 flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-slate-400">
                <span className="material-symbols-outlined text-sm text-emerald-400">pets</span>
                <span className="font-bold text-white font-mono">{farm.totalAnimals}</span> Livestock
              </div>
              <Link
                to="/vet/diagnostics"
                className="text-primary hover:text-primary-fixed font-bold flex items-center gap-1"
              >
                <span>Diagnose</span>
                <span className="material-symbols-outlined text-xs">arrow_forward</span>
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
