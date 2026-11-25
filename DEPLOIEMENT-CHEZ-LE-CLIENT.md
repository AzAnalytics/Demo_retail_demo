# Faire tourner Le Cockpit sur un poste chez le client

Le cas de Salaisons Cros : la base Oracle est dans leurs locaux, le pilote et
la connexion existent déjà sur un poste, et tu y accèdes à distance. Le
tableau de bord tourne donc **là-bas**, et les dirigeants l'ouvrent dans leur
navigateur depuis le réseau de l'entreprise.

C'est le déploiement le plus simple à faire accepter par une PME, pour une
raison qu'il faut dire en rendez-vous : **les données ne sortent jamais de
chez eux**.

---

## 1. Ce qu'il faut sur le poste

- **Python 3.11 ou plus récent** (python.org, case « Add to PATH » cochée).
- Les dépendances : `pip install -r requirements.txt`, plus `pyodbc` pour la
  connexion ODBC existante (ou `oracledb` pour se passer de l'instant client).
- Le **pilote Oracle** déjà installé, puisque la connexion Excel fonctionne.
- Un poste qui **reste allumé**. C'est la vraie contrainte : un portable qu'on
  emporte le soir ne convient pas.

## 2. Les réglages, dans un fichier `.env` à côté du code

```
COCKPIT_SOURCE=odbc
COCKPIT_DB_CHAINE=DRIVER={Oracle in instantclient_19_5x64};SERVER=...;UID=...;PWD=...
COCKPIT_SOURCE_REQUETE=SELECT ...
COCKPIT_ACCESS_PASSWORD=un-mot-de-passe-choisi-avec-le-dirigeant
COCKPIT_DEMO_AUTO=0
COCKPIT_TAUX_TVA=0
```

`COCKPIT_DEMO_AUTO=0` est **obligatoire** chez un client : on ne régénère
jamais les données de quelqu'un. `COCKPIT_TAUX_TVA=0` si l'ERP renvoie déjà
des montants hors taxes, ce qui est le cas général en B2B.

Ce fichier contient un mot de passe de base de données : il reste sur le poste
du client, il n'est pas versionné, et il ne part pas par mail.

## 3. Le verrou d'accès

Dès que `COCKPIT_ACCESS_PASSWORD` est renseigné, le Cockpit demande un mot de
passe avant d'afficher le moindre chiffre (`acces.py`, testé dans
`test_acces.py`). Sans cela, n'importe qui sur le réseau de l'entreprise voit
les marges par client.

À dire clairement au dirigeant : ce verrou tient les curieux à l'écart, il ne
remplace pas la sécurité du réseau. **Le Cockpit ne doit jamais être exposé sur
internet** depuis ce poste.

## 3 bis. Donner à chacun son périmètre (l'équivalent du RLS)

Le dirigeant voit tout, le responsable de Toulouse voit Toulouse, le
commercial voit ses clients. Chacun ouvre la même adresse.

Copier `profils.example.json` en `profils.json` (jamais versionné), puis
fabriquer les empreintes :

```
python permissions.py "le mot de passe de cette personne"
```

Un profil sans `magasins`, `categories` ni `clients` voit tout. Les
restrictions se cumulent : `"magasins": ["Toulouse"], "categories": ["Textile"]`
donne le textile de Toulouse, rien d'autre.

### Les rôles : ce que chacun a le droit de FAIRE

Le périmètre dit ce qu'on voit, le rôle dit ce qu'on peut faire. Les deux se
combinent : un contributeur restreint à Toulouse exporte Toulouse, et rien
d'autre.

| Rôle | Ouvrir | Exporter | Régler objectif et seuil | État technique | Gérer les comptes |
|---|:--:|:--:|:--:|:--:|:--:|
| `lecteur` | oui | non | non | non | non |
| `contributeur` | oui | oui | oui | non | non |
| `admin` | oui | oui | oui | oui | oui |

Chaque droit correspond à une action réelle de l'écran, pas à une étiquette :
le bouton d'export n'existe pas pour un lecteur, les curseurs de réglage non
plus, et les panneaux « État technique » et « Comptes et périmètres »
n'apparaissent que pour un administrateur. Comme l'écran est calculé sur le
serveur, ne pas afficher une action, c'est ne pas l'offrir.

Un rôle inconnu dans `profils.json` est refusé au chargement, et n'autorise
rien : une faute de frappe ne peut pas ouvrir des droits par accident.

Un bouton **Se déconnecter** est affiché à droite du nom, sous le bandeau. Sur
un poste partagé dans un magasin ou un atelier, pouvoir sortir compte autant
que pouvoir entrer : le suivant retrouve l'écran de connexion, vide.

Le panneau d'administration permet aussi de fabriquer l'empreinte d'un mot de
passe sans ligne de commande, pour créer un compte depuis l'écran. Les comptes
eux-mêmes se modifient dans `profils.json` : l'écran ne réécrit jamais ce
fichier, pour qu'une fausse manoeuvre ne puisse enfermer personne dehors.

Trois niveaux de protection, à ne pas confondre quand on en parle à un client :

| Niveau | Ce que c'est | Où c'est fait |
|---|---|---|
| Cacher des graphiques | **pas** de la sécurité : les données sont chargées | à proscrire |
| Filtrer dans l'application | les lignes hors périmètre sont retirées dès la lecture, avant tout calcul et avant la prévision | `permissions.applique`, en place |
| Filtrer dans la base | les lignes interdites ne sortent jamais du serveur | `permissions.filtre_sql`, à coller dans la requête |

