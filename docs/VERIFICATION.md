# Bilan de vérification — SONUTECH

Date : 30 septembre 2026. Vérification indépendante après implémentation et correction des anomalies trouvées.

## Résultats exécutés

| Vérification | Résultat |
| --- | --- |
| `python manage.py test content inquiries --verbosity 1` | **27 tests réussis**, PostgreSQL réel, aucun test ignoré |
| `python manage.py check` | Aucune erreur |
| `python manage.py makemigrations --check --dry-run` | Aucune modification de modèle sans migration lors du contrôle |
| `python manage.py showmigrations` | Migrations appliquées, y compris `content.0002_sitesettings_about_body_and_more` |
| `npm run lint` | Réussi |
| `npm run typecheck` | Réussi |
| `npm run test:e2e -- --reporter=list` | **10 tests Playwright réussis** en 35 secondes, Chromium, frontend réel + Django réel |

Les tests Python ont été lancés avec `.env.local` chargé depuis la racine, puis `backend/.venv/bin/python backend/manage.py test content inquiries`. Les commandes frontend sont lancées dans `frontend/`. Le projet livré doit être testé avec une base dédiée : les tests navigateur déposent de vraies demandes synthétiques, identifiables par une adresse `e2e-…@example.com`.

## Parcours navigateur

- Toutes les pages principales et toutes les fiches publiées d’expertises, secteurs et formations retournent HTTP 200, avec un H1 unique, un titre SONUTECH et sans erreur JavaScript de page.
- Tous les liens internes découverts dans ces pages ont été suivis par requête HTTP, sans réponse d’erreur. La page inconnue affiche une 404 cohérente.
- Menu mobile : ouverture, navigation, fermeture par Échap et retour du focus vérifiés à 390 × 844. Absence de débordement horizontal vérifiée sur les principales pages mobile et les pages desktop à 1440 × 1000.
- Carrousel : cinq indicateurs, flèches précédent/suivant, parcours de chaque slide, bouclage clavier gauche/droite et préférence de réduction des animations. Le carrousel étant manuel, aucun contrôle de pause n’est nécessaire.
- Catalogue : catégorie CRM, recherche insensible aux accents, état vide et remise à zéro.
- Formulaires contact, devis avec date/budget et demande d’information depuis une fiche formation : réponse réelle HTTP 201, message de réussite accessible et association à la formation consultée.
- Validation HTML des champs requis avant toute requête ; honeypot rejeté par le backend ; erreur réseau accessible sans fausse réussite et sans perte des champs.
- Réponse perdue : le test laisse Django enregistrer réellement la demande, interrompt seulement le retour réseau, puis vérifie qu’une nouvelle tentative utilise la même clé et reçoit HTTP 200 avec la même référence. Aucune réussite n’est simulée.

Une lecture directe PostgreSQL via l’ORM a confirmé les trois types de demandes, leur statut `new`, la relation de formation `crm-relation-client` et leur conservation en `notification_status=failed` lorsque SMTP n’est pas configuré.

## API, sécurité et administration future

Les tests couvrent publication seule en lecture publique, refus d’écriture publique, refus de consultation publique des demandes, validation, antispam, limitation partagée en base, authentification des en-têtes de relais, idempotence simple et quatre soumissions concurrentes PostgreSQL. Ils vérifient également l’échec SMTP et la relance réussie sans second envoi après succès.

Les rôles éditeur, commercial, responsable, utilisateur sans rôle, compte inactif et superutilisateur ont été contrôlés. L’éditeur n’accède pas aux demandes ; le commercial ne modifie pas les contenus ; le responsable ne peut administrer les comptes ou s’élever en superutilisateur. Les actions privées exigent leurs permissions. Les exports CSV neutralisent les cellules pouvant être interprétées comme formules et excluent les notes internes.

Connexion, écriture et déconnexion de session ont été testées avec contrôle CSRF réel. Les origines CORS non autorisées sont refusées. Les réponses privées sont `no-store`. La création d’un utilisateur vérifie le hachage du mot de passe, son absence des réponses et l’absence de ses valeurs dans l’audit. L’audit conserve l’acteur, l’action et les noms de champs ; il n’est pas anonyme, afin d’assurer la traçabilité, mais ne contient pas les messages privés ni les secrets.

