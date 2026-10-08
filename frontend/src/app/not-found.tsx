import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
export default function NotFound(){return <section className="container not-found"><p className="eyebrow">ERREUR 404</p><span className="error-number">404</span><h1>Cette page a pris un autre chemin.</h1><p>Retrouvons ensemble la bonne direction.</p><Link href="/" className="button">Retour à l’accueil <ArrowRight size={18}/></Link></section>;}
