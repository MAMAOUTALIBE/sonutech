import type { Metadata } from 'next';
import { api, type Course } from '@/lib/api';
import { PageIntro, CTA } from '@/components/shared';
import { Catalogue } from '@/components/catalogue';
export const metadata:Metadata={title:'Nos formations',description:'Développez les compétences de vos équipes en informatique, outils numériques, CRM et intelligence artificielle.',alternates:{canonical:'/formations'}};
export default async function Formations(){const courses=await api<Course[]>('courses');return <><PageIntro eyebrow="Formations" title="Les compétences pour aller plus loin." description="Des parcours pratiques pour prendre en main vos outils et gagner en autonomie, à votre rythme."/><section className="container content-section"><Catalogue courses={courses}/></section><CTA/></>;}
