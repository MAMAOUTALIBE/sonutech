# Identité et visuels

La maquette jointe sert de référence de composition, couleurs, sections et hiérarchie. Elle n'est jamais utilisée comme image de fond de la page.

## Logo

Aucun fichier de logo original n'était présent dans les pièces accessibles (seul le cahier des charges texte était joint sur disque). `frontend/public/images/logo.svg` est un monogramme ST provisoire, reconstruit pour l'intégration. Remplacer ce fichier par le logo approuvé avant publication. Le logo est un composant indépendant : `frontend/src/components/logo.tsx`.

## Photographies d'illustration

Photographies téléchargées localement depuis Unsplash le 30 septembre 2026, sous [licence Unsplash](https://unsplash.com/license), qui autorise l'utilisation commerciale. Les personnes illustrées ne sont pas présentées comme des salariés, clients ou partenaires de SONUTECH. Pas de téléchargement depuis une recherche d'images sans vérification de licence.

| Asset local | Source exacte |
| --- | --- |
| `hero.jpg` | https://images.unsplash.com/photo-1600880292203-757bb62b4baf |
| `entreprises.jpg` | https://images.unsplash.com/photo-1521737711867-e3b97375f902 |
| `hotellerie.jpg` | https://images.unsplash.com/photo-1517248135467-4c7edcad34c4 |
| `formations.jpg` | https://images.unsplash.com/photo-1524178232363-1fb2b075b655 |
| `energie.jpg` | https://images.unsplash.com/photo-1508514177221-188b1cf16e9d |

Résolution source : 1800 px pour le hero, 1000 px pour les autres. Le composant Next Image réserve les dimensions et sert des variantes optimisées. Les images hors hero sont chargées paresseusement. Aucun appel Unsplash n'est nécessaire dans le navigateur : les fichiers sont inclus au projet. Les photos diffèrent de celles de la maquette, dont les originaux et droits d'usage n'ont pas été fournis.

## Icônes

[Lucide](https://lucide.dev/license), licence ISC. Les SVG sont rendus par `lucide-react`, sans service tiers. Police système Arial/Helvetica : aucun appel à Google Fonts ou service de suivi.
