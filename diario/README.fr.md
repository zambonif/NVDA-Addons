# Journal pour NVDA

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Français](README.fr.md)

Version 1.4.2

## Nouveautés de la version 1.4.2

Si le mot de passe actuel est refusé lors de la modification du mot de passe ou de la récupération, le message identifie désormais le mot de passe actuel sans mentionner une phrase de récupération incorrecte. Le message est traduit dans toutes les langues du module.

Les tests de régression couvrent des mots de passe allant jusqu’à 4 096 caractères, avec de la ponctuation et de l’Unicode. L’utilisateur ayant signalé le problème a confirmé que le module mis à jour fonctionne avec son mot de passe de 128 caractères et que le message trompeur n’apparaît plus. La phrase de récupération reste facultative.


Journal pour NVDA est un journal personnel accessible et hors ligne, intégré au lecteur d'écran NVDA. Sa combinaison distinctive réunit des entrées datées, l'enregistrement automatique de leur création, un coffre-fort chiffré protégé par mot de passe, une récupération facultative et une correction orthographique accessible en temps réel.

## Fonctions principales

- Créer, répertorier, lire, modifier et supprimer des entrées.
- Choisir la date de chaque entrée tout en conservant la date et l'heure originales de création.
- Protéger titres, dates et texte dans un coffre-fort avec chiffrement authentifié AES-256-GCM.
- Changer le mot de passe et définir facultativement une phrase de récupération.
- Entendre un avertissement après un mot potentiellement incorrect sans perdre l'espace, la ponctuation ou le saut de ligne saisi.
- Ouvrir les suggestions par clic droit, Applications, Maj+F10 ou Alt+F10.
- Remplacer le mot, l'ignorer pendant la session NVDA actuelle ou l'ajouter au dictionnaire local du Journal.
- Exporter les deux fichiers chiffrés du coffre-fort dans un ZIP et importer uniquement les entrées qui n'existent pas encore dans le Journal ouvert.
- Utiliser l'interface et la documentation en portugais brésilien, anglais, espagnol, italien ou français.
- Conserver toutes les données sur l'ordinateur ; le module complémentaire n'envoie pas les entrées sur Internet.

## Configuration requise

- NVDA 2025.1 ou version ultérieure.
- Windows 8 ou version ultérieure pour l'API native de correction orthographique. Les versions actuelles de NVDA exigent une version plus récente et prise en charge de Windows.
- Un dictionnaire orthographique Windows pour la langue choisie dans le Journal. S'il est absent, le Journal continue à fonctionner normalement ; seule la correction orthographique est désactivée pour cette langue.

## Installation et ouverture

Installez `diario-1.4.2.nvda-addon` en ouvrant directement le paquet et confirmez l'installation. Redémarrez NVDA lorsque cela est demandé.

Ouvrez le Journal depuis menu NVDA > Outils > Journal ou appuyez sur NVDA+Alt+D. Le geste peut être modifié dans Gestes de commandes, catégorie Journal.

## Correction orthographique

Les champs du titre et du texte sont vérifiés pendant la saisie. Après un mot suivi d'une espace, d'un signe de ponctuation, de Tab ou d'Entrée, un avertissement retentit si Windows le considère incorrect. Le séparateur est toujours inséré : vous pouvez donc ignorer l'avertissement et continuer à écrire.

Placez le curseur sur le mot ou juste après, puis appuyez sur Applications, Maj+F10 ou Alt+F10. Un clic droit sur le mot fonctionne également. Le menu accessible présente jusqu'à huit suggestions de Windows, puis :

- **Ignorer pour cette session :** interrompt les avertissements pour ce mot jusqu'au redémarrage de NVDA.
- **Ajouter au dictionnaire local :** enregistre le mot dans `dicionario.txt`, dans le dossier de données du Journal, et évite les avertissements futurs.

