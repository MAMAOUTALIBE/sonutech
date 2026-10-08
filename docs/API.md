# API SONUTECH v1 et raccordement du futur CRM

Le backend Django constitue la source de référence. Le site public et le futur CRM utilisent les API ; aucun navigateur ne se connecte à PostgreSQL. Le CRM et ses écrans ne sont pas inclus dans cette phase.

Base locale : `http://localhost:8000/api/v1/`. Les endpoints des deux premières sections sont relatifs à `/api/v1/public/` ; ceux d’authentification et de gestion sont relatifs à `/api/v1/`. Les endpoints se terminent par `/`. Le schéma OpenAPI `/api/v1/schema/` et sa documentation `/api/v1/docs/` sont réservés aux sessions authentifiées.

## Contenus publics

| Méthode | Endpoint | Réponse |
| --- | --- | --- |
| GET | `services/`, `services/{slug}/` | Expertises publiées |
| GET | `slides/`, `slides/{slug}/` | Slides publiés, ordre, textes, images, CTA |
| GET | `sectors/`, `sectors/{slug}/` | Secteurs publiés |
| GET | `courses/`, `courses/{slug}/` | Formations publiées et programmes |
| GET | `courses/?category=ia` | Filtre de catégorie |
| GET | `settings/` | Coordonnées, textes juridiques, page À propos, méthode et note du hero |

Les ressources non publiées ne figurent pas dans les listes et répondent 404 par leur slug public. Les listes publiques ne sont pas paginées. Les modifications privées doivent être visibles lors d’une nouvelle requête du site, sans nécessiter de reconstruire le frontend.

## Dépôt de demandes

`POST inquiries/` accepte du JSON. Aucune méthode publique ne permet de consulter une demande après son dépôt. Une réponse de dépôt contient seulement un identifiant opaque et `status: received`.

```json
{
  "kind": "contact",
  "name": "Exemple de test",
  "company": "",
  "email": "test@example.com",
  "phone": "",
  "domain": "informatique",
  "message": "Je souhaite discuter d’un projet de site professionnel.",
  "idempotency_key": "fd419ec4-5a80-4550-b272-7519ef00881d",
  "website": ""
}
```

Générer un nouvel UUID avec `crypto.randomUUID()` pour chaque nouvelle demande ; conserver le même UUID pour une nouvelle tentative de la **même** demande. Réponse 201 si créée, 200 si déjà enregistrée avec le même contenu, 409 si la clé est réutilisée avec un contenu différent. Cela empêche les doublons lors des reprises réseau.

`kind` vaut `contact`, `quote` ou `training`. Un devis nécessite `project_type` ; `budget` et `deadline` restent facultatifs. Une demande de formation nécessite `course`, le slug d’une formation publiée. Les domaines sont des slugs d’expertises publiées. Le message doit contenir au moins 10 caractères. Le champ leurre antispam `website` doit rester vide.

Les validations donnent 400 avec des erreurs par champ ; la limite antispam donne 429. Le seuil configurable `INQUIRY_RATE_LIMIT` vaut 10 requêtes/heure par défaut. La clé d’idempotence ne contourne pas la limite. Par défaut, les dépôts passant par Next.js partagent conservativement le quota de son adresse réseau. Une limitation par visiteur exige un ingress qui écrase `X-Real-IP`, `TRUST_PROXY_HEADERS=1` côté Next.js et un `PROXY_SHARED_SECRET` commun (32 caractères minimum) transmis uniquement entre serveurs. Django ignore les en-têtes personnalisés sans secret valide ; `X-Forwarded-For` seul n’est jamais accepté. Voir la procédure de déploiement.

Le dépôt en base précède la notification SMTP. L’échec SMTP ne supprime pas la demande et ne transforme pas un dépôt enregistré en erreur frontend. Aucun consentement marketing obligatoire n’est demandé.

## Authentification de gestion

Authentification par sessions Django et cookie HttpOnly, sans JWT ni stockage de jeton dans `localStorage`. Les cookies sont `Secure` lorsque `DJANGO_DEBUG=0`, et `SameSite=Lax`. Durée maximale configurée : 8 heures, expiration à la fermeture du navigateur.

Flux prévu pour un CRM sur la même origine ou sur une origine HTTPS de confiance appartenant au même site :

1. Appeler `GET auth/csrf/` avec `credentials: 'include'`. Conserver la valeur JSON `csrfToken` en mémoire.
2. Appeler `POST auth/login/` avec le JSON `{ "username": "…", "password": "…" }`, `credentials: 'include'`, `Content-Type: application/json` et `X-CSRFToken`.
3. Après connexion, rappeler `GET auth/csrf/` car Django renouvelle le secret CSRF. Le cookie de session est géré uniquement par le navigateur.
4. Appeler `GET auth/me/` pour identifier l’utilisateur et ses droits.
5. Toute écriture privée (`POST`, `PUT`, `PATCH`, `DELETE`) doit inclure `X-CSRFToken` et les cookies. La vérification CSRF s’applique aussi à la connexion.
6. Fermer la session par `POST auth/logout/`, avec CSRF.

