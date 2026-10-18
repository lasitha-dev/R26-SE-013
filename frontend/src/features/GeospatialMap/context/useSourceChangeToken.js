import { useRef } from 'react'

/**
 * A counter that moves only when the eligible-source signature changes from
 * one loaded value to another (adapters/liveSourceSignature.js). The first
 * load (empty -> value) does not count, so a page never refetches its
 * timeline just because the case records arrived after it.
 */
export function useSourceChangeToken(signature) {
  const lastRef = useRef('')
  const countRef = useRef(0)
  if (signature && signature !== lastRef.current) {
    if (lastRef.current) countRef.current += 1
    lastRef.current = signature
  }
  return countRef.current
}
