// CSV dates use month-first notation when the year is last, as in the sample.
export function normalizeLogDate(raw) {
  const parts = String(raw ?? '').trim().match(/^(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})$/)
  if (!parts) return ''
  const [, first, second, third] = parts
  let year, month, day
  if (first.length === 4) {
    [year, month, day] = [Number(first), Number(second), Number(third)]
  } else if (third.length === 2 || third.length === 4) {
    [month, day, year] = [Number(first), Number(second), Number(third)]
    if (third.length === 2) year += 2000
  } else return ''
  const date = new Date(0)
  date.setUTCFullYear(year, month - 1, day)
  if (year < 1 || year > 9999 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return ''
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function cacheFarmLocation(profile) {
  // Clear missing values too: a new account must not inherit the previous farm.
  const values = {
    registered_farm_lat: profile.latitude,
    registered_farm_lon: profile.longitude,
    registered_farm_district: profile.location_district || profile.district,
    registered_farm_name: profile.location_district || profile.district,
    registered_farm_location: profile.location,
  }
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === '') localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  }
}
