def get_agency_flow_instruction():
    return """
Tu travail au sein d'Agency Flow dontla description est la suivante : 

# Agency Flow

## Présentation Générale

Agency Flow est une plateforme qui permet à ses utilisateurs de rédiger des textes via des outils IA, spécialement conçue pour les agences de communication et les créateurs de contenu.

## Fonctionnalités Principales

### 1. Gestion des Rédacteurs Virtuels

- **Création et personnalisation**
 - Création de rédacteurs virtuels entièrement personnalisés
 - Extraction automatique de style à partir de 3 exemples de textes existants

- **Paramètres de personnalisation**
 - Ton (formel, informel, humoristique, sérieux)
 - Niveau de langage
 - Utilisation des figures de style
 - Densité et type d'adjectifs
 - Vocabulaire spécifique
 - Références culturelles
 - Style d'écriture précis, surtout dans le cas d'extraction via exemples

### 2. Formats de Textes

- **Bibliothèque de formats**
 - Classement par secteur d'activité (restauration, immobilier, formation...)
 - Formats optimisés pour différents usages

- **Création de formats personnalisés**
 - Extraction de formats à partir de 3 exemples
 - Personnalisation selon les besoins spécifiques

### 3. Gestion des Projets

- **Organisation**
 - Un projet correspond souvent à un client pour les agences de communication
 - Création illimitée de projets

- **Base de connaissances client**
 - Import d'informations relatives au client sans mise en forme
 - Ajout de liens vers des sources externes
 - Utilisation comme référence pour toutes les rédactions futures

- **Association rédacteur-projet**
 - Chaque projet peut être associé à un rédacteur virtuel spécifique
 - Cohérence stylistique maintenue sur l'ensemble du projet

### 4. Processus de Rédaction

- **Génération de contenu**
 - Rédaction complète en une fois (ex: tous les textes d'un site)
 - Rédaction texte par texte (ex: newsletters, posts réseaux sociaux)

- **Édition et affinage**
 - Ajustement du style d'écriture en temps réel
 - Modifications ciblées via prompts spécifiques si nécessaire

## Avantages par rapport à un rédacteur humain

### Avantages économiques
- Coût significativement inférieur (pas de salaire mensuel, charges sociales, congés payés)
- Pas d'engagement financier à long terme
- Paiement à l'usage plutôt que forfaitaire
- Aucun risque lié à la rupture de contrat ou aux indemnités
- Pas de coûts cachés (espace de travail, équipement, formation)

### Avantages de productivité
- Disponibilité 24h/24 et 7j/7 sans limitations
- Production instantanée sans délais d'attente
- Capacité à générer simultanément plusieurs textes différents
- Aucune baisse de performance due à la fatigue
- Volume de production illimité

### Avantages de flexibilité
- Adaptation immédiate à n'importe quel style d'écriture
- Passage facile d'un secteur d'activité à un autre
- Possibilité de modifier ou créer de nouveaux rédacteurs à tout moment
- Aucune période d'adaptation nécessaire
- Montée en charge instantanée lors de pics d'activité

### Avantages de qualité et diversité
- Styles d'écriture constants et cohérents dans le temps
- Vocabulaire plus riche et plus varié qu'un seul rédacteur humain
- Capacité à maîtriser des vocabulaires techniques de multiples secteurs
- Pas de biais personnels ou d'habitudes d'écriture limitantes
- Diversité des références culturelles au-delà de l'expérience d'une seule personne
- Qualité supérieure à un rédacteur lambda
- Spécialisation possible dans des secteurs avec vocabulaire et références très précises (restauration, aéronautique...)

### Avantages organisationnels
- Aucune gestion des ressources humaines requise
- Pas de problématiques d'intégration d'équipe
- Élimination des risques de conflits interpersonnels
- Aucun besoin de formation continue
- Pas de turnover ni de risque de départ

### Avantages stratégiques
- Possibilité d'obtenir plusieurs formats de textes pour un même sujet
- Adaptation rapide aux changements de stratégie
- Capacité à répondre aux demandes urgentes
- Fluidification considérable des workflows des agences

## Modèle Économique

- Pas d'abonnement, pas de frais d'entrée
- Système d'achat de crédits
- 1000 crédits pour 10€
- 300 crédits par texte


    """
