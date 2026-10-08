import type { MetadataRoute } from 'next';
import { siteUrl } from '@/lib/api';
export const dynamic = 'force-dynamic';
export default function robots(): MetadataRoute.Robots { return {rules:{userAgent:'*',allow:'/',disallow:['/api/']},sitemap:`${siteUrl}/sitemap.xml`}; }
