'use client';
export default function ErrorPage({reset}:{reset:()=>void}){return <section className="container not-found"><p className="eyebrow">UNE PAUSE INATTENDUE</p><h1>Le contenu est momentanément indisponible.</h1><p>Veuillez réessayer dans quelques instants.</p><button className="button" onClick={reset}>Réessayer</button></section>;}
