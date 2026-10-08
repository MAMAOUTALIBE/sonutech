# Exploitation et déploiement

Le projet livré est local. Aucun site ni service payant n’a été publié. Docker Compose est une base de lancement local, pas un dispositif complet de production.

## Avant ouverture au public

1. Renseigner les mentions légales, le responsable du traitement, la durée de conservation, les coordonnées et les destinataires de demandes dans les paramètres du backend. Faire valider ces textes selon la situation réelle de SONUTECH.
2. Fournir le logo officiel séparé et vérifier les visuels et leurs textes alternatifs.
3. Définir `DJANGO_DEBUG=0`, une clé secrète forte, les domaines exacts des hosts/CORS/CSRF et l’URL publique HTTPS. Aucun secret ne doit avoir un préfixe `NEXT_PUBLIC_`.
4. Placer un reverse proxy HTTPS devant Next.js et Django. Restreindre PostgreSQL au réseau privé. Adapter les en-têtes proxy Django uniquement à un proxy de confiance ; ne pas faire confiance aux en-têtes envoyés librement par les visiteurs.
5. Servir `/media/` et `/static/` depuis les volumes correspondants avec un serveur de fichiers : ni listing de répertoire, ni exécution de scripts, types MIME contrôlés et `X-Content-Type-Options: nosniff`. En mode production Django ne sert pas automatiquement les médias.
6. Configurer SMTP, le destinataire interne et un expéditeur autorisé. Vérifier délivrabilité et reprise des notifications échouées.
7. Effectuer les migrations, charger les contenus initiaux, créer le premier utilisateur de gestion. Les interfaces du CRM et Django Admin ne sont pas exposées.
8. Exécuter les contrôles Django de déploiement, les tests, le build et des essais manuels des formulaires. Planifier sauvegardes et tests de restauration.

Les contenus publics sont lus côté serveur depuis Django. Un changement de publication dans le backend doit être contrôlé sur une nouvelle navigation et dans le sitemap. Les données commerciales et demandes ne transitent jamais par les endpoints publics de lecture.

## Assistant IA

Le service Compose `agent` utilise l’image du backend et exécute `python manage.py run_agent`. Il ne publie aucun port et reste inactif tant que `AGENT_ENABLED=1` n’est pas défini. Avant de l’activer en production :

1. Fournir `ANTHROPIC_API_KEY` par le gestionnaire de secrets ou `.env`, jamais dans une variable `NEXT_PUBLIC_*`.
2. Configurer SMTP et `AGENT_OWNER_EMAIL` ; définir `AGENT_PUBLIC_BASE_URL` sur l’URL HTTPS publique (le template nginx relaie `/api/v1/` vers Django, ce qui rend les liens de validation accessibles).
3. Compléter la politique de confidentialité : transmission à Anthropic, transfert hors Union européenne, conservation.
4. Démarrer en `AGENT_MODE=draft`, surveiller `docker compose logs agent` et le résumé quotidien, puis élargir le mode si les réponses conviennent.

Arrêt immédiat : `AGENT_ENABLED=0` puis `docker compose up -d --force-recreate agent`, ou `docker compose stop agent`. Les demandes continuent d’être enregistrées. Détails : [AGENT_IA.md](AGENT_IA.md).

## Sauvegarde PostgreSQL et médias

Exécuter depuis la racine avec le fichier `.env` en place. Les sauvegardes contiennent des données personnelles : limiter les droits, chiffrer hors machine et définir une durée de conservation. Suspendre les écritures pendant une sauvegarde nécessitant une cohérence stricte entre base et médias.

```sh
mkdir -p backups
chmod 700 backups
docker compose exec -T db pg_dump -U sonutech -d sonutech -Fc > backups/sonutech.dump
docker compose exec -T backend tar -C /app/media -czf - . > backups/media.tar.gz
chmod 600 backups/sonutech.dump backups/media.tar.gz
```

Conserver les deux fichiers ensemble, accompagnés de la version du code. Sauvegarder séparément les secrets dans un coffre, jamais dans Git. Automatiser avec des noms horodatés pour éviter d’écraser une copie précédente et contrôler le code de retour.

## Restauration

Cette opération remplace les données de la base cible. S’assurer d’être sur la bonne machine, sauvegarder l’état actuel puis arrêter le frontend et le backend. Restaurer d’abord sur une instance isolée avant une reprise réelle.

```sh
docker compose stop frontend backend agent
docker compose exec -T db pg_restore -U sonutech -d sonutech --clean --if-exists --no-owner < backups/sonutech.dump
# Le service arrêté conserve l'accès au volume grâce à un conteneur temporaire.
docker compose run --rm --no-deps -T --entrypoint sh backend -c 'mkdir -p /app/media && tar -C /app/media -xzf -' < backups/media.tar.gz
docker compose run --rm backend python manage.py migrate
docker compose up -d backend frontend agent
```

L’extraction remplace les fichiers portant le même nom, mais ne supprime pas les médias ajoutés depuis la sauvegarde. Pour une restauration exacte, utiliser un volume média neuf, conserver l’ancien pour retour arrière, puis extraire la sauvegarde dans le nouveau volume. Vérifier connexions de gestion, contenu publié, images et enregistrement d’une demande. Ne jamais utiliser `docker compose down -v` comme commande d’arrêt courant : elle détruit les volumes.

## Développement local sans Docker

