'use client';
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, BrainCircuit } from 'lucide-react';
import type { Slide } from '@/lib/api';
export function Hero({slides,note}: {slides: Slide[];note:string}) {
  const [index,setIndex] = useState(0);
  if (!slides.length) return <section className="hero hero-empty"><h1>Construisons votre prochain projet.</h1><Link href="/contact" className="button">Parlons de votre projet <ArrowRight size={18}/></Link></section>;
  const slide=slides[index];
  const move=(amount:number)=>setIndex((index+amount+slides.length)%slides.length);
  const image = slide.image?.startsWith('/images/')||slide.image?.startsWith('/media/') ? slide.image:'/images/hero.jpg';
  return <section className="hero" aria-roledescription="carrousel" aria-label="Les solutions SONUTECH" tabIndex={0} onKeyDown={e=>{if(e.key==='ArrowRight'){e.preventDefault();move(1);}if(e.key==='ArrowLeft'){e.preventDefault();move(-1);}}}>
    <Image key={image} src={image} alt={slide.image_alt || ''} fill priority sizes="100vw" className="hero-photo"/>
    <div className="hero-gradient"/><div className="hero-shape"/>
    <div className="hero-content" aria-live="polite" aria-atomic="true"><p className="hero-eyebrow">INFORMATIQUE <span>• IA • CONSEIL •</span> ÉNERGIE</p><h1>{slide.title}{slide.accent&&<><br/><span>{slide.accent}</span></>}</h1><p className="hero-description">{slide.description}</p><div className="hero-actions"><Link href={slide.primary_href || '/contact'} className="button">{slide.primary_label || 'Discuter de mon projet'} <ArrowRight size={18}/></Link><Link href={slide.secondary_href || '/#expertises'} className="button button-outline">{slide.secondary_label || 'Explorer nos services'}</Link></div><p className="hero-note">{note}</p></div>
    <span className="hero-badge"><BrainCircuit size={25}/> IA & automatisation</span>
    {slides.length>1&&<div className="carousel-controls"><button onClick={()=>move(-1)} aria-label="Diapositive précédente"><ArrowLeft size={20}/></button><div className="carousel-dots">{slides.map((s,i)=><button key={s.id} className={i===index?'selected':''} aria-label={`Afficher la diapositive ${i+1}`} aria-current={i===index?'true':undefined} onClick={()=>setIndex(i)}/>)}</div><button onClick={()=>move(1)} aria-label="Diapositive suivante"><ArrowRight size={20}/></button></div>}
  </section>;
}
