/**
 * Router access that also works when a page is rendered outside a Router
 * (unit/smoke tests render the pages bare). Whether a Router exists never
 * changes for a mounted tree, so the hook order stays stable.
 */
import { useInRouterContext, useLocation, useNavigate } from 'react-router-dom'

export function useOptionalNavigate() {
  const inRouter = useInRouterContext()
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return inRouter ? useNavigate() : null
}

export function useOptionalLocationState() {
  const inRouter = useInRouterContext()
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return inRouter ? useLocation().state ?? null : null
}
