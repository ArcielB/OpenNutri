// Same-origin PDF proxy (Vercel serverless function).
//
// Many publisher / aggregator PDF URLs (and EuropePMC's ?pdf=render form) either
// omit Access-Control-Allow-Origin or 302-redirect without CORS headers, so the
// in-browser annotator (react-pdf / PDF.js) cannot fetch them directly. This
// endpoint fetches the PDF server-side (no CORS constraints, follows redirects)
// and re-serves the bytes same-origin with permissive CORS, so PDF.js can render
// papers sourced from arbitrary open-access hosts.
//
// Abuse hardening: https-only, IP-literal / loopback hosts rejected, and the
// upstream payload must actually be a PDF (%PDF- magic) before we return it.

import { Buffer } from 'node:buffer';

export const config = { maxDuration: 30 };

const MAX_BYTES = 25 * 1024 * 1024; // refuse absurdly large bodies

function isBlockedHost(host) {
  if (!host) return true;
  const h = host.toLowerCase();
  if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.local') || h.endsWith('.internal')) {
    return true;
  }
  // IPv4 literal or bracketed/colon IPv6 literal — block to avoid SSRF to internal hosts.
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h)) return true;
  if (h.includes(':') || h.startsWith('[')) return true;
  return false;
}

export default async function handler(req, res) {
  const raw = req.query?.url;
  const target = Array.isArray(raw) ? raw[0] : raw;
  if (!target) {
    res.status(400).json({ error: 'missing url' });
    return;
  }

  let u;
  try {
    u = new URL(target);
  } catch {
    res.status(400).json({ error: 'invalid url' });
    return;
  }
  if (u.protocol !== 'https:') {
    res.status(400).json({ error: 'https only' });
    return;
  }
  if (isBlockedHost(u.hostname)) {
    res.status(403).json({ error: 'host not allowed' });
    return;
  }

  let upstream;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    upstream = await fetch(u.toString(), {
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; OpenNutriPDF/1.0)',
        Accept: 'application/pdf,*/*',
      },
    });
    clearTimeout(timer);
  } catch {
    res.status(502).json({ error: 'upstream fetch failed' });
    return;
  }
  if (!upstream.ok) {
    res.status(502).json({ error: `upstream ${upstream.status}` });
    return;
  }

  let buf;
  try {
    buf = Buffer.from(await upstream.arrayBuffer());
  } catch {
    res.status(502).json({ error: 'upstream read failed' });
    return;
  }
  if (buf.length > MAX_BYTES) {
    res.status(413).json({ error: 'pdf too large' });
    return;
  }
  // Only ever return real PDFs — keeps this from being used as a generic proxy.
  if (buf.subarray(0, 5).toString('latin1') !== '%PDF-') {
    res.status(415).json({ error: 'upstream is not a pdf' });
    return;
  }

  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Access-Control-Allow-Origin', '*');
  // Paper PDFs are content-immutable, so cache aggressively: the browser keeps a
  // copy for a year and skips revalidation (`immutable`), and the Vercel edge
  // holds it too. Each paper is downloaded from the upstream host at most once.
  res.setHeader('Cache-Control', 'public, max-age=31536000, s-maxage=31536000, immutable');
  res.setHeader('Content-Length', String(buf.length));
  res.status(200).send(buf);
}
