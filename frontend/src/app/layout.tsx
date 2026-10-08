import type { Metadata } from 'next';
import { Header } from '@/components/header';
import { Footer } from '@/components/shared';
import { Chatbot } from '@/components/chatbot';
import { SiteFrame } from '@/components/site-frame';
import { api, getSettings, siteUrl, type Service } from '@/lib/api';
import './globals.css';
export const dynamic = 'force-dynamic';
export const metadata: Metadata = { metadataBase: new URL(siteUrl), title: {default:'SONUTECH — Des idées ambitieuses. Des solutions concrètes.',template:'%s | SONUTECH'}, description:'Informatique, conseil, digitalisation, intelligence artificielle, formation et énergie : SONUTECH accompagne la transformation de votre entreprise.', openGraph:{locale:'fr_FR',type:'website',siteName:'SONUTECH',images:[{url:'/images/hero.jpg',width:1800,height:1200,alt:'Collaboration autour d’un projet numérique'}]}, robots:{index:true,follow:true} };
export default async function RootLayout({children}:Readonly<{children:React.ReactNode}>) {
  const [settings,services] = await Promise.all([getSettings().catch(()=>null),api<Service[]>('services').catch(()=>[])]);
  return <html lang="fr"><body><SiteFrame header={<Header/>} footer={<Footer settings={settings} services={services}/>} chat={<Chatbot/>}>{children}</SiteFrame></body></html>;
}
