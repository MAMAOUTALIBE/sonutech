# CRM professionnel SONUTECH

Accès privé : https://sonutech.fr/crm/. Le CRM React utilise l’API Django et la
base PostgreSQL existante. Les comptes, prospects et conversations existants
sont conservés. L’interface et les formulaires sont en français.

## Navigation

Le menu latéral, l’en-tête et le pied de page restent en place ; le contenu
central défile. Sur téléphone, le bouton de menu ouvre la navigation.

- **Tableau de bord** : indicateurs réels, pipeline commercial, activité du jour,
  projets et répartition des services. Une base vide affiche des états de départ,
  sans chiffres de démonstration.
- **Prospects** : coordonnées, qualification et suivi des contacts.
- **Clients** : fiches clients et informations de contact.
- **Opportunités** : pipeline Kanban, montant et avancement commercial.
- **Projets** : client, service, état, budget, progression et échéances.
- **Devis & factures** : lignes, quantités, prix, taxes et totaux calculés par le
  serveur ; numérotation automatique distincte des devis et factures.
- **Agenda** : rendez-vous et tâches de suivi.
- **E-mails** : brouillons commerciaux à relire ; aucun envoi automatique.
- **Documents** : fichiers privés associés aux contacts, clients et projets.
- **Assistant IA** : réglages Groq, test de connexion et préparation de messages.
- **Paramètres** : coordonnées de SONUTECH et comptes de l’équipe.

Les formulaires permettent l’ajout et la modification. Les filtres et la
recherche permettent de retrouver les éléments. Les données de l’équipe sont
partagées au sein de ce CRM SONUTECH.

## Accès et rôles

Les identifiants existants restent valables. Les rôles distinguent la lecture
seule, le travail commercial et la responsabilité de l’équipe. Les contrôles
s’appliquent aussi dans l’API, indépendamment des boutons affichés.

L’envoi commercial conserve une permission d’approbation explicite. La clé Groq
ne revient jamais dans les réponses de l’API. Les sessions utilisent les cookies
sécurisés en production, avec contrôle CSRF sur les modifications.

## Services externes

L’agenda est interne au CRM : aucune synchronisation de calendrier externe n’est
configurée. Le module e-mails gère les brouillons et leur envoi validé, sans
prétendre synchroniser une boîte de réception.

Groq nécessite une clé enregistrée et testée dans l’assistant. Les envois exigent
la configuration SMTP du serveur. Voir [CHATBOT.md](CHATBOT.md).

## Exploitation

Les documents sont stockés dans `/opt/sonutech/var/private/documents`, en dehors
des médias publics. Leur téléchargement passe par l’API authentifiée. Sauvegarder
ce répertoire séparément de la base et protéger les sauvegardes.

Nginx dirige le nouveau CRM React vers Next.js et `/api/v1/` vers Django.
Les routes historiques de connexion et de validation des brouillons restent
accessibles pour compatibilité. Les pages et API privées utilisent `no-store`
et `noindex`. Voir [HOSTINGER.md](../deploy/HOSTINGER.md) pour le déploiement et
[CRM_API.md](CRM_API.md) pour le contrat de l’API.