Les téléversements anonymes sont refusés ; les SVG sont rejetés ; les images autorisées sont réencodées en JPEG avec un nom généré. Un téléversement authentifié réel a été enregistré puis servi avec un type `image/jpeg` par Django local et la route dynamique `/media/` de Next.js, puis l’optimiseur `/_next/image` (HTTP 200). Le fichier de contrôle a été supprimé ensuite.

Une vérification supplémentaire a créé un contenu temporaire via API privée, testé sa non-publication, sa publication, une modification immédiatement visible sur une nouvelle requête Next.js puis sa dépublication. Le contenu, le compte temporaire et leurs entrées d’audit de test ont été supprimés. Aucun écran CRM n’a été créé.

## Anomalies corrigées et retestées

- Une échéance facultative envoyée comme `null` empêchait les formulaires sans date : le frontend transmet maintenant une chaîne vide.
- Les limites de longueur du formulaire ont été alignées avec les modèles.
- L’origine locale `127.0.0.1` pouvait être refusée par le relais : les origines de développement sont explicitement traitées ; l’origine de production reste configurable.
- Le relais de limitation par adresse client est authentifié et réservé à un proxy de confiance configuré.
- Les erreurs de réseau sont présentées en français.

## Limites et contrôles de livraison

Les essais natifs ci-dessus utilisent PostgreSQL **14.19** sur le port 55432. Ils ont été complétés par les contrôles réels sur PostgreSQL **17** en conteneurs détaillés ci-dessous. Le navigateur intégré n’avait pas d’outil d’exécution disponible dans cette session ; les tests ont donc utilisé Playwright et Chromium installés localement.

La délivrabilité SMTP réelle n’a pas été testée, aucun compte n’ayant été fourni. Le test de panne/reprise utilise un transport simulé côté Python ; l’enregistrement réel sans configuration SMTP a été vérifié séparément. Le reverse proxy HTTPS, la délivrabilité SMTP et la mise en service nécessitent une validation sur l’environnement cible. Les sauvegardes/restaurations ont été exécutées localement, y compris en conteneurs. Les médias de production doivent être servis conformément à `DEPLOIEMENT.md`.

Les résultats du build final, de la comparaison visuelle et du lancement Docker sont consignés ci-dessous par le responsable de livraison ; les tests locaux ne valent pas validation implicite de ces environnements.

## Nettoyage des données de vérification

Les cinq demandes synthétiques créées pendant les essais ont été supprimées après vérification, en ciblant strictement `name="Vérification E2E"`, `email__startswith="e2e-"` et `email__endswith="@example.com"`. Aucune demande métier ni contenu initial n’a été supprimé. La base temporaire des tests Django est détruite automatiquement. Les compteurs de limitation sont conservés et expirent normalement.

Les tests navigateur ne possèdent pas d’accès privé ni de secret de gestion. Pour les rejouer, utiliser une base de vérification dédiée puis supprimer les seuls enregistrements synthétiques avec un opérateur autorisé, ou réinitialiser cette base isolée. Ne pas lancer ces tests sur une base de production.

## Validation Docker et build final

**Gate de livraison : PASS pour le périmètre développé et testé localement.**

