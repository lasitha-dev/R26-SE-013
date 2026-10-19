import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

import { forecastUrl, heatIntensity, kmCircle, parseForecast } from '../adapters/weatherForecast'
import WeatherForecastStrip from '../components/WeatherForecastStrip'

const day = parseForecast({ daily: { time: ['2026-10-17'], weather_code: [61], precipitation_sum: [4.2], precipitation_probability_max: [70], wind_speed_10m_max: [15], wind_direction_10m_dominant: [270], temperature_2m_max: [31], temperature_2m_min: [24], relative_humidity_2m_mean: [82] } })

describe('Env weather: icon tiles and point forecast', () => {
  it('a point forecast requests exactly that one point', () => {
    const params = new URL(forecastUrl({ points: [[80.56, 6.34]] })).searchParams
    expect(params.get('latitude')).toBe('6.340')
    expect(params.get('longitude')).toBe('80.560')
  })

  it('kmCircle is a closed ring about the requested radius', () => {
    const ring = kmCircle([80.5, 6.0], 5).coordinates[0]
    expect(ring[0]).toEqual(ring.at(-1))
    const northKm = (Math.max(...ring.map((p) => p[1])) - 6.0) * 110.574
    expect(northKm).toBeCloseTo(5, 1)
  })

  it('shows every value as a tile, with the wind arrow pointing downwind', () => {
    render(<WeatherForecastStrip district="Matara" dates={['2026-10-17']} selectedDate="2026-10-17" days={day} status="ready" todayKey="2026-10-17" />)
    for (const label of ['Rain (24 h)', 'Rain chance', 'Temperature', 'Humidity', 'Wind']) expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('24–31 °C')).toBeInTheDocument()
    expect(screen.getByLabelText('toward E')).toBeInTheDocument() // wind from W blows toward E
    expect(screen.getByText(/District average · click the map/)).toBeInTheDocument()
  })

  it('point mode names the point and offers a way back to the district average', () => {
    const onClear = vi.fn()
    render(<WeatherForecastStrip district="Matara" areaLabel="near Deniyaya · Matara" pointMode onClearPoint={onClear} dates={['2026-10-17']} selectedDate="2026-10-17" days={day} status="ready" todayKey="2026-10-17" />)
    expect(screen.getByText(/Weather · near Deniyaya · Matara/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'District average' }))
    expect(onClear).toHaveBeenCalled()
  })

  it('hot & dry days come from the real forecast high and rain only', () => {
    const d = (tempMax, rainMm, condition = 'SUNNY') => ({ tempMax, rainMm, condition })
    expect(heatIntensity(d(29.9, 0))).toBe(0) // not hot enough (hill country)
    expect(heatIntensity(d(30, 0))).toBeCloseTo(0.35, 6)
    expect(heatIntensity(d(35, 0.2))).toBe(1)
    expect(heatIntensity(d(34, 1.5))).toBe(0) // wet day
    expect(heatIntensity(d(34, 0.5, 'RAIN'))).toBe(0) // rain code
    expect(heatIntensity(d(null, 0))).toBe(0) // no data -> no effect
    const hot = parseForecast({ daily: { time: ['2026-10-28'], weather_code: [1], precipitation_sum: [0], temperature_2m_max: [33], temperature_2m_min: [25] } })
    render(<WeatherForecastStrip district="Matara" dates={['2026-10-28']} selectedDate="2026-10-28" days={hot} status="ready" todayKey="2026-10-17" />)
    expect(screen.getByText('Hot & dry')).toBeInTheDocument()
  })
})
