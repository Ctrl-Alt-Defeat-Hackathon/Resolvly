import type { NavigateFunction, NavigateOptions, To } from 'react-router-dom'

/** Navigate with a cross-fade when the browser supports View Transitions API. */
export function viewTransitionNavigate(
  navigate: NavigateFunction,
  to: To,
  options?: NavigateOptions,
) {
  if (typeof document !== 'undefined' && 'startViewTransition' in document) {
    ;(document as Document & { startViewTransition: (cb: () => void) => void }).startViewTransition(
      () => navigate(to, options),
    )
    return
  }
  navigate(to, options)
}
