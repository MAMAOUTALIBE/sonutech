'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { MessageCircle, Send, X } from 'lucide-react';
import styles from './chatbot.module.css';

type ChatMessage = { id: string; role: 'assistant' | 'user'; text: string };
type PendingMessage = { id: string; text: string };
type Contact = { name: string; email: string; phone: string; company: string; message: string; consent: boolean };
type Reply = { available?: boolean; token?: string; reply?: string; captured?: boolean; detail?: string; suggest_contact?: boolean };
const emptyContact: Contact = { name: '', email: '', phone: '', company: '', message: '', consent: false };

export function Chatbot() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [expired, setExpired] = useState(false);
  const [pending, setPending] = useState<PendingMessage | null>(null);
  const [showContact, setShowContact] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [contact, setContact] = useState<Contact>(emptyContact);
  const dialog = useRef<HTMLDialogElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inFlight = useRef(false);
  const contactAttempt = useRef<{ id: string; payload: string } | null>(null);

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else if (dialog.current?.open) dialog.current.close();
  }, [open]);
  useEffect(() => { if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight; }, [messages, busy]);

  function close() { setOpen(false); launcher.current?.focus(); }
  function reset() {
    if (inFlight.current) return;
    setToken(''); setMessages([]); setError(''); setExpired(false); setPending(null); setInput('');
    setShowContact(false); setCaptured(false); setContact(emptyContact); contactAttempt.current = null;
  }
  async function request(payload: Record<string, unknown>): Promise<Reply | null> {
    if (inFlight.current) return null;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.timeout(40000) });
      const result: Reply = await response.json();
      if (!response.ok) { if (response.status === 401) setExpired(true); throw new Error(result.detail || 'La demande n’a pas pu aboutir.'); }
      return result;
    } catch (cause) {
      setError(cause instanceof Error && cause.name !== 'TimeoutError' && cause.name !== 'TypeError' ? cause.message : 'La connexion a été interrompue. Vous pouvez réessayer.');
      return null;
    } finally { inFlight.current = false; setBusy(false); }
  }
  async function start() {
    const result = await request({ action: 'start' });
    if (result?.available && result.token && result.reply) {
      setToken(result.token); setMessages([{ id: 'welcome', role: 'assistant', text: result.reply }]);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    } else if (result) setError('Assistant indisponible pour le moment. Contactez directement notre équipe.');
  }
  async function send(text = input, retry?: PendingMessage) {
    if (inFlight.current || !token || expired || (!retry && pending) || !text.trim()) return;
    const attempt = retry || { id: crypto.randomUUID(), text: text.trim() };
    if (!retry) { setMessages(previous => [...previous, { id: attempt.id, role: 'user', text: attempt.text }]); setInput(''); }
    setPending(attempt);
    const result = await request({ action: 'message', token, message_id: attempt.id, message: attempt.text });
    if (result?.reply) { setMessages(previous => [...previous, { id: `${attempt.id}-reply`, role: 'assistant', text: result.reply! }]); setPending(null); }
    else if (result) setError('La réponse n’est pas arrivée. Réessayez votre message.');
  }
  async function submitContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || captured || expired) return;
    if (!contact.email.trim() && !contact.phone.trim()) { setError('Indiquez un email ou un téléphone pour être recontacté.'); return; }
    const payload = JSON.stringify(contact);
    if (!contactAttempt.current || contactAttempt.current.payload !== payload) contactAttempt.current = { id: crypto.randomUUID(), payload };
    const result = await request({ action: 'contact', token, contact_id: contactAttempt.current.id, ...contact });
    if (result?.captured) { setCaptured(true); setContact(emptyContact); setShowContact(false); }
  }
  return <>
    <button ref={launcher} type="button" className={styles.launcher} onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open} aria-controls="sonutech-chat"><MessageCircle size={23} aria-hidden="true"/><span>Parlons de votre projet<small>Assistant IA SONUTECH</small></span></button>
    <dialog ref={dialog} id="sonutech-chat" className={styles.dialog} aria-labelledby="sonutech-chat-title" onCancel={event => { event.preventDefault(); close(); }} onClose={() => { setOpen(false); launcher.current?.focus(); }}>
      <header className={styles.header}><div className={styles.avatar} aria-hidden="true"><MessageCircle size={23}/></div><div><h2 id="sonutech-chat-title">Assistant IA SONUTECH</h2><p>Construisons votre prochain projet.</p></div><button type="button" onClick={close} aria-label="Fermer la discussion" className={styles.close}><X size={22}/></button></header>
      {!token ? <div className={styles.welcome}><span className={styles.eyebrow}>UNE IDÉE ? UN BESOIN ?</span><h3>Faisons le premier pas.</h3><p>Découvrez nos expertises et précisez votre projet avec notre assistant d’intelligence artificielle.</p><div className={styles.notice}><strong>Avant de commencer</strong><p>Vos messages seront transmis à Groq pour générer les réponses. Évitez les données sensibles ou confidentielles. L’IA peut se tromper : l’équipe confirme les devis et disponibilités.</p><a href="/confidentialite">Comment vos données sont utilisées</a></div><button type="button" className={styles.primary} onClick={start} disabled={busy}>{busy ? 'Connexion…' : 'Accepter et discuter'}</button><a className={styles.direct} href="/contact">Contacter directement l’équipe</a></div> : <>
        <div ref={transcript} className={styles.transcript} role="log" aria-label="Messages de la discussion" aria-live="polite" aria-relevant="additions text">{messages.map(message => <div key={message.id} className={`${styles.message} ${message.role === 'user' ? styles.user : styles.assistant}`}><span className={styles.speaker}>{message.role === 'user' ? 'Vous' : 'Assistant IA'}</span><p>{message.text}</p></div>)}{busy && !showContact && <p className={styles.loading} role="status">L’assistant prépare sa réponse…</p>}</div>
        {messages.length === 1 && !showContact && <div className={styles.suggestions}>{['Quels sont vos services ?', 'Je souhaite créer un site web'].map(text => <button type="button" key={text} onClick={() => send(text)} disabled={busy || !!pending || expired}>{text}</button>)}</div>}
        {captured && <p className={styles.success} role="status">Votre demande a été transmise à l’équipe. Un rendez-vous sera confirmé avec vous ; aucun créneau n’est réservé automatiquement.</p>}
        {showContact ? <form className={styles.contact} onSubmit={submitContact}><div className={styles.contactHeading}><h3>Être recontacté</h3><button type="button" className={styles.linkButton} onClick={() => { setShowContact(false); setError(''); }} disabled={busy}>Retour à la discussion</button></div><p>Vos coordonnées et le contexte de cet échange seront transmis à l’équipe SONUTECH.</p><div className={styles.contactGrid}><label>Votre nom *<input name="name" autoComplete="name" required maxLength={150} value={contact.name} onChange={event => setContact({ ...contact, name: event.target.value })}/></label><label>Entreprise<input name="company" autoComplete="organization" maxLength={180} value={contact.company} onChange={event => setContact({ ...contact, company: event.target.value })}/></label><label>Email<input name="email" type="email" autoComplete="email" maxLength={254} value={contact.email} onChange={event => setContact({ ...contact, email: event.target.value })}/></label><label>Téléphone<input name="phone" type="tel" autoComplete="tel" maxLength={40} value={contact.phone} onChange={event => setContact({ ...contact, phone: event.target.value })}/></label></div><p className={styles.hint}>Un email ou un téléphone est nécessaire.</p><label>Votre demande *<textarea name="message" required rows={2} maxLength={2000} placeholder="Votre besoin, vos disponibilités si vous souhaitez un appel…" value={contact.message} onChange={event => setContact({ ...contact, message: event.target.value })}/></label><label className={styles.consent}><input type="checkbox" required checked={contact.consent} onChange={event => setContact({ ...contact, consent: event.target.checked })}/><span>J’accepte que SONUTECH utilise mes coordonnées et cet échange pour me recontacter au sujet de ma demande.</span></label><button className={styles.primary} type="submit" disabled={busy || expired}>{busy ? 'Transmission…' : 'Transmettre ma demande'}</button></form> : <div className={styles.composer}><div className={styles.actions}>{!captured && <button type="button" className={styles.linkButton} disabled={busy || expired} onClick={() => { setShowContact(true); setError(''); }}>Être recontacté</button>}<button type="button" className={styles.linkButton} disabled={busy} onClick={reset}>Nouvelle discussion</button></div><form onSubmit={event => { event.preventDefault(); void send(); }}><label className={styles.srOnly} htmlFor="chat-message">Votre message</label><textarea ref={inputRef} id="chat-message" value={input} maxLength={2000} rows={2} placeholder="Parlez-nous de votre projet…" disabled={busy || !!pending || expired} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }}/><button className={styles.send} type="submit" aria-label="Envoyer le message" disabled={busy || !!pending || expired || !input.trim()}><Send size={19}/></button></form><p className={styles.hint}>Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne</p>{pending && !expired && <button type="button" className={styles.linkButton} onClick={() => send(pending.text, pending)} disabled={busy}>Réessayer ce message</button>}</div>}
      </>}
      {error && <div className={styles.error} role="alert"><p>{error}</p>{expired && <button type="button" onClick={reset} disabled={busy}>Recommencer la discussion</button>}<a href="/contact">Contacter l’équipe</a></div>}
      <footer className={styles.footer}><a href="/confidentialite">Confidentialité</a><span>IA · Réponses à confirmer avec notre équipe</span></footer>
    </dialog>
  </>;
}
