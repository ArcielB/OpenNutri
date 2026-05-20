import { supabase } from '../supabaseClient'

const LOCAL_STORAGE_PREFIX = 'opennutri-evidence-dedup:v2:'

export function readLocalDedup(paperId) {
    if (!paperId || typeof window === 'undefined') return null
    try {
        const raw = window.localStorage.getItem(LOCAL_STORAGE_PREFIX + String(paperId))
        if (!raw) return null
        const parsed = JSON.parse(raw)
        return parsed && typeof parsed === 'object' ? parsed : null
    } catch {
        return null
    }
}

export function writeLocalDedup(paperId, clusters) {
    if (!paperId || typeof window === 'undefined') return
    if (!clusters || Object.keys(clusters).length === 0) return
    try {
        window.localStorage.setItem(LOCAL_STORAGE_PREFIX + String(paperId), JSON.stringify(clusters))
    } catch {
        // ignore quota / disabled-storage errors
    }
}

export async function fetchRemoteDedup(paperId) {
    if (!paperId) return null
    const { data, error } = await supabase
        .from('paper_evidence_dedup')
        .select('clusters')
        .eq('paper_id', paperId)
        .maybeSingle()
    if (error) return null
    return data?.clusters && typeof data.clusters === 'object' ? data.clusters : null
}

export async function writeRemoteDedup(paperId, clusters) {
    if (!paperId || !clusters || Object.keys(clusters).length === 0) return
    await supabase.rpc('merge_paper_evidence_dedup', {
        p_paper_id: paperId,
        p_clusters: clusters,
    })
}
