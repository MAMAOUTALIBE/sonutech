import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { api, localImage, type Sector } from '@/lib/api';
import { BulletList, PageIntro, CTA } from '@/components/shared';
type Props={params:Promise<{slug:string}>};
async function getSector(slug:string){return (await api<Sector[]>('sectors')).find(s=>s.slug===slug);}
export async function generateMetadata({params}:Props):Promise<Metadata>{const {slug}=await params;const s=await getSector(slug);return {title:s?.seo_title||s?.title||'Secteur introuvable',description:s?.seo_description||s?.description,alternates:{canonical:`/secteurs/${slug}`}};}
export default async function SectorPage({params}:Props){const {slug}=await params;const s=await getSector(slug);if(!s)notFound();return <><PageIntro eyebrow="Secteurs" title={s.title} description={s.description}/><section className="container content-section detail-grid"><div><h2>Des solutions ancrées dans votre quotidien</h2><p className="body-copy">{s.body}</p><h2>Un accompagnement adapté</h2><BulletList items={s.prestations}/><h2>Pour votre activité</h2><BulletList items={s.benefits}/><Link href={`/contact?projet=${encodeURIComponent(s.title)}`} className="button">Parlons de votre activité <ArrowRight size={18}/></Link></div><div className="detail-photo"><Image src={localImage(s.image)} alt={s.image_alt} fill sizes="(max-width: 850px) 100vw, 40vw"/></div></section><CTA/></>;}
