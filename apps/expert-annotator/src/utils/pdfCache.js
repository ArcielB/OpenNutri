// Durable PDF byte cache backed by the Cache Storage API.
//
// The /api/pdf proxy already sends long-lived immutable cache headers, but the
// browser's HTTP cache is volatile: large PDFs (up to 25 MB, ~200 in the queue)
// get evicted under cache pressure, so reopening a paper often re-downloads it.
// Supabase-storage PDFs are worse — they're served `no-cache` and never persist.
//
// This stores fetched PDF bytes in an explicit, named Cache Storage bucket keyed
// by URL. That survives across sessions and is only evicted under real disk
// pressure (not the aggressive HTTP-cache heuristics), so a paper is downloaded
// once and then rendered from disk. An LRU index (in localStorage) caps how many
// papers we keep so the bucket can't grow without bound.

const CACHE_NAME = 'opennutri-pdfs-v1'
const ORDER_KEY = 'opennutri-pdf-cache-order:v1'
// Sized to hold the whole working queue (~250 papers, typically 1-3 MB each,
// so a few hundred MB worst-typical). 40 was too small: reading ~20 papers
// plus their prefetched neighbours filled the LRU and evicted papers the
// reviewer had already opened, forcing slow re-downloads days later.
const MAX_ENTRIES = 150

function cachesAvailable() {
  return typeof window !== 'undefined' && 'caches' in window
}

function readOrder() {
  try {
    const raw = window.localStorage.getItem(ORDER_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

function writeOrder(order) {
  try {
    window.localStorage.setItem(ORDER_KEY, JSON.stringify(order))
  } catch {
    // localStorage full/unavailable — eviction just won't be tracked.
  }
}

// Move `url` to the front of the LRU index (most-recently-used).
function touchOrder(url) {
  writeOrder([url, ...readOrder().filter((entry) => entry !== url)])
}

// Register `url` at the BACK of the LRU index (next in line for eviction).
// Prefetches use this so a speculative warm can never displace a paper the
// reviewer actually opened; if the paper is later opened for real,
// touchOrder promotes it.
function appendOrder(url) {
  const order = readOrder()
  if (order.includes(url)) return
  writeOrder([...order, url])
}

// Drop least-recently-used entries (both the Cache Storage body and the index)
// until we're back under MAX_ENTRIES.
async function evictIfNeeded(cache) {
  const order = readOrder()
  while (order.length > MAX_ENTRIES) {
    const oldest = order.pop()
    if (!oldest) continue
    try {
      await cache.delete(oldest)
    } catch {
      // Ignore — index will still shrink so we stop looping.
    }
  }
  writeOrder(order)
}

// Returns the PDF at `url` as a fresh ArrayBuffer, cache-first. Each call returns
// a brand-new buffer (Response.arrayBuffer() copies), so PDF.js is free to detach
// it on transfer without affecting the cached copy or any other open.
export async function getPdfBytes(url) {
  if (!url) throw new Error('missing pdf url')

  if (!cachesAvailable()) {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`pdf fetch failed: ${res.status}`)
    return res.arrayBuffer()
  }

  const cache = await caches.open(CACHE_NAME)
  const hit = await cache.match(url)
  if (hit) {
    touchOrder(url)
    return hit.arrayBuffer()
  }

  const res = await fetch(url)
  if (!res.ok) throw new Error(`pdf fetch failed: ${res.status}`)
  try {
    await cache.put(url, res.clone())
    touchOrder(url)
    await evictIfNeeded(cache)
  } catch {
    // Quota or storage error — fall through and still return the bytes.
  }
  return res.arrayBuffer()
}

// Best-effort warm of the cache for `url`. Used to prefetch upcoming papers
// during idle time; never throws and skips work if already cached.
export async function prefetchPdf(url) {
  if (!url || !cachesAvailable()) return
  try {
    // When the cache is full of real reads, downloading just to self-evict
    // wastes bandwidth — skip instead.
    if (readOrder().length >= MAX_ENTRIES) return
    const cache = await caches.open(CACHE_NAME)
    if (await cache.match(url)) return
    const res = await fetch(url)
    if (!res.ok) return
    await cache.put(url, res.clone())
    appendOrder(url)
    await evictIfNeeded(cache)
  } catch {
    // Prefetch is advisory; ignore all failures.
  }
}
