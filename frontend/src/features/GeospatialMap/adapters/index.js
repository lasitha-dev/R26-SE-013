import { DISEASE_CODE } from '../disease/diseaseRegistry'
import * as fmdOutbreakAdapter from './fmdOutbreakAdapter'
import * as lsdOutbreakAdapter from './lsdOutbreakAdapter'

const ADAPTERS_BY_DISEASE = {
  [DISEASE_CODE.LSD]: lsdOutbreakAdapter,
  [DISEASE_CODE.FMD]: fmdOutbreakAdapter,
}

/** The one place a component picks an outbreak adapter by disease code --
 * never `if (disease === 'LSD') lsdAdapter.x() else fmdAdapter.x()`
 * scattered through pages/components. */
export function getOutbreakAdapter(diseaseCode) {
  const adapter = ADAPTERS_BY_DISEASE[diseaseCode]
  if (!adapter) {
    throw new Error(`no outbreak adapter registered for disease code: ${diseaseCode}`)
  }
  return adapter
}
