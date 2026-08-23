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
        const alertExists = data.some(c => c.health_status === 'Alert' || c.status === 'Alert')
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

