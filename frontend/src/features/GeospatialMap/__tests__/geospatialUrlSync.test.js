import { describe, expect, it } from 'vitest'

import { buildGeospatialSearchParams, buildGeospatialUrl, parseGeospatialSearchParams } from '../context/useGeospatialUrlSync'

describe('geospatial URL deep-link contract', () => {
  it('round-trips a full selection through the URL', () => {
    const selection = {
      selectedDisease: 'LSD',
      selectedOutbreakId: 'ORIGIN:Sri Lanka:2020-09-28',
      selectedForecastDay: 5,
      selectedModelRunId: '8b523733c7504ab5b0e09a492436ca37e17990d3f8a0688d4069b76bc9a807a7',
      selectedAreaId: 'jaffna',
    }
    const params = buildGeospatialSearchParams(selection)
    expect(params.toString()).toBe(
      'disease=LSD&outbreak=ORIGIN%3ASri+Lanka%3A2020-09-28&day=5&modelRun=8b523733c7504ab5b0e09a492436ca37e17990d3f8a0688d4069b76bc9a807a7&area=jaffna',
    )
    expect(parseGeospatialSearchParams(params)).toEqual({
      disease: 'LSD',
      outbreakId: 'ORIGIN:Sri Lanka:2020-09-28',
      day: 5,
      modelRunId: '8b523733c7504ab5b0e09a492436ca37e17990d3f8a0688d4069b76bc9a807a7',
      areaId: 'jaffna',
    })
  })

  it('parses an empty URL as all-nulls, day null (never a fabricated default day)', () => {
    const parsed = parseGeospatialSearchParams(new URLSearchParams(''))
    expect(parsed).toEqual({ disease: null, outbreakId: null, day: null, modelRunId: null, areaId: null })
  })

  it('day 0 round-trips correctly (falsy but present -- must not be dropped like a missing param)', () => {
    const params = buildGeospatialSearchParams({ selectedForecastDay: 0 })
    expect(params.get('day')).toBe('0')
    expect(parseGeospatialSearchParams(params).day).toBe(0)
  })

  it('buildGeospatialUrl overrides only the given keys, preserving the rest of the current selection', () => {
    const selection = { selectedDisease: 'LSD', selectedOutbreakId: 'ORIGIN:Sri Lanka:2020-09-28', selectedForecastDay: 2 }
    const url = buildGeospatialUrl('/vet/geospatial/area', selection, { selectedForecastDay: 5 })
    expect(url).toBe('/vet/geospatial/area?disease=LSD&outbreak=ORIGIN%3ASri+Lanka%3A2020-09-28&day=5')
  })

  it('buildGeospatialUrl with no selection fields returns the bare path', () => {
    expect(buildGeospatialUrl('/vet/geospatial/map', {})).toBe('/vet/geospatial/map')
  })
})
