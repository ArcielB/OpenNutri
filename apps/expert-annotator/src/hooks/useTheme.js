import { useState, useEffect, useLayoutEffect, useCallback } from 'react'

const STORAGE_KEY = 'opennutri-theme'

function getSystemTheme() {
    if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function useTheme() {
    const [systemTheme, setSystemTheme] = useState(getSystemTheme)
    const [override, setOverride] = useState(() => {
        if (typeof window === 'undefined') return null
        const saved = sessionStorage.getItem(STORAGE_KEY)
        if (!saved) return null
        const system = getSystemTheme()
        if (saved !== system) {
            sessionStorage.removeItem(STORAGE_KEY)
            return null
        }
        return saved
    })

    const theme = override || systemTheme

    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined

        const media = window.matchMedia('(prefers-color-scheme: light)')
        const handleChange = (event) => {
            setSystemTheme(event.matches ? 'light' : 'dark')
        }

        if (media.addEventListener) {
            media.addEventListener('change', handleChange)
        } else {
            media.addEventListener(handleChange)
        }

        return () => {
            if (media.removeEventListener) {
                media.removeEventListener('change', handleChange)
            } else {
                media.removeEventListener(handleChange)
            }
        }
    }, [])

    useLayoutEffect(() => {
        if (typeof document === 'undefined') return
        document.documentElement.setAttribute('data-theme', theme)
    }, [theme])

    useEffect(() => {
        if (typeof window === 'undefined') return
        if (override) {
            sessionStorage.setItem(STORAGE_KEY, override)
        } else {
            sessionStorage.removeItem(STORAGE_KEY)
        }
    }, [override])

    const toggleTheme = useCallback(() => {
        setOverride((prev) => {
            const current = prev || systemTheme
            return current === 'dark' ? 'light' : 'dark'
        })
    }, [systemTheme])

    const clearOverride = useCallback(() => {
        setOverride(null)
    }, [])

    return { theme, toggleTheme, clearOverride }
}