Un PostgreSQL 14.19 isolé a été créé pour les vérifications de livraison lorsque le moteur Docker n’était pas accessible : port `55432`, base `sonutech`, fichiers `.local/postgres`, identifiants `.env.local`. Ces fichiers sont exclus de Git. Ils ne constituent pas la configuration portable Docker du projet.

```sh
# macOS/Homebrew, uniquement pour cette instance locale
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D .local/postgres status
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D .local/postgres stop -m fast
# Pour redémarrer :
/opt/homebrew/opt/postgresql@14/bin/pg_ctl -D .local/postgres -l .local/logs/postgres.log -o '-p 55432 -h 127.0.0.1 -k /tmp' start
```

## Adresse du visiteur et limitation des demandes

Le relais Next.js ignore les en-têtes d’adresse IP du navigateur par défaut (`TRUST_PROXY_HEADERS=0`). Django regroupe alors les dépôts par l’adresse du relais : la limite locale conservatrice de 10 demandes/heure peut donc être partagée par plusieurs visiteurs. Ce mode protège le dépôt sans prétendre identifier chaque visiteur derrière un proxy.

Pour une production avec limitation par adresse du visiteur :

1. Générer `PROXY_SHARED_SECRET` avec `python3 -c 'import secrets; print(secrets.token_hex(32))'` et le fournir à Next.js et Django via le gestionnaire de secrets ou `.env`. Minimum 32 caractères, jamais `NEXT_PUBLIC_*`.
2. Placer Next.js derrière un unique ingress de confiance qui **écrase** `X-Real-IP` avec l’adresse du pair (`$remote_addr` dans nginx), supprime les valeurs de forwarding reçues du visiteur et interdit l’accès public direct aux ports applicatifs.
3. Activer `TRUST_PROXY_HEADERS=1` uniquement dans cet environnement. Le relais transmet alors une IP normalisée et le secret sous deux en-têtes privés. Django ne les accepte qu’avec une comparaison du secret en temps constant ; sinon il conserve `REMOTE_ADDR`. La limitation des connexions de gestion conserve `REMOTE_ADDR` et peut donc rester partagée derrière un proxy.
4. Tester qu’un visiteur ne peut pas modifier son quota en envoyant ses propres `X-Real-IP`, `X-Forwarded-For` ou `X-Sonutech-*`.

Le [template nginx](../deploy/nginx.conf.example) illustre cette entrée : il n’est pas activé automatiquement. Remplacer le domaine réservé `.example`, fournir les certificats HTTPS, placer nginx sur le réseau Compose et monter les volumes médias/static en lecture seule aux chemins indiqués. Si un CDN précède nginx, configurer séparément les seules plages réseau autorisées à fournir l’adresse réelle ; ne pas activer globalement la confiance dans un en-tête.

La redirection HTTPS de ce template est réalisée par nginx. Conserver `SECURE_SSL_REDIRECT=0` derrière ce template tant que Django ne dispose pas d’une configuration explicite et sécurisée de son proxy TLS, sinon une boucle de redirection peut survenir. Conserver `DJANGO_DEBUG=0` et les cookies Secure en production. Exécuter `python manage.py collectstatic --noinput` dans le backend pour remplir le volume static. Django ne fournit plus ces routes lorsque DEBUG vaut 0. Compose monte donc aussi `media_data:/app/media:ro` dans Next.js et fixe `MEDIA_ROOT=/app/media` : la route média et l’optimisation Next Image lisent les fichiers partagés en lecture seule, y compris lorsqu’une requête d’optimisation ne traverse pas nginx. Le serveur nginx peut continuer à servir les médias directement. Hors Docker, donner à Next un `MEDIA_ROOT` absolu accessible en lecture, ou prévoir un service média interne disponible en production ; le relais Django de développement seul ne suffit pas lorsque DEBUG vaut 0.

Planifier quotidiennement `python manage.py cleanup_rate_buckets` pour retirer les compteurs expirés. La notification SMTP est une livraison au moins une fois : une interruption après acceptation SMTP mais avant confirmation en base peut entraîner un second email lors d’une reprise. La demande en base reste unique grâce à sa clé d’idempotence.

## URL publique et métadonnées Next.js

Configurer `NEXT_PUBLIC_SITE_URL` dans `.env` avec l’URL HTTPS finale. Compose transmet aussi cette valeur à `SITE_URL`, variable serveur lue à l’exécution pour les URL canoniques, le sitemap, robots.txt et le contrôle d’origine des formulaires. Cela évite de figer `localhost` dans ces réponses lors de la construction de l’image. Hors Compose, fournir explicitement `SITE_URL` au processus Next.js.

## Particularité du poste de vérification Docker

Le moteur a été lancé via la VM Colima existante. Le gestionnaire `docker-credential-desktop` référencé par la configuration globale était absent ; les vérifications utilisent donc une configuration Docker isolée dans `.local/docker-config`, sans modifier le fichier global de secrets. Sur ce poste uniquement, préfixer les commandes Docker si nécessaire :

```sh
export DOCKER_CONFIG="$PWD/.local/docker-config"
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
```

L’override local `.local/compose.validation.yaml` utilise 3001/8001 pour les conteneurs afin de préserver les serveurs natifs 3000/8000. Ces fichiers exclus de Git ne sont pas nécessaires à une nouvelle installation avec Docker opérationnel.
