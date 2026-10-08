import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { api, type Service } from '@/lib/api';
import { BulletList, PageIntro, Method } from '@/components/shared';
import { ExpertiseIcon } from '@/components/icon';
type Props={params:Promise<{slug:string}>};
async function getService(slug:string){return (await api<Service[]>('services')).find(s=>s.slug===slug);}
export async function generateMetadata({params}:Props):Promise<Metadata>{const {slug}=await params;const s=await getService(slug);return {title:s?.seo_title||s?.title||'Expertise introuvable',description:s?.seo_description||s?.description,alternates:{canonical:`/expertises/${slug}`}};}
export default async function ServicePage({params}:Props){const {slug}=await params;const service=await getService(slug);if(!service)notFound();return <><PageIntro eyebrow="Expertises" title={service.title} description={service.description}/><section className="container content-section detail-grid"><div><span className="icon-bubble large"><ExpertiseIcon name={slug} size={36}/></span><h2>Une réponse à vos besoins</h2><p className="body-copy">{service.body}</p><BulletList items={service.needs}/><h2>Ce que nous vous apportons</h2><BulletList items={service.prestations}/><h2>Des bénéfices concrets</h2><BulletList items={service.benefits}/></div><aside className="detail-aside"><p className="eyebrow">AVANÇONS ENSEMBLE</p><h2>Votre projet commence par un échange.</h2><p>Parlons de votre contexte, de vos priorités et de la solution qui vous correspond.</p><Link href={`/contact?domaine=${slug}`} className="button">Discuter de mon projet <ArrowRight size={18}/></Link>{slug==='formation'&&<Link href="/formations" className="text-link">Découvrir les formations <ArrowRight size={18}/></Link>}</aside></section><Method/></>;}
