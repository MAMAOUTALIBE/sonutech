import type { MetadataRoute } from 'next';
import { api, siteUrl, type Content } from '@/lib/api';
export default async function sitemap():Promise<MetadataRoute.Sitemap>{const [services,courses,sectors]=await Promise.all(['services','courses','sectors'].map(p=>api<Content[]>(p)));return ['','/expertises','/formations','/a-propos','/contact','/mentions-legales','/confidentialite',...services.map(s=>`/expertises/${s.slug}`),...courses.map(c=>`/formations/${c.slug}`),...sectors.map(s=>`/secteurs/${s.slug}`)].map(path=>({url:siteUrl+path,changeFrequency:'weekly',priority:path===''?1:0.7}));}
