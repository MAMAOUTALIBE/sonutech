import 'server-only';
import { cache } from 'react';
export interface Content {
  id: number; title: string; slug: string; description: string; body: string;
  image: string; image_alt: string; seo_title: string; seo_description: string; order: number;
}
export interface Service extends Content { icon: string; needs: string[]; prestations: string[]; benefits: string[] }
export interface Sector extends Content { prestations: string[]; benefits: string[] }
export interface Course extends Content { objectives: string[]; audience: string[]; prerequisites: string[]; program: string[]; duration: string; modality: string; category: string }
export interface Slide extends Content { accent: string; primary_label: string; primary_href: string; secondary_label: string; secondary_href: string }
export interface Settings { site_name: string; tagline: string; email: string; phone: string; address: string; legal_text: string; privacy_text: string; social_links: Record<string,string>; about_title:string; about_description:string; about_body:string[]; about_values:{title:string;description:string}[]; method_steps:{title:string;description:string}[]; hero_note:string }
export const api = cache(async <T,>(path: string): Promise<T> => {
  const response = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/v1/public/${path}/`, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
  if (!response.ok) throw new Error(`Content unavailable (${response.status})`);
  return response.json() as Promise<T>;
});
export const getSettings = () => api<Settings>('settings');
export const siteUrl = process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
export function localImage(src: string | undefined, fallback = '/images/hero.jpg') {
  if (!src) return fallback;
  if (src.startsWith('/images/') || src.startsWith('/media/')) return src;
  try { const url = new URL(src); if (url.pathname.startsWith('/media/')) return url.pathname; } catch { /* only local managed assets are displayed */ }
  return fallback;
}
