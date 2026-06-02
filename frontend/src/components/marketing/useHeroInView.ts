import { useEffect, useState } from 'react'

/** True while the hero (`#top` by default) is still in view — used to swap nav actions. */
export function useHeroInView(heroId = 'top') {
  const [inHero, setInHero] = useState(true)

  useEffect(() => {
    const hero = document.getElementById(heroId)
    if (!hero) {
      setInHero(false)
      return
    }

    const update = () => {
      const rect = hero.getBoundingClientRect()
      setInHero(rect.bottom > 88)
    }

    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [heroId])

  return inHero
}
