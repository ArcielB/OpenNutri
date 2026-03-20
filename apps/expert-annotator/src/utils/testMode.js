const TEST_MODE_KEY = 'opennutri_test_mode'
const TEST_EVENTS_KEY = 'opennutri_test_mode_events'

export function isTestModeEnabled() {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(TEST_MODE_KEY) === '1'
}

export function setTestModeEnabled(enabled) {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(TEST_MODE_KEY, enabled ? '1' : '0')
}

export function appendTestEvent(event) {
    if (typeof window === 'undefined') return
    try {
        const existing = JSON.parse(window.localStorage.getItem(TEST_EVENTS_KEY) || '[]')
        existing.push({
            ...event,
            recorded_at: new Date().toISOString(),
        })
        window.localStorage.setItem(TEST_EVENTS_KEY, JSON.stringify(existing))
    } catch (error) {
        console.error('Failed to persist test-mode event:', error)
    }
}
