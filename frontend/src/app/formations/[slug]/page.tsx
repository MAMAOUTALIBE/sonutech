import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowRight, Clock3, Monitor } from 'lucide-react';
import { api, type Course } from '@/lib/api';
import { BulletList, PageIntro } from '@/components/shared';
type Props={params:Promise<{slug:string}>};
async function getCourse(slug:string){return (await api<Course[]>('courses')).find(s=>s.slug===slug);}
export async function generateMetadata({params}:Props):Promise<Metadata>{const {slug}=await params;const c=await getCourse(slug);return {title:c?.seo_title||c?.title||'Formation introuvable',description:c?.seo_description||c?.description,alternates:{canonical:`/formations/${slug}`}};}
export default async function CoursePage({params}:Props){const {slug}=await params;const c=await getCourse(slug);if(!c)notFound();return <><PageIntro eyebrow="Formations" title={c.title} description={c.description}/><section className="container content-section detail-grid"><div><p className="body-copy">{c.body}</p><h2>Objectifs de la formation</h2><BulletList items={c.objectives}/><h2>À qui s’adresse cette formation ?</h2><BulletList items={c.audience}/><h2>Prérequis</h2><BulletList items={c.prerequisites}/><h2>Au programme</h2><ol className="programme">{c.program.map((p,i)=><li key={p}><span>{String(i+1).padStart(2,'0')}</span>{p}</li>)}</ol></div><aside className="detail-aside"><span className="course-category">{c.category}</span><h2>Place à la pratique.</h2><p className="contact-line"><Clock3 size={20}/>{c.duration}</p><p className="contact-line"><Monitor size={20}/>{c.modality}</p><p>Les modalités, le calendrier et le tarif sont précisés avec vous selon vos besoins.</p><Link href={`/contact?formation=${slug}&domaine=formation`} className="button">Demander des informations <ArrowRight size={18}/></Link></aside></section></>;}
