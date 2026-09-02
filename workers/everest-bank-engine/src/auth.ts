// Single access-key gate shared with everest-cfo-agent (issue #19737 scope: "same
// access-key gate as everest-cfo-agent ... do not invent a new one"). This is a byte-for-byte
// port of that Worker's worker/src/auth.ts (X-CFO-Secret header or ?key= query param, constant
// time compare) so both Workers speak the identical convention.

export function isAuthorized(request: Request, sharedSecret: string | undefined): boolean {
  if (!sharedSecret) return false;
  const header = request.headers.get("X-CFO-Secret");
  if (header && timingSafeEqual(header, sharedSecret)) return true;
  const url = new URL(request.url);
  const queryKey = url.searchParams.get("key");
  if (queryKey && timingSafeEqual(queryKey, sharedSecret)) return true;
  return false;
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