C'est exactement le fonctionnement du RLS de Power BI : la restriction est
appliquée par l'outil qui sert les données, pas par l'écran. Le troisième
niveau va plus loin que Power BI, et se décide avec l'informatique du client.

Deux tests garantissent la promesse : la clause SQL et le filtre Python donnent
le même résultat, et un profil connecté à l'écran ne voit pas le chiffre
d'affaires des autres (`test_permissions.py`).

Ce que ce dispositif ne fait pas : il ne remplace pas une vraie identité
d'entreprise. Si le client tient à ce que chacun se connecte avec son compte
Microsoft, Streamlit sait le faire (`st.login`, OpenID Connect avec Entra ID),
et les profils deviennent alors une simple table de correspondance entre une
adresse professionnelle et un périmètre.

## 4. Démarrer, et redémarrer tout seul

Lancer une fois à la main pour vérifier :

```
demarrer_cockpit.bat
```

Puis ouvrir `http://localhost:8501` sur le poste. Depuis un autre poste du
réseau : `http://nom-du-poste:8501`.

**Ouvrir le port** (une fois, en administrateur) :

```
netsh advfirewall firewall add rule name="Le Cockpit" dir=in action=allow protocol=TCP localport=8501
```

**Redémarrage automatique** au démarrage de Windows, avec le planificateur de
tâches (en administrateur, le mot de passe du compte est demandé par Windows,
c'est à l'informatique du client de le saisir) :

```
schtasks /create /tn "Le Cockpit" /tr "\"C:\cockpit\demarrer_cockpit.bat\"" /sc onstart /ru NOM_DU_COMPTE /rp * /rl highest /f
```

Dans les propriétés de la tâche, cocher « Exécuter même si l'utilisateur n'est
pas connecté », et dans l'onglet Paramètres, « Redémarrer la tâche toutes les
5 minutes en cas d'échec ». Un poste Windows redémarre tout seul pour les mises
à jour : sans cette tâche, le tableau de bord disparaît un matin sans prévenir,
et c'est le client qui s'en aperçoit.

## 4 bis. La voie Docker, quand l'informatique la connaît

Si le prestataire informatique du client utilise déjà Docker, c'est la voie la
plus propre : pas de Python à installer, pas de conflit de versions, et une
mise à jour qui tient en une commande.

Sur le serveur, dans le dossier du projet :

```bash
docker compose up -d --build
```

L'écran est alors sur `http://<nom-du-serveur>:8501`, **depuis le réseau
interne uniquement**. On n'ouvre jamais ce port vers Internet : si le client
veut y accéder de chez lui, cela passe par son VPN.

Ce qu'il faut savoir avant de s'en servir :

- **Les comptes ne sont pas dans l'image.** Ils vivent dans `config/profils.json`,
  monté en lecture seule. Changer un mot de passe ne demande donc aucune
  reconstruction, et une image envoyée par erreur ne contient aucun accès client.
- **Les versions sont figées** dans `requirements.txt`. Une reconstruction dans
  six mois installera exactement le logiciel testé aujourd'hui.
- **L'application ne tourne pas en root**, et Docker surveille sa santé toutes
  les trente secondes : si elle ne répond plus, le conteneur redémarre seul.
- **`restart: unless-stopped`** la relance après un redémarrage du serveur.

Pour livrer une nouvelle version : `git pull` puis `docker compose up -d --build`.
Quelques secondes d'interruption, pas davantage.

Pour vérifier que tout va bien, sans ouvrir de navigateur :

```bash
docker compose ps        # la colonne STATUS doit afficher (healthy)
docker compose logs -f   # ce que raconte l'application
```

## 5. Vérifier que ça tient

- Les journaux : `logs\cockpit-AAAA-MM-JJ.log`, un fichier par jour.
- Après un redémarrage du poste, rouvrir la page : elle doit répondre sans
  intervention.
- La fraîcheur des chiffres : le Cockpit relit la base une fois par heure
  (cache). Si le dirigeant veut voir une vente du matin, c'est le bon moment
  pour en parler : une lecture plus fréquente se règle, mais elle tape sur leur
  base de production.

## 6. Les livrer, les mettre à jour

Pour une mise à jour, il suffit de remplacer les fichiers `.py` et de relancer
la tâche. Garder la même structure de dossier (`C:\cockpit` par exemple), et ne
jamais écraser le `.env` du client.

Avant chaque livraison, lancer les tests sur ta machine :

```
python -m pytest -q
```

## 7. Ce qu'il faut annoncer au client, et ne pas promettre

- Le tableau de bord dépend d'un poste qui doit rester allumé et connecté à la
  base. Si le poste est éteint, l'écran ne répond plus. Ce n'est pas une panne
  du Cockpit.
- Une mise à jour de l'ERP peut renommer une colonne : le Cockpit affiche alors
  un message au lieu d'un chiffre faux, et il faut reprendre la requête. Prévoir
  cette ligne dans l'offre de suivi.
- Tu n'es pas l'informatique du client : l'ouverture du port, le compte de
  service et le mot de passe du poste sont de leur côté.
- Ce que tu garantis, toi : les chiffres affichés sont ceux de leur base, et
  chaque calcul est vérifiable.

## 8. L'alternative, si l'informatique refuse

Programmer une extraction nocturne de la requête vers un fichier CSV, dans un
dossier partagé ou envoyé chiffré. Le Cockpit lit alors ce fichier
(`COCKPIT_SOURCE=csv`) et peut tourner n'importe où, y compris sur ton propre
hébergement. Les chiffres datent de la veille, ce qui suffit à presque tous les
pilotages mensuels.
