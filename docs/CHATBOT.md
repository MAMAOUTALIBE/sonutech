# Assistant commercial Groq

Le chatbot public et les brouillons du CRM utilisent Groq, avec le modèle
`openai/gpt-oss-120b`. Le fournisseur est appelé uniquement par Django.
Références vérifiées le 8 octobre 2026 : [modèle](https://console.groq.com/docs/model/openai/gpt-oss-120b),
[API](https://console.groq.com/docs/api-reference) et
[réponses structurées](https://console.groq.com/docs/structured-outputs).

## Activation par le responsable

1. Ouvrir `https://sonutech.fr/crm/assistant-ia/` avec le compte responsable.
2. Saisir la clé API Groq et enregistrer. Une clé laissée vide conserve la clé
   existante ; celle-ci n'est jamais réaffichée.
3. Cliquer sur **Tester la connexion**. Ce test effectue un appel réel à Groq.
4. Activer le chatbot et enregistrer. Le plafond initial est de 100 appels IA
   par jour, partagé entre les conversations, les tests et les brouillons.

La configuration reste désactivée sans intervention du responsable. Les tests
automatisés utilisent des réponses simulées et ne prouvent pas la validité
d'une clé réelle ni la qualité des réponses du compte Groq choisi.

## Parcours visiteur et CRM

Le visiteur ouvre l'assistant et accepte le traitement de ses messages par
Groq avant de commencer. L'IA utilise les informations publiques du site et
les consignes commerciales du responsable. Elle ne peut consulter les autres
prospects, envoyer des emails ni réserver un rendez-vous.

Le formulaire **Être recontacté** demande un accord explicite. Il enregistre la
demande, retrouve ou crée la fiche prospect, conserve le contexte de l'échange
et crée une action de suivi. Les demandes répétées d'une même conversation ne
créent pas plusieurs fiches. Les notes et étapes définies par une personne ne
sont pas remplacées par le chatbot.

Le service `assistant` examine les nouvelles demandes du site et du chatbot
chaque minute après activation. Il prépare les brouillons sans envoyer de
message. Les anciennes demandes antérieures à l'activation ne sont pas
traitées automatiquement. Depuis une fiche prospect, **Préparer un message IA**
permet aussi de produire un brouillon à la demande.

Les brouillons sont accessibles depuis **E-mails** dans le CRM professionnel. Le
responsable peut les modifier, refuser ou valider leur envoi. Sans SMTP configuré,
ils restent consultables mais ne peuvent pas être envoyés. Un envoi dont le
résultat est incertain n'est jamais retenté automatiquement.

## Exploitation et protections

- Clé dans `/opt/sonutech/var/private/groq.json`, fichier mode 600, répertoire
  privé non servi par Nginx ; montage en lecture seule pour le worker.
- Permissions du responsable : `chatbot.change_assistantconfiguration` et
  `chatbot.approve_outreachdraft`. Les comptes commerciaux ordinaires peuvent
  préparer et relire des brouillons, sans accéder à la clé ni approuver l'envoi.
- Le navigateur appelle `/api/chat`. Ce relais contrôle l'origine et appelle
  uniquement l'endpoint interne fixé, avec le secret de relais existant.
- Une conversation est identifiée par un jeton aléatoire, conservé seulement en
  mémoire du navigateur et haché en base. Sa validité est limitée à 24 heures.
  Cette expiration n'est pas une suppression automatique des enregistrements.
- Les messages ont des limites de taille, de fréquence et de nombre de tours.
  Un identifiant de message évite de doubler un appel déjà réussi lors d'une reprise.
- Les pannes et quotas produisent un message d'indisponibilité et un accès au
  formulaire de contact ; aucune réponse IA de substitution n'est fabriquée.
- Les requêtes qui échouent chez le fournisseur sont comptées dans le plafond.
  L'épuisement du plafond ne consomme pas les tentatives de reprise du worker.
- L'ancien service Anthropic `agent` reste désactivé (`AGENT_ENABLED=0`).

```sh
cd /opt/sonutech
docker compose --env-file .env.production -f compose.production.yaml logs --tail 50 assistant
docker compose --env-file .env.production -f compose.production.yaml stop assistant
```

Pour arrêter aussi les réponses aux visiteurs, désactiver le chatbot dans ses
réglages CRM. Les demandes et brouillons déjà enregistrés restent accessibles.
Les sauvegardes de la base ne contiennent pas la clé Groq : conserver les secrets
séparément dans un stockage protégé.
