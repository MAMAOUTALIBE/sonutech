import type { Metadata } from 'next';
import { PageIntro, CTA, Method } from '@/components/shared';
import { getSettings } from '@/lib/api';
import { Lightbulb, Handshake, Compass } from 'lucide-react';
export async function generateMetadata():Promise<Metadata>{const s=await getSettings();return {title:'À propos',description:s.about_description,alternates:{canonical:'/a-propos'}};}
export default async function About(){const s=await getSettings();const icons=[Compass,Lightbulb,Handshake];return <><PageIntro eyebrow="À propos" title={s.about_title} description={s.about_description}/><section className="container content-section about-section"><div><p className="eyebrow">NOTRE APPROCHE</p><h2>Écouter. Comprendre.<br/><span className="turquoise">Construire ensemble.</span></h2></div><div>{s.about_body?.map(p=><p key={p}>{p}</p>)}</div></section><section className="container values-grid">{s.about_values?.map(({title,description},i)=>{const Icon=icons[i%icons.length];return <article className="service-card" key={title}><span className="icon-bubble"><Icon/></span><h3>{title}</h3><p>{description}</p></article>;})}</section><Method/><CTA/></>;}
