# Déploiement SONUTECH sur le VPS Hostinger

VPS : `195.35.25.236` (alias SSH local `gandal-vps`). Installation : `/opt/sonutech`.
Le Compose de production est indépendant du Compose de développement.

## Commandes d'exploitation

```sh
cd /opt/sonutech
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs --tail 100
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

Les secrets sont générés sur le VPS dans `.env.production` (mode 600).
Le frontend écoute uniquement sur `127.0.0.1:3400`, Django sur
`127.0.0.1:8400`. PostgreSQL est privé au réseau Docker et utilise le volume
`sonutech_postgres_data`. Les médias et fichiers statiques sont dans `var/`.
Nginx sur l'hôte sert le domaine et les médias. Les autres sites du VPS conservent
leurs configurations et ports.

## Raccordement du domaine

Dans la zone DNS Hostinger, remplacer l'adresse de l'enregistrement A de `@`
par `195.35.25.236`. Le CNAME `www` pointe déjà vers `sonutech.fr`.
Ne pas modifier les enregistrements de messagerie. Le domaine n'avait aucun
AAAA lors de la préparation ; ne pas ajouter une adresse IPv6 non configurée.

Après propagation DNS :

```sh
cd /opt/sonutech
sh deploy/activate-https.sh
```

Le script utilise le compte Let's Encrypt existant sur le VPS, émet le certificat,
vérifie Nginx avant de le recharger et installe un hook de renouvellement.
La configuration HTTP initiale ne sert que les challenges de certificat ; les
autres requêtes reçoivent 503 jusqu'à l'activation HTTPS.

## Données et limites

Seul le contenu éditorial local est transféré, sans comptes, demandes de test,
prospects ni clés de développement. Les groupes de gestion sont créés.
Créer un compte nominatif si nécessaire via `manage.py createsuperuser` en
terminal interactif. L'assistant IA reste désactivé. SMTP n'est pas configuré :
les demandes sont conservées en base mais les notifications email ne partent pas.
Compléter les coordonnées et textes juridiques avec les données de l'entreprise.

Sauvegarder PostgreSQL, `var/media` et les secrets avant toute mise à jour ;
ne jamais supprimer le volume de production avec `down -v`.

```sh
cd /opt/sonutech
umask 077
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose --env-file .env.production -f compose.production.yaml exec -T db \
  pg_dump -U sonutech -d sonutech -Fc > "backups/database-$stamp.dump"
tar -czf "backups/media-$stamp.tar.gz" -C var media
```

Conserver une copie chiffrée hors VPS et vérifier sa restauration.

## Validation du 8 octobre 2026

Gate serveur : **PASS**. Gate publication HTTPS : **PASS**.

- `manage.py test content inquiries accounts agent --noinput` : 49 tests réussis.
- `npm run lint` et `npm run typecheck` : réussis.
- Construction Docker frontend/backend sur le VPS : réussie.
- `npm audit --omit=dev` : aucune vulnérabilité signalée pour les dépendances de production.
- Compose valide ; migrations appliquées ; PostgreSQL sain ; API et frontend démarrés.
- 22 routes publiques testées sur les ports internes du VPS : HTTP 200.
- Sitemap : URL canonique `https://sonutech.fr`, aucune URL localhost.
- Accès non authentifié aux demandes privées et origine de formulaire étrangère : refusés.
- Dépôt réel par le relais frontend : 201, rejeu idempotent : 200 avec le même identifiant.
  L'unique demande synthétique créée a ensuite été supprimée.
- `manage.py check --deploy` : seul avertissement W008, redirection HTTPS prévue
  au niveau Nginx dans la configuration finale, conformément au déploiement existant.
- Configuration Nginx HTTP : syntaxe validée et rechargement réussi.

Le DNS pointe maintenant vers `195.35.25.236`. Le certificat Let's Encrypt couvre
`sonutech.fr` et `www.sonutech.fr`, avec expiration le 6 janvier 2027 et
renouvellement automatique activé. Nginx sert désormais la configuration HTTPS.
Le test `certbot renew --cert-name sonutech.fr --dry-run` a réussi.
Les redirections HTTP et www vers `https://sonutech.fr` sont vérifiées (301).
Les 22 routes publiques et 15 ressources de l'accueil répondent en HTTPS (200).
Le formulaire a été vérifié sur l'URL publique : création 201, rejeu 200,
accès privés et origine étrangère refusés. La demande synthétique a été supprimée.
Aucune validation visuelle par navigateur n'a été exécutée pour cette
modification d'infrastructure.

## Ajout du CRM

Le CRM privé sous `/crm/` est servi par Django ; les pages publiques restent
servies par Next.js. Guide d'utilisation et création de comptes :
[docs/CRM.md](../docs/CRM.md).

