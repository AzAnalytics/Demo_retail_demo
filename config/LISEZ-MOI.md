# Le dossier des réglages du client

Ce dossier est monté dans le conteneur sur `/config`, en lecture seule.
**Rien de ce qui est ici n'entre dans l'image Docker**, et rien n'est
versionné : c'est voulu, ce sont les données et les accès du client.

## Ce qu'on y dépose

**`profils.json`** — les comptes et leurs périmètres. Partir de
`profils.example.json`, à la racine du projet, et remplacer les empreintes.

Pour fabriquer l'empreinte d'un mot de passe, sans jamais l'écrire en clair
nulle part :

```bash
python -c "import permissions as p; print(p.empreinte('le-mot-de-passe'))"
```

Puis coller le résultat dans le champ `empreinte` du profil. Le mot de passe
lui-même n'est stocké nulle part, et l'empreinte ne se relit pas.

**`ventes.csv`** (facultatif) — l'export du client, si le Cockpit lit un
fichier plutôt qu'une base. Dans ce cas, décommenter `COCKPIT_DATA_FILE` et
`COCKPIT_DEMO_AUTO: "0"` dans `docker-compose.yml`, sinon l'application
régénérerait des ventes de démonstration par-dessus.

## Ce qu'on n'y met jamais

Les identifiants de base de données. Ils passent par les variables
d'environnement du `docker-compose.yml`, ou mieux, par les secrets de la
machine. Voir `BASES-DE-DONNEES.md`.

## Si ce dossier est vide

L'application démarre quand même, mais **sans verrou d'accès** : n'importe
qui sur le réseau interne voit les chiffres. C'est acceptable pour une
démonstration, jamais pour une livraison. Vérifier l'écran de connexion
avant de dire au client que c'est en place.