Ajouter l’origine exacte du CRM à `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` ; pas de wildcard. Un CRM hébergé sur un domaine tiers nécessiterait une réévaluation des cookies et du modèle CSRF : privilégier un reverse proxy d’origine commune ou des sous-domaines du même site. Aucune clé API publique ne donne accès à la gestion.

## Gestion privée et permissions

Les endpoints `/manage/services/`, `/manage/slides/`, `/manage/sectors/`, `/manage/courses/`, `/manage/images/` et `/manage/settings/` exposent les contenus selon les permissions du compte. Les identifiants de gestion sont les IDs backend, pas les slugs publics. Les paramètres du site existants se modifient par PUT/PATCH. Les médias utilisent `multipart/form-data` ; champ `file` et texte alternatif `alt`, limite 5 Mo, formats JPEG/PNG/WebP, maximum 20 mégapixels. Les fichiers sont décodés et réencodés en JPEG avec un nom UUID ; SVG et fichiers non image sont refusés. Reporter ensuite le chemin `/media/…` dans le contenu concerné. Les images de contenu sont limitées aux chemins gérés `/images/…` et `/media/…` ; les URL externes sont refusées.

`/manage/inquiries/` permet la consultation et le traitement des demandes avec pagination de 25 résultats. Filtres : `status`, `kind`, `domain`, `search`, `page`. Les mises à jour autorisées portent sur `status` et `internal_notes` ; les champs du dépôt d’origine ne sont pas modifiables par cet endpoint.

- Statuts : `new` (Nouvelle), `in_progress` (En cours), `processed` (Traitée), `archived` (Archivée).
- Export filtré : `GET manage/inquiries/export/`, permission spécifique obligatoire. Les valeurs CSV pouvant être interprétées comme des formules sont neutralisées.
- Relance : `POST manage/inquiries/{id}/retry-notification/`, permission spécifique et CSRF.
- Utilisateurs et groupes : `/manage/users/`, `/manage/groups/`, réservés aux superutilisateurs. Le catalogue `/manage/permissions/` suit cette même restriction.
- Audit : `/manage/audit-logs/`, accès privé selon permissions ; identifiant de ressource, acteur, action et champs modifiés, sans copie du message privé ni secret.

| Groupe | Droits initiaux |
| --- | --- |
| `content_editor` | Lecture et gestion des contenus, images et paramètres |
| `sales` | Consultation/traitement/export des demandes, reprise des notifications, prospects et brouillons de l’assistant IA |
| `manager` | Union des deux groupes et consultation des journaux d’audit |
| Superutilisateur | Tous les droits, dont utilisateurs/groupes/permissions |

Les permissions Django sont vérifiées par modèle et par action (`view`, `add`, `change`, `delete`, export et reprise). `bootstrap_roles` crée les groupes de base. Le superutilisateur initial sert à créer des comptes nominatifs, puis les groupes définissent l’accès effectif. Vérifier le détail de la commande et le schéma avant de raccorder une interface CRM.

## Assistant IA

L’assistant décrit dans [AGENT_IA.md](AGENT_IA.md) enregistre ses résultats dans trois ressources privées, accessibles au groupe `sales` (donc aussi `manager`) :

| Méthode | Endpoint | Rôle |
| --- | --- | --- |
| GET, PATCH | `manage/leads/`, `manage/leads/{id}/` | Prospects. Filtres `stage` (`to_qualify`, `qualified`, `not_retained`), `temperature` (`hot`, `warm`, `cold`), `search`. Modifiables : `name`, `company`, `phone`, `stage`, `internal_notes` |
| GET | `manage/agent-triages/`, `manage/agent-triages/{inquiry_id}/` | Analyse de chaque demande : état, spam, intérêt, résumé, besoins, pré-devis, alerte, modèle et jetons consommés. Filtres `state`, `temperature`, `escalated=true/false` |
| GET, PATCH | `manage/agent-drafts/`, `manage/agent-drafts/{id}/` | Réponses (`sequence` 0) et relances (1, 2…). Filtres `status`, `inquiry`. Seuls `subject` et `body` sont modifiables, tant que le message est `scheduled` ou `pending_approval` |
| POST | `manage/agent-drafts/{id}/approve/` | Valide et envoie ; accepte `subject` et `body` facultatifs. Réponse `{"status": "sent"}` ou `"approved"` si l’envoi sera réessayé |
| POST | `manage/agent-drafts/{id}/reject/` | Refuse et annule les relances suivantes |

Statuts des brouillons : `scheduled` (relance programmée), `pending_approval`, `approved` (envoi en cours), `sent`, `rejected`, `cancelled`. Une décision sur un message déjà traité répond 409. Ces actions exigent la permission `change_emaildraft` et le jeton CSRF, comme les autres écritures. Le jeton de validation envoyé par email n’est jamais exposé par l’API.

La page `GET/POST /api/v1/agent/approval/{jeton}/` sert uniquement au lien reçu par email. Le jeton aléatoire, stocké haché, vaut authentification : il est à usage unique, expire, et la page est servie en `no-store`, `noindex` et sans référent.

Les réponses 403 indiquent une session manquante, un droit insuffisant ou un rejet CSRF ; aucune donnée privée ne doit être affichée en repli public. Ne jamais enregistrer les mots de passe, cookies, messages privés ou secrets SMTP dans les journaux du CRM.
