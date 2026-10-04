// Pure helpers only: the engine's validator never follows `$` across an import.

export const HEARTBEAT_MS = 5000;

/** SPEC 10.3: the files whose bytes make the guard digest, in order. Never stored; computed at runtime. */
export const GUARD_DIGEST_FILES: readonly string[] = [
  'config/guard-rules.json',
  'scripts/orchestra_core/guards.py',
  'scripts/orchestra_core/hooks.py',
  'hooks/mod/guard.ts',
];

export type Marker = {
  session_id: string;
  heartbeat_ms: number;
  plugin_version: string;
  rules_sha256: string | null;
};

/** ${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/<session_id>.json */
export function markerPath(xdg: string | undefined, home: string | undefined, sessionId: string): string {
  const base = xdg ? xdg : `${home}/.local/state`;
  return `${base}/orchestra/mods/${sessionId}.json`;
}

export function markerJson(sessionId: string, version: string, rules: string | null, heartbeat: number): string {
  const marker: Marker = {
    session_id: sessionId,
    heartbeat_ms: heartbeat,
    plugin_version: version,
    rules_sha256: rules,
  };
  return JSON.stringify(marker);
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/** Decode standard padded base64 (no runtime decoder is assumed). */
export function fromBase64(text: string): Uint8Array {
  const clean = text.replace(/[^A-Za-z0-9+/]/g, '');
  const out: number[] = [];
  let bits = 0;
  let acc = 0;
  for (const ch of clean) {
    acc = (acc << 6) | B64.indexOf(ch);
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.push((acc >> bits) & 255);
    }
  }
  return Uint8Array.from(out);
}

/** UTF-8 bytes of a string (lone surrogates become U+FFFD). */
export function utf8(text: string): Uint8Array {
  const out: number[] = [];
  for (const ch of text) {
    let c = ch.codePointAt(0)!;
    if (c >= 0xd800 && c <= 0xdfff) c = 0xfffd;
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return Uint8Array.from(out);
}

/** UTF-8 decode (invalid sequences become U+FFFD). */
export function fromUtf8(bytes: Uint8Array): string {
  let out = '';
  let i = 0;
  while (i < bytes.length) {
    const b = bytes[i]!;
    let need = 0;
    let c = 0;
    if (b < 0x80) c = b;
    else if (b >= 0xc2 && b < 0xe0) (need = 1), (c = b & 31);
    else if (b >= 0xe0 && b < 0xf0) (need = 2), (c = b & 15);
    else if (b >= 0xf0 && b < 0xf5) (need = 3), (c = b & 7);
    else c = 0xfffd;
    let ok = true;
    for (let k = 1; k <= need; k++) {
      const next = bytes[i + k];
      if (next === undefined || (next & 0xc0) !== 0x80) {
        ok = false;
        break;
      }
      c = (c << 6) | (next & 63);
    }
    if (!ok || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) {
      out += '\ufffd';
      i += 1;
      continue;
    }
    out += String.fromCodePoint(c);
    i += need + 1;
  }
  return out;
}

const K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

/** SHA-256 of bytes, as lowercase hex. */
export function sha256Hex(data: Uint8Array): string {
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const length = data.length;
  const padded = new Uint8Array(((length + 9 + 63) >> 6) << 6);
  padded.set(data);
  padded[length] = 0x80;
  const bitsHigh = Math.floor(length / 0x20000000);
  const bitsLow = (length << 3) >>> 0;
  const end = padded.length;
  padded[end - 8] = (bitsHigh >>> 24) & 255;
  padded[end - 7] = (bitsHigh >>> 16) & 255;
  padded[end - 6] = (bitsHigh >>> 8) & 255;
  padded[end - 5] = bitsHigh & 255;
  padded[end - 4] = (bitsLow >>> 24) & 255;
  padded[end - 3] = (bitsLow >>> 16) & 255;
  padded[end - 2] = (bitsLow >>> 8) & 255;
  padded[end - 1] = bitsLow & 255;
  const w = new Array<number>(64).fill(0);
  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < end; off += 64) {
    for (let t = 0; t < 16; t++) w[t] = ((padded[off + 4 * t]! << 24) | (padded[off + 4 * t + 1]! << 16) | (padded[off + 4 * t + 2]! << 8) | padded[off + 4 * t + 3]!) | 0;
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(w[t - 15]!, 7) ^ rotr(w[t - 15]!, 18) ^ (w[t - 15]! >>> 3);
      const s1 = rotr(w[t - 2]!, 17) ^ rotr(w[t - 2]!, 19) ^ (w[t - 2]! >>> 10);
      w[t] = (w[t - 16]! + s0 + w[t - 7]! + s1) | 0;
    }
    let [a, b, c, d, e, f, g, hh] = h as [number, number, number, number, number, number, number, number];
    for (let t = 0; t < 64; t++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[t]! + w[t]!) | 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) | 0;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) | 0;
    }
    h[0] = (h[0]! + a) | 0;
    h[1] = (h[1]! + b) | 0;
    h[2] = (h[2]! + c) | 0;
    h[3] = (h[3]! + d) | 0;
    h[4] = (h[4]! + e) | 0;
    h[5] = (h[5]! + f) | 0;
    h[6] = (h[6]! + g) | 0;
    h[7] = (h[7]! + hh) | 0;
  }
  return h.map((x) => (x >>> 0).toString(16).padStart(8, '0')).join('');
}

/**
 * SPEC 10.3 guard digest: SHA-256 over, per file in GUARD_DIGEST_FILES order, the relative path, NUL, the
 * decimal byte length, NUL and the bytes. A missing or unreadable file (null) counts as zero bytes.
 */
export function guardDigest(contents: readonly (Uint8Array | null)[]): string {
  const chunks: Uint8Array[] = [];
  let total = 0;
  GUARD_DIGEST_FILES.forEach((rel, i) => {
    const data = contents[i] ?? new Uint8Array(0);
    const head = utf8(rel + '\0' + String(data.length) + '\0');
    chunks.push(head, data);
    total += head.length + data.length;
  });
  const all = new Uint8Array(total);
  let at = 0;
  for (const chunk of chunks) {
    all.set(chunk, at);
    at += chunk.length;
  }
  return sha256Hex(all);
}
