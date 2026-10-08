# Assistant IA — traitement des demandes en votre absence

> Ce document décrit l'ancien service Anthropic, maintenu désactivé en production.
> Le chatbot et l'assistant commercial actuels utilisent Groq, avec validation
> humaine obligatoire avant envoi : voir [docs/CHATBOT.md](CHATBOT.md).

L'assistant prend en charge chaque demande déposée sur le site (contact, devis, formation) : il l'analyse, crée ou met à jour la fiche du prospect, rédige une réponse et deux relances, puis vous en rend compte. Il fonctionne dans le backend Django, sous la forme d'un service séparé (`agent`), avec le modèle Claude Opus 5.5 d'Anthropic.

Il est **désactivé par défaut**. L'API Anthropic est un service payant : rien n'est consommé tant que `AGENT_ENABLED=1` et une clé ne sont pas configurés.

## Ce qu'il fait pour chaque demande

1. **Analyse** : repère les spams, résume la demande, liste les besoins, estime l'intérêt (chaud, tiède, froid, note sur 100) et conseille une prochaine étape.
2. **Prospect** : crée une fiche « À qualifier », ou met à jour celle du même email. Aucun prospect n'est transformé en client automatiquement.
3. **Réponse** : rédige un email personnalisé à partir des seuls contenus publiés sur le site et des règles de l'entreprise, sans prix, délai ni engagement.
4. **Pré-devis** : pour une demande de devis, prépare pour vous une reformulation, un découpage en phases et les questions à poser. Ce texte reste interne.
5. **Relances** : prépare deux relances, à J+3 puis J+7 après l'envoi effectif de la réponse.
6. **Alertes** : une demande urgente, importante, une réclamation ou une demande hors champ est marquée « prioritaire » et n'est jamais envoyée sans vous.
7. **Résumé quotidien** : chaque matin, un email récapitule les demandes, les envois et ce qui attend votre validation.

L'IA rédige ; c'est le code qui décide. Elle ne peut ni envoyer un email, ni choisir un destinataire, ni modifier le site : elle ne produit que du texte, puis les règles ci-dessous s'appliquent.

## Les trois modes (`AGENT_MODE`)

| Mode | Envoyé sans vous | Soumis à votre validation |
| --- | --- | --- |
| `draft` (par défaut) | Rien | Toutes les réponses et relances |
| `semi` | Contacts et demandes de formation | Devis et demandes prioritaires |
| `auto` | Tout le reste | Demandes prioritaires uniquement |

Dans tous les modes, les spams ne reçoivent rien, les demandes prioritaires attendent votre validation et les envois automatiques sont plafonnés (`AGENT_MAX_AUTO_SENDS_PER_HOUR`, 20 par défaut ; au-delà, validation requise). Commencez en `draft` quelques semaines, puis passez en `semi` lorsque les réponses vous conviennent.

## Mise en route

1. **Emails** : configurer SMTP comme indiqué dans le README (`SMTP_*`, `DEFAULT_FROM_EMAIL`). Sans SMTP, l'assistant prépare les brouillons mais ne peut ni vous prévenir ni envoyer.
2. **Clé Anthropic** : créer une clé sur [platform.claude.com](https://platform.claude.com) et la placer dans `.env` (`ANTHROPIC_API_KEY`). Ne jamais la mettre dans le code ni dans une variable `NEXT_PUBLIC_*`.
3. **Réglages** dans `.env` :

   ```sh
   AGENT_ENABLED=1
   AGENT_MODE=draft
   AGENT_OWNER_EMAIL=vous@votre-domaine.fr
   # En production : l'URL HTTPS du site ; nginx relaie /api/v1/ vers Django.
   AGENT_PUBLIC_BASE_URL=https://votre-domaine.fr
   ```

4. **Démarrer** : `docker compose run --rm backend python manage.py migrate`, puis `docker compose up -d agent`. Après toute modification de `.env` : `docker compose up -d --force-recreate agent`.
5. **Tester** : déposer une demande sur le site. Dans la minute, vous recevez « Réponse à valider » avec un lien. `docker compose logs -f agent` affiche l'activité.

Hors Docker, lancer `python manage.py run_agent` en service permanent (un passage toutes les 30 secondes), ou `python manage.py run_agent --once` depuis une tâche planifiée chaque minute.

## Vos règles

Le fichier [`backend/agent/regles.md`](../backend/agent/regles.md) fixe le ton, ce que l'assistant peut dire, ce qu'il ne doit jamais dire, la grille tarifaire éventuelle et les cas d'alerte. Réglages par défaut : vouvoiement, signature « L'équipe SONUTECH » (`AGENT_SIGNATURE`), aucun prix ni délai. Le fichier est intégré à l'image Docker : après modification, lancer `docker compose build agent && docker compose up -d agent`.

## Valider une réponse

L'email « Réponse à valider » indique le prospect, le type de demande et l'intérêt estimé, sans reprendre le message. Le lien ouvre une page qui affiche la demande complète, l'analyse, le pré-devis et le brouillon **modifiable**, avec deux boutons : **Envoyer ce message** ou **Refuser**. Refuser annule aussi les relances prévues.

Le lien est personnel, à usage unique et expire après 7 jours (`AGENT_APPROVAL_TTL_HOURS`). Ne le transférez pas : il donne accès à la demande. Après expiration, le brouillon reste consultable et validable par l'API de gestion. La réponse part depuis `DEFAULT_FROM_EMAIL`, avec votre adresse en « répondre à » : le prospect vous répond directement.

## Relances : ce que vous devez faire

L'assistant ne lit pas votre boîte mail. Lorsqu'un prospect vous répond, passez la demande en « Traitée » (`/manage/inquiries/`) ou le prospect en « Qualifié » ou « Non retenu » (`/manage/leads/`) : les relances en attente sont alors annulées. Elles le sont aussi si vous refusez la réponse ou la relance précédente.

## Données transmises à Anthropic

Pour chaque demande sont transmis : nom, entreprise, type, domaine, formation, type de projet, budget, échéance, message, ainsi que la date, le type et le statut des demandes précédentes de la même adresse. L'**email et le numéro de téléphone ne sont pas transmis** (seulement le fait qu'un téléphone a été indiqué). Le catalogue publié et `regles.md` accompagnent la demande.

