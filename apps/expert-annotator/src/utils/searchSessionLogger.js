import { supabase } from '../supabaseClient'

export const SEARCH_LOG_DEBOUNCE_MS = 250
let loggingDisabled = false

function normalizeQuery(value) {
    return (value || '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim()
}

function snapshotOptions(options, optionType) {
    return (options || []).slice(0, 10).map((option, index) => ({
        id: String(option.id),
        label: option.canonical_name || option.name || '',
        option_type: optionType,
        rank: index,
    }))
}

export function createSearchSession({ searchType, inputSource = 'typed' }) {
    return {
        searchType,
        inputSource,
        startedAt: new Date().toISOString(),
        steps: [],
    }
}

export function appendSearchStep(sessionRef, { query, shownOptions, optionType, inputSource }) {
    if (!sessionRef.current) {
        sessionRef.current = createSearchSession({
            searchType: optionType === 'food' ? 'food' : 'nutrient',
            inputSource: inputSource || 'typed',
        })
    }

    const normalizedQuery = normalizeQuery(query)
    if (!normalizedQuery) return

    const step = {
        query,
        query_normalized: normalizedQuery,
        shown_options: snapshotOptions(shownOptions, optionType),
        timestamp: new Date().toISOString(),
    }

    const steps = sessionRef.current.steps
    const lastStep = steps[steps.length - 1]

    if (lastStep && lastStep.query_normalized === normalizedQuery) {
        steps[steps.length - 1] = step
    } else {
        steps.push(step)
    }
}

export async function persistSearchSession(sessionRef, {
    userId,
    status,
    selectedOption = null,
}) {
    const session = sessionRef.current
    sessionRef.current = null

    if (!session || !userId || !session.steps.length || loggingDisabled) return

    const payload = {
        user_id: userId,
        search_type: session.searchType,
        input_source: session.inputSource,
        status,
        selected_option_id: selectedOption?.id ? String(selectedOption.id) : null,
        selected_option_label: selectedOption?.label || null,
        selected_option_type: selectedOption?.type || null,
        query_steps: session.steps,
        started_at: session.startedAt,
        ended_at: new Date().toISOString(),
    }

    const { error } = await supabase.from('search_sessions').insert(payload)
    if (error) {
        console.error('Failed to persist search session:', error)
        if (
            error.code === 'PGRST205' ||
            error.message?.toLowerCase().includes('search_sessions') ||
            error.message?.toLowerCase().includes('relation')
        ) {
            loggingDisabled = true
        }
    }
}