Le dictionnaire local est un fichier texte UTF-8 qui contient uniquement les mots ajoutés par l'utilisateur. Il n'est pas chiffré, car il ne contient aucune entrée du journal. Le même fichier est partagé par les cinq langues de l'interface.

## Exportation et importation de la sauvegarde chiffrée

Les boutons **Exporter la sauvegarde** et **Importer une sauvegarde** sont disponibles uniquement après le déverrouillage du Journal.

**Exporter la sauvegarde** ouvre une boîte de dialogue pour choisir l'emplacement et crée un ZIP contenant exactement `diario.enc` et `diario.backup.enc`. Les deux fichiers restent chiffrés ; aucun titre, aucune date ni aucun texte d'entrée n'est écrit en clair.

**Importer une sauvegarde** ouvre une boîte de dialogue de sélection, valide les deux copies chiffrées dans un emplacement temporaire et ajoute uniquement les entrées dont l'identifiant n'existe pas encore dans le Journal actuel. Les entrées existantes ne sont jamais remplacées, même si une entrée importée portant le même identifiant contient un texte différent. Les dates, titres, textes et heures de création des nouvelles entrées sont conservés.

Une sauvegarde exportée depuis le même coffre-fort s'ouvre avec la clé déjà conservée par le Journal déverrouillé et ne demande aucun autre mot de passe. Une sauvegarde provenant d'un coffre-fort créé séparément possède une autre clé aléatoire, même si le texte du mot de passe est identique ; dans ce seul cas, le module demande le mot de passe de cette sauvegarde. Cela ne modifie pas le mot de passe du Journal actuel. Après la fusion, les nouvelles entrées sont protégées par le coffre-fort actuel.

Si le ZIP est invalide, si le mot de passe est incorrect, si l'opération est annulée ou s'il ne contient aucune nouvelle entrée, le Journal actuel reste inchangé.

## Données, confidentialité et récupération

Les données sont stockées sous le dossier de configuration de NVDA, dans le sous-dossier `diario`. Le coffre-fort principal est `diario.enc` et sa sauvegarde chiffrée est `diario.backup.enc`.

Tout le contenu, y compris les titres et les dates, est protégé par un chiffrement authentifié AES-256-GCM via Windows CNG. La clé du coffre-fort est protégée à partir du mot de passe avec PBKDF2-HMAC-SHA256 et 600 000 itérations. Lorsqu'elle est configurée, la phrase de récupération protège séparément la même clé aléatoire.

La phrase de récupération ne révèle pas l'ancien mot de passe ; elle permet seulement d'en créer un nouveau. Si le mot de passe et la phrase sont oubliés, le module ne peut pas récupérer les entrées. Utilisez des secrets longs et difficiles à deviner et conservez des copies indépendantes des fichiers chiffrés.

La version 1.3.0 conserve un format de coffre-fort compatible avec la version 1.1.0.

## Langue de l'interface

Ouvrez menu NVDA > Préférences > Paramètres > Journal pour choisir Português (Brasil), Español, Italiano, Français ou English sans changer la langue générale de NVDA. Les nouvelles fenêtres appliquent immédiatement le choix. Redémarrez NVDA pour actualiser également l'élément Outils, la catégorie et la description du geste.

## Construction et tests

Le dépôt utilise uniquement la bibliothèque standard de Python :

```text
python build.py
python -m unittest discover -s tests -v
```

La construction lit la version dans `manifest.ini` et crée `dist/diario-<version>.nvda-addon`, sans inclure tests, caches ni fichiers de développement dans le paquet installable. L'intégration native doit être testée une dernière fois sous Windows avec NVDA avant publication dans l'Add-on Store.

Utilisez `python build.py --source` pour créer également le ZIP du code source et les sommes de contrôle.

## Licence et auteur

Copyright © Fernando de Paula Zamboni.

Licence GNU General Public License, version 2 ou ultérieure. Consultez [LICENSE.txt](LICENSE.txt).
