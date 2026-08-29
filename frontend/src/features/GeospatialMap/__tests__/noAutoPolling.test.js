import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

function collectSourceFiles(dir) {
  const files = []
  for (const entry of readdirSync(dir)) {
    if (entry === '__tests__' || entry === 'node_modules') continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...collectSourceFiles(full))
    } else if (/\.(js|jsx)$/.test(entry)) {
      files.push(full)
    }
  }
  return files
}

describe('11A-POLL-01: no automatic scientific polling timer exists', () => {
  it('no source file under GeospatialMap/ (excluding tests) calls setInterval or setTimeout for a scientific refresh', () => {
    const files = collectSourceFiles(FEATURE_ROOT)
    expect(files.length).toBeGreaterThan(0)
    for (const file of files) {
      const src = readFileSync(file, 'utf-8')
      expect(src.includes('setInterval(')).toBe(false)
      expect(src.includes('setTimeout(')).toBe(false)
    }
  })
})