- Images Docker frontend et backend construites avec succès. Le build Next.js de production compile les pages, vérifie TypeScript et génère les routes.
- Stack effective : Node.js 22, Python 3.13, PostgreSQL 17 ; ports alternatifs 3001 et 8001 pour préserver les serveurs natifs sur 3000 et 8000. Aucun service n'est publié sur Internet.
- Migrations complètes, commandes `bootstrap_roles`, `seed_content`, contrôle Django et **27 tests backend réussis aussi dans Docker**, en plus de leur passage natif.
- Homepage et contact HTTP 200 ; dépôt réel HTTP 201 puis répétition HTTP 200 avec la même référence. Lecture SQL PostgreSQL 17 : un seul enregistrement, notification en échec conservée lorsque SMTP est absent. Les données de test ont ensuite été retirées.
- URL runtime vérifiée dans robots.txt et sitemap.xml : port 3001 conforme à la configuration, sans URL figée lors du build.
- Médias : proxy natif, lecture du volume Docker et optimisation Next Image HTTP 200. Vérification supplémentaire avec **Django DEBUG=0** : Django répond 404 sur le média comme attendu, tandis que Next.js sert le volume en lecture seule et optimise correctement l'image. Une tentative d'écriture échoue (`EROFS`) ; une traversée de chemin ou un lien symbolique hors racine répond 404.
- Sauvegarde `pg_dump` puis restauration réelle vers une base temporaire, en local et sous PostgreSQL 17 : contenus initiaux retrouvés. Sauvegarde et restauration des médias par archive, comparaison des fichiers identique. Les bases et fichiers temporaires ont été retirés.

## Comparaison visuelle

Inspection des captures complètes à 1280 px, 800 px et 390 px, ainsi que du formulaire mobile. La structure reprend le header fixe, le hero bleu marine à accents turquoise, le bandeau à six expertises, la grille 3 × 2, les étapes, trois secteurs photographiques, le CTA et le footer. Sur mobile, la navigation devient un menu accessible, les cartes d'expertise passent sur deux colonnes et les secteurs sur une colonne. Aucun titre ou bouton n'est coupé. Les couleurs du texte turquoise sur blanc et des champs ont été assombries pour préserver la lisibilité.

Captures livrées dans `docs/screenshots/` : [ordinateur](screenshots/accueil-desktop.png), [tablette](screenshots/accueil-tablette.png), [mobile](screenshots/accueil-mobile.png), [contact mobile](screenshots/contact-mobile.png).

Les photographies et le monogramme provisoire diffèrent des originaux de la maquette : aucun fichier de logo séparé ni photographie originale n'a été fourni. Sources et modalités de remplacement : `VISUELS.md`.

## Informations restant à fournir

- Logo officiel séparé et éventuels visuels propres à SONUTECH.
- Coordonnées publiques, raison sociale, forme juridique, immatriculation, siège, responsable de publication et hébergeur.
- Responsable de traitement et durées de conservation, à intégrer aux textes de confidentialité.
- Paramètres SMTP réels, expéditeur autorisé et destinataire interne.
- Domaine final, infrastructure HTTPS et calendrier/modalités/tarifs des formations à préciser selon l'offre validée.

Les champs non fournis restent configurables. Les pages juridiques signalent leur état préparatoire. Ni certification, financement garanti, référence client ni chiffre de performance n'a été inventé. Aucun écran CRM n'est livré ; les endpoints privés et les permissions préparent son raccordement.

## Gate indépendant final

**PASS — aucun blocage fonctionnel non résolu identifié dans le périmètre livré.** Relecture indépendante du dernier changement média : racine résolue avec `realpath`, refus des chemins et liens sortant de la racine, fichiers réguliers uniquement, limite de 6 Mo, liste fermée d’extensions/types image, `nosniff` et volume partagé monté en lecture seule dans Compose. La provenance des fichiers reste le téléversement contrôlé et réencodé par Django.

Contrôle ciblé en lecture seule sur le build Docker final au port 3001 : accueil, contact, robots et sitemap HTTP 200 ; média inexistant, SVG et traversée encodée HTTP 404. Les preuves de média avec `DEBUG=0`, optimisation, refus d’écriture et tests PostgreSQL 17 consignées par l’agent d’exploitation ont été relues. Les suites complètes déjà réussies n’ont pas été relancées sans nécessité. Ce gate valide la livraison locale ; les informations et configurations de mise en ligne manquantes restent explicitement listées ci-dessus.

## Assistant IA (ajout du 30 septembre 2026)

| Vérification | Résultat |
| --- | --- |
| `python manage.py test content inquiries agent` (natif, PostgreSQL 14.19) | **49 tests réussis**, dont 22 pour l’assistant |
| Même suite dans Docker (Python 3.13, PostgreSQL 17) | **49 tests réussis** |
| `makemigrations --check`, `check`, schéma OpenAPI `--validate` | Conformes ; 8 endpoints ajoutés, aucun endpoint existant modifié |
| `npm run lint`, `npm run typecheck` | Réussis |
| Build Docker backend, agent et frontend | Réussi ; le service `agent` démarre et reste inactif avec `AGENT_ENABLED=0` |

