import { NextResponse } from 'next/server';
import { readFile, realpath, stat } from 'node:fs/promises';
import { resolve, sep } from 'node:path';

const types: Record<string, string> = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
function headers(type: string) {
  return { 'Content-Type': type, 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'public, max-age=86400' };
}
export async function GET(_request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  // Uploaded files are re-encoded by Django and use generated UUID filenames.
  if (!path.length || path.some(segment => !/^[a-zA-Z0-9_.-]+$/.test(segment) || segment === '.' || segment === '..') || !/\.(jpg|jpeg|png|webp)$/i.test(path.at(-1)!)) {
    return new NextResponse(null, { status: 404 });
  }
  try {
    if (process.env.MEDIA_ROOT) {
      // Docker mounts the same media volume read-only: image optimization works
      // even when production Django no longer serves /media/ (DEBUG=0).
      const root = await realpath(process.env.MEDIA_ROOT);
      const file = await realpath(resolve(root, ...path));
      if (!file.startsWith(root + sep)) return new NextResponse(null, { status: 404 });
      const info = await stat(file);
      if (!info.isFile() || info.size > 6 * 1024 * 1024) return new NextResponse(null, { status: 404 });
      const type = types[path.at(-1)!.split('.').at(-1)!.toLowerCase()];
      return new NextResponse(new Uint8Array(await readFile(file)), { headers: headers(type) });
    }
    const response = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/media/${path.map(encodeURIComponent).join('/')}`, { signal: AbortSignal.timeout(10000), cache: 'no-store', redirect: 'error' });
    if (!response.ok) return new NextResponse(null, { status: response.status === 404 ? 404 : 502 });
    const type = response.headers.get('content-type')?.split(';')[0];
    if (!type || !Object.values(types).includes(type)) return new NextResponse(null, { status: 502 });
    return new NextResponse(response.body, { headers: headers(type) });
  } catch (error) {
    const missing = error && typeof error === 'object' && 'code' in error && error.code === 'ENOENT';
    return new NextResponse(null, { status: missing ? 404 : 502 });
  }
}
