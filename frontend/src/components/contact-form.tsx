'use client';
import { useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, CheckCircle2, LoaderCircle } from 'lucide-react';
import type { Service } from '@/lib/api';
type Kind='contact'|'quote'|'training';
export function ContactForm({services,initialDomain,course,initialProject}: {services:Service[];initialDomain:string;course?:{slug:string;title:string};initialProject:string}) {
  const [kind,setKind]=useState<Kind>(course?'training':'contact');const [busy,setBusy]=useState(false);const [success,setSuccess]=useState(false);const [error,setError]=useState('');const [fieldErrors,setFieldErrors]=useState<Record<string,string>>({});
  const submitting=useRef(false);const key=useRef<string|null>(null);const snapshot=useRef('');const statusRef=useRef<HTMLDivElement>(null);
  async function submit(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(submitting.current)return;
    const form=event.currentTarget; if(!form.reportValidity())return;
    const data=Object.fromEntries(new FormData(form));
    const payload={...data,kind,course:course?.slug||null,deadline:data.deadline||''};
    const encoded=JSON.stringify(payload);
    if(!key.current||snapshot.current!==encoded){key.current=crypto.randomUUID();snapshot.current=encoded;}
    submitting.current=true;setBusy(true);setError('');setFieldErrors({});
    try{
      const response=await fetch('/api/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,idempotency_key:key.current})});
      const result=await response.json();
      if(!response.ok){
        if(response.status===429)throw new Error('Vous avez effectué plusieurs demandes. Merci de patienter quelques minutes avant de réessayer.');
        if(response.status===400){const errors:Record<string,string>={};for(const [name,messages] of Object.entries(result)){errors[name]=Array.isArray(messages)?messages.join(' '):String(messages);}setFieldErrors(errors);throw new Error('Certains champs nécessitent votre attention. Vérifiez les indications ci-dessous.');}
        throw new Error('Votre demande n’a pas pu être confirmée. Réessayez : une demande déjà enregistrée ne sera pas créée en double.');
      }
      if(!result.id)throw new Error('L’enregistrement de votre demande n’a pas pu être confirmé.');
      setSuccess(true);setTimeout(()=>statusRef.current?.focus(),0);
    }catch(e){setError(e instanceof TypeError?'La connexion a été interrompue. Votre demande n’a pas pu être confirmée. Vérifiez votre connexion et réessayez.':e instanceof Error?e.message:'Une erreur est survenue. Veuillez réessayer.');}
    finally{submitting.current=false;setBusy(false);}
  }
  function invalid(name:string){return {'aria-invalid':!!fieldErrors[name],'aria-describedby':fieldErrors[name]?`${name}-error`:undefined};}
  function fieldError(name:string){return fieldErrors[name]?<span id={`${name}-error`} className="field-error">{fieldErrors[name]}</span>:null;}
  if(success)return <div className="form-success" role="status" tabIndex={-1} ref={statusRef}><CheckCircle2 size={50}/><h2>Votre demande est bien enregistrée.</h2><p>Merci pour votre message. SONUTECH reviendra vers vous à l’adresse email indiquée.</p><Link href="/" className="button">Retour à l’accueil <ArrowRight size={18}/></Link></div>;
  return <form onSubmit={submit} className="contact-form">
    {!course&&<fieldset className="form-kind"><legend>Comment pouvons-nous vous aider ?</legend><div>{([['contact','Nous contacter'],['quote','Demander un devis']] as const).map(([value,label])=><label key={value} className={kind===value?'selected':''}><input type="radio" name="request_kind" value={value} checked={kind===value} onChange={()=>setKind(value)}/>{label}</label>)}</div></fieldset>}
    {course&&<div className="training-request"><span className="eyebrow">DEMANDE D’INFORMATIONS</span><h2>{course.title}</h2></div>}
    <p className="form-note">Les champs marqués d’un * sont obligatoires.</p>
    <div className="form-grid"><label>Nom et prénom *<input name="name" required minLength={2} maxLength={150} autoComplete="name" placeholder="Votre nom et prénom" {...invalid('name')}/>{fieldError('name')}</label><label>Entreprise <span className="optional">(facultatif)</span><input name="company" maxLength={180} autoComplete="organization" placeholder="Nom de votre entreprise" {...invalid('company')}/>{fieldError('company')}</label><label>Adresse email *<input name="email" type="email" required maxLength={254} autoComplete="email" placeholder="vous@entreprise.fr" {...invalid('email')}/>{fieldError('email')}</label><label>Téléphone <span className="optional">(facultatif)</span><input name="phone" type="tel" maxLength={40} autoComplete="tel" placeholder="Votre numéro de téléphone" {...invalid('phone')}/>{fieldError('phone')}</label></div>
    <label>Domaine concerné *<select name="domain" required defaultValue={initialDomain} {...invalid('domain')}><option value="" disabled>Choisissez une expertise</option>{services.map(s=><option value={s.slug} key={s.slug}>{s.title}</option>)}</select>{fieldError('domain')}</label>
    {kind==='quote'&&<div className="quote-fields"><label>Type de projet *<input name="project_type" required maxLength={180} defaultValue={initialProject} placeholder="Site web, CRM, automatisation…" {...invalid('project_type')}/>{fieldError('project_type')}</label><div className="form-grid"><label>Budget indicatif <span className="optional">(facultatif)</span><select name="budget"><option value="">À définir ensemble</option><option>Moins de 2 000 €</option><option>2 000 à 5 000 €</option><option>5 000 à 15 000 €</option><option>Plus de 15 000 €</option></select>{fieldError('budget')}</label><label>Échéance souhaitée <span className="optional">(facultatif)</span><input name="deadline" type="date" {...invalid('deadline')}/>{fieldError('deadline')}</label></div></div>}
    <label>Votre message *<textarea name="message" required minLength={10} maxLength={10000} rows={6} placeholder="Parlez-nous de votre projet, de vos besoins et de vos envies…" defaultValue={initialProject?`Bonjour, je souhaite échanger au sujet de mon activité : ${initialProject}. `:''} {...invalid('message')}/>{fieldError('message')}</label>
    <div className="honeypot" aria-hidden="true"><label>Votre site internet<input name="website" tabIndex={-1} autoComplete="off"/></label></div>
    <p className="privacy-note">Les informations transmises permettent de traiter votre demande et de vous recontacter. Consultez notre <Link href="/confidentialite">politique de confidentialité</Link>.</p>
    {error&&<div className="form-error" role="alert"><p>{error}</p>{Object.entries(fieldErrors).filter(([k])=>!['name','company','email','phone','domain','project_type','budget','deadline','message'].includes(k)).map(([k,v])=><p key={k}>{v}</p>)}</div>}
    <button type="submit" className="button" disabled={busy} aria-busy={busy}>{busy?<><LoaderCircle className="spin" size={18}/>Enregistrement en cours…</>:<>Envoyer ma demande <ArrowRight size={18}/></>}</button>
  </form>;
}
