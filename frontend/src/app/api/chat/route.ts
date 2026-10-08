import { NextRequest, NextResponse } from 'next/server';
import { isIP } from 'node:net';

export const runtime = 'nodejs';
const headers = { 'Cache-Control': 'no-store' };
const fail = (detail: string, status: number) => NextResponse.json({ detail }, { status, headers });

export async function POST(request: NextRequest) {
  const allowed = new Set([request.nextUrl.origin, process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000']);
  const origin = request.headers.get('origin');
  if (!origin || !allowed.has(origin)) return fail('Origine non autorisée.', 403);
  if (!request.headers.get('content-type')?.includes('application/json')) return fail('Contenu JSON requis.', 415);
  if (Number(request.headers.get('content-length') || 0) > 32000) return fail('Message trop volumineux.', 413);
  let body: Record<string, unknown>;
  try {
    // Bound the stream itself rather than buffering an unbounded chunked request.
    const reader = request.body?.getReader();
    if (!reader) return fail('Contenu JSON requis.', 400);
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > 32000) { await reader.cancel(); return fail('Message trop volumineux.', 413); }
      chunks.push(chunk.value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fail('Demande invalide.', 400);
    body = parsed as Record<string, unknown>;
  } catch { return fail('Contenu JSON invalide.', 400); }
  if (!['start', 'message', 'contact'].includes(String(body.action))) return fail('Action invalide.', 400);
  const secret = process.env.PROXY_SHARED_SECRET || '';
  const clientIp = request.headers.get('x-real-ip') || '';
  if (process.env.TRUST_PROXY_HEADERS !== '1' || secret.length < 32 || !isIP(clientIp)) return fail('Assistant temporairement indisponible. Vous pouvez nous contacter directement.', 503);
  try {
    const response = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/v1/public/chat/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sonutech-Proxy-Secret': secret, 'X-Sonutech-Client-IP': clientIp },
      body: JSON.stringify(body), signal: AbortSignal.timeout(35000), cache: 'no-store', redirect: 'error',
    });
    if (!response.ok) {
      const errors: Record<number, string> = { 400: 'Vérifiez votre demande et vos coordonnées.', 401: 'Votre conversation a expiré. Démarrez une nouvelle discussion.', 403: 'Cette demande ne peut pas être traitée.', 409: 'Votre message est encore en cours de traitement. Réessayez dans quelques instants.', 429: 'Trop de demandes pour le moment. Réessayez plus tard ou contactez-nous directement.' };
      return fail(errors[response.status] || 'Assistant temporairement indisponible. Réessayez ou contactez-nous directement.', [400, 401, 403, 409, 429].includes(response.status) ? response.status : 503);
    }
    const data = await response.json();
    // Only publish the narrow visitor contract, never a provider diagnostic or private CRM ID.
    const result: Record<string, unknown> = {};
    for (const key of ['available', 'captured', 'suggest_contact']) if (typeof data[key] === 'boolean') result[key] = data[key];
    for (const key of ['token', 'reply', 'detail']) if (typeof data[key] === 'string') result[key] = data[key];
    return NextResponse.json(result, { status: response.status, headers });
  } catch { return fail('Assistant temporairement indisponible. Réessayez ou contactez-nous directement.', 503); }
}
