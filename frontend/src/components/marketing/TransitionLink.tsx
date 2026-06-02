import type { CSSProperties, MouseEvent, ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { goToSection, parseSectionIdFromHref } from '../../lib/pageScroll'
import { viewTransitionNavigate } from '../../lib/viewTransitionNavigate'

type TransitionLinkProps = {
  to: string
  children: ReactNode
  className?: string
  style?: CSSProperties
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void
}

/** In-app link with optional View Transition; hash links use native navigation. */
export default function TransitionLink({ to, children, className, style, onClick }: TransitionLinkProps) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const sectionId = parseSectionIdFromHref(to)

  return (
    <a
      href={to.startsWith('#') && !to.startsWith('/#') ? to : to}
      className={className}
      style={style}
      onClick={(e) => {
        onClick?.(e)
        if (e.defaultPrevented) return

        if (to.startsWith('http')) return

        if (sectionId) {
          e.preventDefault()
          goToSection(sectionId, pathname, navigate)
          return
        }

        e.preventDefault()
        viewTransitionNavigate(navigate, to)
      }}
    >
      {children}
    </a>
  )
}
