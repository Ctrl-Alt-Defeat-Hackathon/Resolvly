import { useEffect } from 'react'
import type { CSSProperties, ElementType, ReactNode } from 'react'

export interface RevealProps {
  children?: ReactNode
  delay?: number
  as?: string
  className?: string
  style?: CSSProperties
  id?: string
  href?: string
  [key: string]: unknown
}

export function Reveal({ children, delay = 0, as: Tag = 'div', className = '', style, ...rest }: RevealProps) {
  const cls = ['reveal', className].filter(Boolean).join(' ')
  const C = Tag as ElementType
  return (
    <C
      className={cls}
      style={{ transitionDelay: delay ? `${delay}ms` : undefined, ...style }}
      {...rest}
    >
      {children}
    </C>
  )
}

export function useRevealEngine() {
  useEffect(() => {
    if ((window as Window & { __dlRevealActive?: boolean }).__dlRevealActive) return

    function reveal(el: Element) {
      el.classList.add('is-in')
      setTimeout(() => {
        ;(el as HTMLElement).style.transition = 'none'
        ;(el as HTMLElement).style.opacity = '1'
        ;(el as HTMLElement).style.transform = 'none'
      }, 1000)
    }

    function sweep() {
      const vh = window.innerHeight || document.documentElement.clientHeight
      document.querySelectorAll('.dreelio-landing .reveal:not(.is-in)').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.top < vh * 0.94 && r.bottom > 0) reveal(el)
      })
    }

    ;(window as Window & { __dlRevealActive?: boolean }).__dlRevealActive = true
    window.addEventListener('scroll', sweep, { passive: true })
    window.addEventListener('resize', sweep)

    let n = 0
    const iv = setInterval(() => {
      sweep()
      if (++n > 50) clearInterval(iv)
    }, 80)
    requestAnimationFrame(sweep)
    setTimeout(() => {
      document.querySelectorAll('.dreelio-landing .reveal:not(.is-in)').forEach(reveal)
    }, 3000)

    return () => {
      window.removeEventListener('scroll', sweep)
      window.removeEventListener('resize', sweep)
      clearInterval(iv)
      ;(window as Window & { __dlRevealActive?: boolean }).__dlRevealActive = false
    }
  }, [])
}
