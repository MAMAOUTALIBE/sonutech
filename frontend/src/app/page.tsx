import Image from 'next/image';
import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { api, getSettings, localImage, type Service, type Sector, type Slide } from '@/lib/api';
import { Hero } from '@/components/hero';
import { ExpertiseIcon } from '@/components/icon';
import { CTA, Method, SectionTitle, ServiceCards, EmptyState } from '@/components/shared';
export const metadata:Metadata={alternates:{canonical:'/'}};
export default async function Home() {
  const [services,slides,sectors,settings]=await Promise.all([api<Service[]>('services'),api<Slide[]>('slides'),api<Sector[]>('sectors'),getSettings()]);
  return <><div className="hero-wrap"><Hero slides={slides} note={settings.hero_note}/></div><div className="container"><nav className="expertise-strip" aria-label="Nos six expertises">{services.map(s=><Link href={`/expertises/${s.slug}`} key={s.slug}><ExpertiseIcon name={s.slug} size={32} className={s.slug==='energie'?'turquoise':''}/><span>{s.title}</span></Link>)}</nav><section className="expertises-section" id="expertises"><SectionTitle>Nos expertises, vos leviers de croissance</SectionTitle>{services.length?<ServiceCards services={services}/>:<EmptyState>Nos expertises seront bientôt disponibles.</EmptyState>}</section></div><Method/><section className="sectors-section container"><SectionTitle>Des solutions adaptées à votre métier</SectionTitle><div className="sector-grid">{sectors.map(s=><Link className="sector-card" href={`/secteurs/${s.slug}`} key={s.slug}><div className="sector-image"><Image src={localImage(s.image,'/images/entreprises.jpg')} alt={s.image_alt} fill sizes="(max-width: 650px) 100vw, 33vw"/></div><div className="sector-body"><h3>{s.title}</h3><p>{s.description}</p><span className="text-link">En savoir plus <ArrowRight size={17}/></span></div></Link>)}</div></section><CTA/></>;
}
