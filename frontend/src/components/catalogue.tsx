'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Clock3, Search, GraduationCap } from 'lucide-react';
import type { Course } from '@/lib/api';
export function Catalogue({courses}: {courses:Course[]}) {
  const [category,setCategory]=useState('Toutes');const [query,setQuery]=useState('');
  const categories=['Toutes',...new Set(courses.map(c=>c.category))];
  const normalized=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const filtered=courses.filter(c=>(category==='Toutes'||c.category===category)&&normalized(c.title+' '+c.description).includes(normalized(query)));
  return <><div className="catalogue-tools"><div className="filter-tabs" aria-label="Filtrer les formations">{categories.map(c=><button key={c} onClick={()=>setCategory(c)} aria-pressed={category===c} className={category===c?'selected':''}>{c}</button>)}</div><label className="search-field"><Search size={20}/><span className="sr-only">Rechercher une formation</span><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Rechercher une formation"/></label></div><p className="result-count" role="status">{filtered.length} formation{filtered.length!==1?'s':''}</p><div className="course-grid">{filtered.map(c=><article className="course-card" key={c.slug}><span className="course-category"><GraduationCap size={19}/>{c.category}</span><h2><Link href={`/formations/${c.slug}`}>{c.title}</Link></h2><p>{c.description}</p><div className="course-meta"><span><Clock3 size={16}/>{c.duration}</span><span>{c.modality}</span></div><Link href={`/formations/${c.slug}`} className="text-link">Découvrir la formation <ArrowRight size={18}/></Link></article>)}</div>{!filtered.length&&<div className="empty-state"><h2>Aucune formation ne correspond à votre recherche.</h2><p>Essayez un autre mot-clé ou découvrez l’ensemble du catalogue.</p><button className="button" onClick={()=>{setQuery('');setCategory('Toutes');}}>Réinitialiser les filtres</button></div>}</>;
}
