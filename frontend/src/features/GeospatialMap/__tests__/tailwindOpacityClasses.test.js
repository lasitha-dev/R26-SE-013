import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Tailwind v3 only generates `<colour>/<n>` for n on the opacity scale; any
// other bare number silently produces NO class. The My Area map legend used
// `bg-[#0e1511]/88`, so its card had no background and its light text
// vanished over the light basemap. Arbitrary values need `/[0.88]`.
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const SCALE = new Set(['0', '5', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60', '65', '70', '75', '80', '85', '90', '95', '100'])

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === '__tests__' ? [] : sourceFiles(path)
    return /\.(jsx?|tsx?)$/.test(name) ? [path] : []
  })
}

describe('Tailwind colour-opacity modifiers', () => {
  it('every bare /<n> modifier is on the default opacity scale (otherwise no CSS is generated)', () => {
    const offenders = []
    for (const file of sourceFiles(ROOT)) {
      const source = readFileSync(file, 'utf8')
      for (const match of source.matchAll(/\b(?:bg|text|border|ring|from|to|via|fill|stroke|shadow|outline|divide|placeholder|accent|caret|decoration)-[\w#[\]-]+\/(\d+)(?![\w.\]])/g)) {
        if (!SCALE.has(match[1])) offenders.push(`${relative(ROOT, file)}: ${match[0]}`)
      }
    }
    expect(offenders).toEqual([])
  })
})
