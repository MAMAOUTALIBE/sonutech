import type { Metadata } from 'next';
import { api, type Service } from '@/lib/api';
import { PageIntro, ServiceCards, CTA, Method } from '@/components/shared';
export const metadata: Metadata={title:'Nos expertises',description:'Six domaines complémentaires pour accompagner votre entreprise : informatique, conseil, digitalisation, IA, formation et énergie.',alternates:{canonical:'/expertises'}};
export default async function Expertises() { const services=await api<Service[]>('services');return <><PageIntro eyebrow="Expertises" title="Vos ambitions. Nos expertises." description="Du premier conseil à la mise en œuvre, nous réunissons les compétences utiles à votre projet."/><section className="container content-section"><ServiceCards services={services}/></section><Method/><CTA/></>; }