La politique de confidentialité par défaut mentionne ce traitement. Avant activation, vérifiez-la avec la personne responsable du traitement : base légale, durée de conservation, transfert hors Union européenne et conditions du prestataire.

**Limite des modes automatiques** : une personne peut saisir l'adresse d'un tiers dans le formulaire. En `semi` ou `auto`, ce tiers recevrait alors une réponse de SONUTECH. Le plafond horaire limite ce risque, que le mode `draft` supprime.

## Coût

Claude Opus 5.5 est facturé 4 $ par million de jetons en entrée et 20 $ par million en sortie. Une demande représente un seul appel, estimé entre 0,05 et 0,10 $, soit environ 5 à 10 $ pour 100 demandes. Cette estimation n'a pas encore été mesurée sur de vrais appels. La consommation réelle figure dans le résumé quotidien et dans les champs `input_tokens` et `output_tokens` de `/manage/agent-triages/`.

## Pannes et reprises

- Si l'IA est indisponible, la demande reste enregistrée. L'assistant réessaie deux fois à 10 minutes d'intervalle, puis vous envoie « Demande à traiter vous-même ».
- Seules les demandes au statut « Nouvelle » de moins de 3 jours sont traitées (`AGENT_MAX_AGE_DAYS`) : activer l'assistant ne répond pas à l'historique.
- Un email refusé par le serveur SMTP est réessayé jusqu'à 5 fois ; les échecs persistants apparaissent dans le résumé quotidien.
- Chaque action (analyse, demande de validation, validation, refus, envoi, annulation) est inscrite dans le journal d'audit. Les actions de l'assistant ont un acteur vide ; les validations via l'API portent le nom de l'utilisateur.

## Réglages

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | vide | Clé API, secret serveur |
| `AGENT_ENABLED` | `0` | Active le service |
| `AGENT_MODE` | `draft` | `draft`, `semi` ou `auto` |
| `AGENT_OWNER_EMAIL` | `INQUIRY_NOTIFICATION_EMAIL` | Destinataire des validations, alertes et résumés |
| `AGENT_SIGNATURE` | `L’équipe SONUTECH` | Ajoutée à chaque email |
| `AGENT_PUBLIC_BASE_URL` | `http://localhost:8000` | Base des liens de validation |
| `AGENT_FOLLOWUP_DAYS` | `3,7` | Délais des relances après la réponse |
| `AGENT_DIGEST_HOUR` | `8` | Heure du résumé quotidien (Europe/Paris) |
| `AGENT_MAX_AUTO_SENDS_PER_HOUR` | `20` | Plafond des envois automatiques |
| `AGENT_APPROVAL_TTL_HOURS` | `168` | Validité des liens |
| `AGENT_MAX_AGE_DAYS` | `3` | Âge maximal d'une demande traitée |
| `AGENT_MODEL` | `claude-opus-5-5` | Modèle Claude |
| `AGENT_EFFORT` | `medium` | Niveau de réflexion du modèle |

En développement, `DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` affiche les emails dans les journaux au lieu de les envoyer.

## Raccordement au futur CRM

Le CRM pourra afficher les prospects, les analyses et les brouillons, et valider ou refuser depuis son interface avec les endpoints `/api/v1/manage/leads/`, `/agent-triages/` et `/agent-drafts/` décrits dans [API.md](API.md). Le lien reçu par email et l'API agissent sur les mêmes brouillons : une décision prise d'un côté invalide l'autre.
