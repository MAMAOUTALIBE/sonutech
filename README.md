# SONUTECH

Site public français réalisé à partir de la maquette fournie, avec Next.js/React/TypeScript/Tailwind, API Django REST Framework et PostgreSQL. Un CRM professionnel React est accessible sous `/crm/` : tableau de bord, prospects, clients, opportunités Kanban, projets, devis et factures, agenda, e-mails, documents et assistant IA. Aucun Django Admin n’est exposé. Voir [le guide CRM](docs/CRM.md).

## Versions

Les versions exactes des dépendances JavaScript sont verrouillées dans `frontend/package-lock.json` et celles de Python dans `backend/requirements.txt`. Environnement Docker : Node.js 22, Python 3.13 et PostgreSQL 17. Backend : Django 5.2.17 LTS, Django REST Framework 3.16.1, psycopg 3.3.6, SDK Anthropic 1.10.0. Frontend : Next.js 16.3.8, React 19.3.0, Tailwind CSS 4.3.3 et TypeScript 6.0.3. Les vérifications sont réalisées sur PostgreSQL 14.19 en natif et PostgreSQL 17 dans Docker via Colima. Le lancement des conteneurs nécessite un moteur Docker actif.

## Installation Docker

Pré-requis : Docker avec Compose v2, moteur Docker démarré et ports 3000/8000 libres. Depuis la racine :

```sh
cp .env.example .env
chmod 600 .env
# Générer deux valeurs distinctes, puis les reporter dans .env :
python3 -c 'import secrets; print(secrets.token_hex(32))'
python3 -c 'import secrets; print(secrets.token_hex(48))'
```

Renseigner respectivement `POSTGRES_PASSWORD` et `DJANGO_SECRET_KEY`. Le mot de passe PostgreSQL doit être utilisable dans une URL ; les valeurs hexadécimales générées conviennent. Ne jamais ajouter `.env` au dépôt. Les variables vides SMTP sont intentionnelles tant qu’aucun compte n’a été fourni.

```sh
docker compose config --quiet
docker compose build
docker compose up -d db
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py bootstrap_roles
docker compose run --rm backend python manage.py seed_content
docker compose up -d
```

Ouvrir [le site local](http://localhost:3000). L’API locale répond sous [localhost:8000/api/v1/](http://localhost:8000/api/v1/public/). PostgreSQL n’expose aucun port hôte dans Compose. Les données et médias sont persistés dans des volumes nommés. Arrêter avec `docker compose down` **sans `-v`**.

## Premier utilisateur de gestion

Créer le premier compte en terminal interactif. Django demande le nom, l’adresse email et le mot de passe sans l’inscrire dans l’historique shell :

```sh
docker compose exec backend python manage.py createsuperuser
```

Conserver ce compte privilégié pour l’amorçage et le dépannage. Se connecter via l’API de session, puis créer des comptes nominatifs et attribuer les groupes `content_editor`, `sales` ou `manager` selon les fonctions ; ne pas distribuer un compte partagé. Les utilisateurs sans droits n’accèdent pas aux données privées. Voir [authentification et permissions](docs/API.md).

## Notifications SMTP

Configurer dans `.env` : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `DEFAULT_FROM_EMAIL` et `INQUIRY_NOTIFICATION_EMAIL`. Les booléens valent `1` ou `0`. TLS et SSL sont exclusifs : le port 587 utilise généralement TLS, 465 SSL selon le fournisseur. Aucun destinataire, compte ou secret réel n’est livré.

Une demande valide est d’abord enregistrée dans PostgreSQL. Si SMTP échoue ou n’est pas configuré, la demande reste conservée et sa notification peut être relancée :

```sh
docker compose exec backend python manage.py retry_notifications
```

Planifier cette commande selon les besoins et surveiller les erreurs. Exécuter aussi `python manage.py cleanup_rate_buckets` quotidiennement. Une coupure après acceptation SMTP peut provoquer une deuxième notification lors de la reprise ; l’enregistrement de la demande reste idempotent. Le message public confirme l’enregistrement de la demande, pas sa livraison par email.

## Assistant IA

Le chatbot Groq peut répondre aux visiteurs et transmettre leurs demandes au CRM
avec leur accord. L'assistant commercial prépare les brouillons pour les
nouvelles demandes ; chaque envoi exige la validation du responsable. Il faut
configurer la clé Groq dans l'espace privé avant activation. Guide :
[docs/CHATBOT.md](docs/CHATBOT.md). L'ancien service Anthropic reste désactivé.

## Développement et vérifications

```sh
# Backend, avec environnement PostgreSQL et DJANGO_SECRET_KEY configurés
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

Dans un autre terminal :

```sh
cd frontend
npm ci
BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Le frontend accède à Django côté serveur avec `BACKEND_URL`. Cette variable est interne ; `NEXT_PUBLIC_SITE_URL` décrit l’URL publique et Compose la transmet aussi à `SITE_URL` pour les métadonnées calculées côté serveur à l’exécution. Hors Compose, configurer également `SITE_URL`. Les formulaires utilisent un relais serveur, le navigateur n’accède jamais à PostgreSQL. L’état initial provient du backend, pas d’une seconde base éditoriale en frontend.

```sh
cd frontend
npm run typecheck
npm run lint
npm run build
# Avec le frontend et le backend lancés, sur une base de test uniquement :
npx playwright install chromium
npm run test:e2e
```

Le [bilan de vérification](docs/VERIFICATION.md) distingue les contrôles exécutés des limites restantes. Les dossiers `.local`, `.env.local`, `.venv`, `.next` et `node_modules` sont locaux et exclus de Git.

## Architecture et suite CRM

- `frontend/` : pages publiques rendues côté serveur, composants, carrousel, catalogue et formulaires.
- `backend/content/` : contenus, publication, images, paramètres et métadonnées SEO.
- `backend/inquiries/` : demandes, statuts, notes privées et notifications.
- `backend/accounts/` : sessions, rôles, utilisateurs et audit de gestion.
- `backend/agent/` : assistant IA, prospects, brouillons, validations et relances.
- `docs/` : API, exploitation, sources visuelles et bilan.

Le CRM React utilise les API Django `/api/v1/crm/`, les sessions sécurisées et le contrôle CSRF. Il conserve les prospects existants, propose trois rôles d’accès et stocke les documents hors des médias publics. Les devis et factures ont des lignes et totaux calculés côté serveur. Une demande ne crée pas automatiquement de client. Les endpoints privés `/api/v1/manage/` restent disponibles pour les intégrations autorisées.

## À renseigner avant publication

Le fichier de logo officiel séparé, les informations juridiques de l’entreprise, les coordonnées publiques, les réseaux sociaux, le responsable du traitement, la durée de conservation, le compte SMTP et le destinataire interne n’ont pas été fournis. Les paramètres et textes doivent être complétés avant ouverture. Aucun client, témoignage, certification, financement ou résultat chiffré n’a été inventé.

Voir [déploiement, sauvegarde et restauration](docs/DEPLOIEMENT.md), [documentation API](docs/API.md) et [sources des visuels](docs/VISUELS.md). Aucune publication n’est effectuée par cette livraison.

## Aperçus de livraison

Sur ce poste, le site de développement est accessible à http://localhost:3000 et la stack Docker vérifiée à http://localhost:3001 (ports distincts pour éviter un conflit).

Captures : [ordinateur](docs/screenshots/accueil-desktop.png), [tablette](docs/screenshots/accueil-tablette.png), [mobile](docs/screenshots/accueil-mobile.png), [formulaire mobile](docs/screenshots/contact-mobile.png).
