import React, { createContext, useState, useEffect } from 'react'

export const ProfileContext = createContext(null)

export function ProfileProvider({ children }) {
  const [profilePhoto, setProfilePhoto] = useState('')
  const [farmerName, setFarmerName] = useState('')

  useEffect(() => {
    // Clear out any stale localStorage photo chunks
    localStorage.removeItem('user_profile_photo')

    const fetchInitialProfile = async () => {
      try {
        const token = localStorage.getItem('token')
        if (!token) return
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
        }
      } catch (err) {
        console.error('Error loading initial farmer details:', err)
      }
    }

    fetchInitialProfile()
  }, [])

  return (
    <ProfileContext.Provider value={{ profilePhoto, setProfilePhoto, farmerName, setFarmerName }}>
      {children}
    </ProfileContext.Provider>
  )
}