Avant cette évolution, une sauvegarde PostgreSQL, une archive du code backend,
une copie de Nginx et l'image Docker précédente ont été conservées avec le suffixe
`20261008T030629Z` dans `backups/` et sous le tag Docker
`sonutech-backend:pre-crm-20261008T030629Z`.

Validation avant déploiement : 60 tests Django réussis ; parcours Chromium
complets en 1440 et 390 pixels ; activation et non-réutilisation du lien
vérifiées ; lint, TypeScript et cohérence des migrations validés. Les pages
privées utilisent `no-store`, `noindex`, des sessions et le contrôle CSRF.

Gate production CRM : **PASS**. Migrations appliquées, fichiers statiques servis,
connexion et déconnexion HTTPS vérifiées avec un compte de test temporaire,
cookies Secure contrôlés, création réelle d'un prospect et rejet d'une requête
sans CSRF vérifiés. Le compte et le prospect de test ont été supprimés.
L'accueil, la page Contact et l'API publique répondent toujours en HTTP 200.
Le premier accès commercial utilise `sonutech@sonutech.fr` ; son lien personnel
d'activation n'est pas conservé dans la documentation.

## Chatbot Groq et brouillons commerciaux — 8 octobre 2026

Déployés sur le même VPS : widget public, configuration privée `/crm/assistant/`,
brouillons `/crm/brouillons/` et service Compose `assistant`. La clé se configure
uniquement dans le CRM ; procédure : [docs/CHATBOT.md](../docs/CHATBOT.md).
Le responsable dispose des permissions de configuration et d'approbation.
L'ancien agent Anthropic reste désactivé.

Sauvegarde avant migration : `backups/pre-chatbot-20261008T040048Z.dump`,
archive `backups/pre-chatbot-source-20261008T040048Z.tar.gz` et images backend /
frontend sous le tag `pre-chatbot-20261008T040048Z`.

Gate de déploiement : **PASS**. Builds Docker, migrations et statiques appliqués ;
quatre services démarrés, PostgreSQL sain. Accueil, contact et confidentialité
répondent en HTTPS. Connexion et pages privées assistant / brouillons contrôlées
avec un compte temporaire ensuite supprimé, ainsi que sa session. Clé non
réaffichée, permissions du responsable et `no-store` vérifiés. Relais public :
503 attendu sans configuration, origine étrangère et accès backend direct 403.

Au déploiement, la configuration reste désactivée : aucune clé Groq fournie et
aucun SMTP configuré. Aucun appel Groq réel ni envoi commercial réel validé.

## CRM professionnel React — 8 octobre 2026

Gate de livraison et production : **PASS**. Le nouveau CRM React est servi sous
`/crm` et `/crm/*` par Next.js ; l’API privée `/api/v1/crm/` reste servie par
Django. Les exceptions Nginx préservent les anciens liens de connexion,
d’activation, de configuration IA et de validation des brouillons. `/crm/`
redirige une fois vers `/crm`, sans boucle. Les API et pages privées utilisent
`no-store` et `noindex`.

Migrations appliquées : `agent.0003`, `crm.0002` et `crm.0003`. Les modèles
existants ont été conservés. Le compte responsable `sonutech@sonutech.fr` reçoit
le groupe manager, sans changement de mot de passe ni retrait de ses permissions
IA. Les documents restent dans `var/private/documents` (répertoire 700), monté
uniquement sur le backend et servi par téléchargement authentifié.

Sauvegardes : base et source `pre-crm-pro-20261008T040826Z`, configuration Nginx
`pre-crm-pro-nginx-20261008T040826Z.conf`, images backend/frontend sous le tag
`pre-crm-pro-20261008T040826Z`. Une sauvegarde immédiate de la base et du répertoire
privé précède aussi les migrations. Les archives sont dans `backups/`, en mode
600. Pour revenir à l’interface précédente, restaurer les images et le routage
Nginx précédents ; conserver les migrations additives et les données créées.

Contrôle HTTPS réel : connexion React, onze collections API privées, dix
rubriques CRM, création/modification/suppression d’un client temporaire,
déconnexion, affichage mobile et absence d’erreurs JavaScript validés. Captures
production inspectées dans `.local/crm-pro/production-{desktop,mobile}.png`.
Compte temporaire, sessions et données de contrôle supprimés. Accueil, contact
et logo public répondent en HTTP 200 ; quatre services actifs, PostgreSQL sain.

La clé Groq et le SMTP restent à configurer. Aucun appel IA réel ni email envoyé
pendant cette livraison. Guide utilisateur : [CRM.md](../docs/CRM.md).