Les tests couvrent : analyse et création de prospect, réutilisation du prospect et historique, validation par lien (lecture sans effet, modification, envoi, lien à usage unique, expiration, entrées invalides), refus et annulation des relances, spam, modes `draft`/`semi`/`auto`, alerte prioritaire jamais envoyée seule, plafond horaire, relances conditionnées à l’envoi effectif et annulées sur demande close, absence de configuration email, demandes anciennes ou déjà prises en charge ignorées, pannes de l’IA avec reprises puis alerte unique, erreur interne sans blocage, résumé quotidien unique, permissions des API par rôle, audit, forme exacte de l’appel à Claude et minimisation des données (ni email ni numéro de téléphone transmis, contenus non publiés exclus), refus du modèle, réponse incomplète, erreurs réseau et clé absente.

Essai réel sur l’environnement de développement : demande de devis déposée par le relais Next.js (HTTP 201), passage de l’agent sans clé API → demande conservée au statut « Nouvelle », échec explicite « Clé API Anthropic absente ». Une analyse simulée a ensuite produit un vrai email de validation (backend console) ; la page de validation a été contrôlée à 390 et 1280 px sans débordement, le texte modifié puis validé dans Chromium, et la réouverture du lien a répondu 404. Données synthétiques et entrées d’audit correspondantes supprimées ensuite.

**Non vérifié** : aucun appel réel à l’API Anthropic (aucune clé fournie), donc ni la qualité des réponses rédigées ni le coût réel ; aucun envoi SMTP réel. À faire après fourniture de la clé : traiter une dizaine de demandes représentatives en mode `draft`, relire chaque brouillon et relever la consommation affichée dans le résumé quotidien.

## Chatbot Groq et CRM — 8 octobre 2026

Validation indépendante : **PASS** pour le déploiement désactivé. Suite complète
Django : 71 tests réussis, puis régression ciblée sur la reprise après plafond
quotidien réussie. Lint, TypeScript, build Next.js et migrations sans dérive.
Chromium : 10 parcours publics, 3 scénarios chatbot simulés, 2 parcours CRM.
Contrôles desktop/mobile, réglages privés, modification/refus des brouillons,
permissions d'envoi, refus SMTP absent et relais HTTP vérifiés.

Déploiement HTTPS contrôlé : voir [HOSTINGER.md](../deploy/HOSTINGER.md).
Aucun appel réel à Groq et aucun email réel envoyé : activation par le responsable
avec sa clé et configuration SMTP nécessaires. Les captures de validation locale
sont dans `.local/chatbot-*.png` ; elles ne sont pas publiées sur le site.

## CRM professionnel React — 8 octobre 2026

**Gate indépendant PASS**, suivi d’un **gate production HTTPS PASS**.

- Django : 82 tests complets réussis, puis 10 tests CRM API ciblés réussis après
  les corrections finales de destinataire et de filtres de dates.
- Playwright : 3 parcours CRM complets et 13 tests site public/chatbot réussis.
- Lint, TypeScript, build Next.js et absence de dérive des migrations vérifiés.
- Parcours réels : prospects, conversion client, Kanban, projets, factures avec
  centimes exacts et montants verrouillés après émission, documents privés,
  destinataire email, agenda Paris, recherche globale et compte lecture seule.
- Visuel : ordinateur 1536 × 1024 et mobile 390 × 844 ; éléments fixes et
  défilement central contrôlés ; captures inspectées indépendamment.
- Production : Docker reconstruits, migrations et routage appliqués ; connexion,
  API privées, rubriques, écriture réelle d’un client temporaire et déconnexion
  vérifiées. Toutes les données temporaires de production ont été supprimées.

Le SMTP et la clé Groq sont absents : aucun envoi ni appel fournisseur réel ne
fait partie de ces validations. Détail : [HOSTINGER.md](../deploy/HOSTINGER.md).
