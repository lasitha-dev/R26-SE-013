import { cacheFarmLocation } from '../features/HealthAnomaly/utils/wellnessData.js'
import React, { createContext, useState, useEffect } from 'react'

export const ProfileContext = createContext(null)

export function ProfileProvider({ children }) {
  const [profilePhoto, setProfilePhoto] = useState('')
  const [farmerName, setFarmerName] = useState('')
  const [hasAlerts, setHasAlerts] = useState(false)

  const checkAlertsStatus = async () => {
    try {
      const token = localStorage.getItem('token')
      if (!token) return
      const response = await fetch('http://127.0.0.1:8000/api/cattle', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      if (response.ok) {
        const data = await response.json()
        const alertStates = ['Alert', 'Heat Stress', 'Unhealthy', 'At Risk']
        const alertExists = Array.isArray(data) && data.some(c => alertStates.includes(c.health_status) || alertStates.includes(c.status))
        setHasAlerts(alertExists)
      }
    } catch (err) {
      console.error('Error loading initial alerts status:', err)
    }
  }

  useEffect(() => {
    // Clear out any stale localStorage photo chunks
    localStorage.removeItem('user_profile_photo')

    let intervalId
    const checkTokenAndFetch = async () => {
      const token = localStorage.getItem('token')
      if (token && !farmerName) {
        try {
          const response = await fetch('http://127.0.0.1:8000/api/user/profile', {
            headers: {
              Authorization: `Bearer ${token}`
            }
          })
          if (response.ok) {
            const data = await response.json()
            if (data.profile_photo) {
              setProfilePhoto(data.profile_photo)
            }
            if (data.owner_name) {
              setFarmerName(data.owner_name)
            }
            cacheFarmLocation(data)
            checkAlertsStatus()
          }
        } catch (err) {
          console.error('Error loading initial farmer details:', err)
        }
      }
    }

    checkTokenAndFetch()
    intervalId = setInterval(checkTokenAndFetch, 800)

    return () => clearInterval(intervalId)
  }, [farmerName])

  return (
    <ProfileContext.Provider value={{ profilePhoto, setProfilePhoto, farmerName, setFarmerName, hasAlerts, checkAlertsStatus }}>
      {children}
    </ProfileContext.Provider>
  )
}

