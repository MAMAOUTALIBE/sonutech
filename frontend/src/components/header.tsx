'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Menu, X } from 'lucide-react';
import { Logo } from './logo';
const links = [['/', 'Accueil'], ['/expertises', 'Expertises'], ['/formations', 'Formations'], ['/a-propos', 'À propos']];
export function Header() {
  const pathname = usePathname(); const [open, setOpen] = useState(false); const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const handle = (e: KeyboardEvent) => { if (e.key === 'Escape' && open) { setOpen(false); button.current?.focus(); } };
    document.addEventListener('keydown', handle); return () => document.removeEventListener('keydown', handle);
  }, [open]);
  return <header className="site-header"><div className="header-inner"><Link href="/" aria-label="SONUTECH, accueil" onClick={()=>setOpen(false)}><Logo /></Link><nav className="desktop-nav" aria-label="Navigation principale">{links.map(([href,label])=><Link key={href} href={href} className={(href==='/'?pathname==='/':pathname.startsWith(href))?'active':''} aria-current={(href==='/'?pathname==='/':pathname.startsWith(href))?'page':undefined}>{label}</Link>)}</nav><Link href="/contact" className="button header-cta">Parlons de votre projet <ArrowRight size={17}/></Link><button className="menu-button" ref={button} aria-label={open?'Fermer le menu':'Ouvrir le menu'} aria-expanded={open} aria-controls="mobile-menu" onClick={()=>setOpen(!open)}>{open?<X/>:<Menu/>}</button></div>{open&&<nav id="mobile-menu" className="mobile-nav" aria-label="Navigation mobile">{[...links,['/contact','Parlons de votre projet']].map(([href,label])=><Link key={href} href={href} onClick={()=>setOpen(false)}>{label}<ArrowRight size={17}/></Link>)}</nav>}</header>;
}
