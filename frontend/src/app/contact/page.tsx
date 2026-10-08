import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { MessageCircle, Mail, Phone, ShieldCheck } from 'lucide-react';
import { api, getSettings, type Service, type Course } from '@/lib/api';
import { PageIntro } from '@/components/shared';
import { ContactForm } from '@/components/contact-form';
export const metadata:Metadata={title:'Contact et demande de devis',description:'Parlez-nous de votre projet. Contactez SONUTECH pour une solution numérique, une formation ou un accompagnement sur mesure.',alternates:{canonical:'/contact'}};
export default async function Contact({searchParams}:{searchParams:Promise<{domaine?:string;formation?:string;projet?:string}>}){
 const query=await searchParams;const [services,courses,settings]=await Promise.all([api<Service[]>('services'),api<Course[]>('courses'),getSettings()]);
 const course=query.formation?courses.find(c=>c.slug===query.formation):undefined;if(query.formation&&!course)notFound();
 const domain=services.some(s=>s.slug===query.domaine)?query.domaine!:'';
 return <><PageIntro eyebrow="Contact" title="Parlons de votre projet." description="Une idée, un besoin ou une question ? Prenons le temps d’en discuter."/><section className="container content-section contact-layout"><aside className="contact-aside"><span className="icon-bubble large"><MessageCircle size={34}/></span><h2>Tout commence<br/>par un échange.</h2><p>Décrivez-nous votre besoin. Nous pourrons identifier ensemble les prochaines étapes.</p>{settings.email&&<a className="contact-line" href={`mailto:${settings.email}`}><Mail size={20}/>{settings.email}</a>}{settings.phone&&<a className="contact-line" href={`tel:${settings.phone.replace(/\s/g,'')}`}><Phone size={20}/>{settings.phone}</a>}<div className="privacy-promise"><ShieldCheck size={25}/><p>Vos informations restent confidentielles et servent uniquement à vous accompagner.</p></div></aside><ContactForm services={services} initialDomain={course?'formation':domain} course={course} initialProject={query.projet||''}/></section></>;
}
