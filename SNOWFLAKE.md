# Le Cockpit dans Snowflake

L'application tourne **à l'intérieur de l'entrepôt du client** : les données ne
sortent pas, il n'y a pas d'identifiant à stocker, pas de serveur à louer, et
l'adresse reste sous le domaine Snowflake de l'entreprise.

C'est la version à montrer à une direction informatique. La version publique
sur Streamlit Cloud reste la vitrine commerciale.

---

## Ce qui est en place aujourd'hui

| Objet | Nom | Rôle |
|---|---|---|
| Base | `MAISON_LAURET` | la démonstration |
| Schéma | `VENTES` | |
| Table | `TICKETS` | 33 841 lignes, du 01/05/2025 au 31/10/2026 |
| Vue sécurisée | `VENTES_PAR_ROLE` | filtre les lignes selon le rôle Snowflake connecté |
| Table de droits | `ACCES_MAGASIN` | la correspondance rôle → magasin |
| Dépôt Git | `DEMO_RETAIL` | pointe sur GitHub `AzAnalytics/Demo_retail_demo` |
| Application | `MAISON_LAURET.VENTES.COCKPIT` | « Le Cockpit - Maison Lauret » |
| Entrepôt | `WH_XS` | X-Small, suspension automatique |

## Les trois niveaux de sécurité

1. **L'écran** : un compte, un mot de passe, un rôle (lecteur, contributeur,
   administrateur). Un lecteur n'a pas le panneau technique ni l'export.
2. **La requête** : le périmètre du compte part dans le `WHERE`. Un vendeur
   d'Auch ne reçoit jamais les lignes de Toulouse, même dans la mémoire de son
   navigateur. Vérifié dans l'historique Snowflake : 16 951 lignes renvoyées
   pour le compte Toulouse, 33 841 pour la direction.
3. **L'entrepôt** : la vue `VENTES_PAR_ROLE` filtre sur `CURRENT_ROLE()`. Même
   en se connectant à Snowflake sans passer par le Cockpit, un rôle de magasin
   ne voit que ses lignes, et la table brute lui est refusée.

> **Édition Standard** : les `ROW ACCESS POLICY` natives demandent l'édition
> Enterprise. La vue sécurisée donne le même résultat et fonctionne partout.
> C'est la réponse à donner si un client est en Standard.

## Les chiffres se mettent à jour tout seuls

> **Désactivée par défaut, et c'est une décision de coût.** Une page laissée
> ouverte réveille l'entrepôt à chaque cycle, et un réveil est facturé au
> minimum une minute. Mesuré sur ce compte : **1,22 crédit en une heure** avec
> l'application ouverte, soit environ 2,40 $. Sur la démonstration les données
> ne bougent jamais : `COCKPIT_FRAICHEUR_S` vaut 0. Chez un client dont les
> ventes arrivent en continu, le mettre à 300.

Quand elle est active, l'écran relit l'entrepôt **toutes les cinq minutes**,
sans que personne ne clique : un fragment Streamlit se réveille toutes les trente secondes, compare
l'âge de la dernière lecture au délai, et relance la page quand il est dépassé.
Entre deux réveils rien ne clignote, ce qui compte quand on présente.

Le panneau technique indique l'ancienneté de la lecture (« lu il y a 12 s »),
jamais une heure : l'horloge du serveur Snowflake n'est pas celle du client.

Réglages, par variable d'environnement :

| Variable | Défaut | Effet |
|---|---|---|
| `COCKPIT_FRAICHEUR_S` | 0 | délai avant relecture automatique, 0 pour désactiver |
| `COCKPIT_MOIS_HISTORIQUE` | 36 | mois lus dans l'entrepôt, 0 pour tout |
| `COCKPIT_TABLE_SNOWFLAKE` | `MAISON_LAURET.VENTES.VENTES_PAR_ROLE` | l'objet lu |

La requête ne demande que les trente-six derniers mois. Sur la démonstration
cela ne change rien ; chez un client qui garde dix ans de tickets, c'est la
différence entre une seconde et une facture.

## Installer chez un client, de zéro

1. **Le dépôt** (une fois) :
   ```sql
   CREATE OR REPLACE API INTEGRATION GIT_HTTPS_API
     API_PROVIDER = GIT_HTTPS_API
     API_ALLOWED_PREFIXES = ('https://github.com/AzAnalytics')
     ENABLED = TRUE;

   CREATE OR REPLACE GIT REPOSITORY MAISON_LAURET.VENTES.DEMO_RETAIL
     API_INTEGRATION = GIT_HTTPS_API
     ORIGIN = 'https://github.com/AzAnalytics/Demo_retail_demo';
   ```
   L'adresse ne contient **qu'une fois** `https://`, l'erreur est vite faite.

2. **Les données** : `snowflake/01_chargement.sql`.
3. **La sécurité** : `snowflake/02_securite.sql`.
4. **L'application** :
   ```sql
   CREATE OR REPLACE STREAMLIT MAISON_LAURET.VENTES.COCKPIT
     ROOT_LOCATION = '@MAISON_LAURET.VENTES.DEMO_RETAIL/branches/main'
     MAIN_FILE = 'app.py'
     QUERY_WAREHOUSE = WH_XS;

   ALTER STREAMLIT MAISON_LAURET.VENTES.COCKPIT
     SET TITLE = 'Le Cockpit - Maison Lauret';
   ```

## Montrer l'application à quelqu'un d'extérieur

Le bouton **Share** de l'application partage avec un **rôle ou une personne du
compte Snowflake**. Il n'existe pas de lien public anonyme : pour la vitrine
ouverte à tous, c'est la version Streamlit Cloud qui sert.

Pour un prospect que l'on veut laisser essayer seul :

1. Jouer `snowflake/03_partage.sql` : il crée le rôle `COCKPIT_DEMO`, qui
   reçoit l'application et l'entrepôt, **et rien d'autre**. L'application
   tourne avec les droits de son propriétaire : elle lit les ventes pour le
   visiteur sans jamais les lui ouvrir.
2. Governance & security > Users & roles > **Invite** (ou Create user), puis
   `GRANT ROLE COCKPIT_DEMO TO USER "prenom.nom";`
3. Sur l'application, **Share > Copy link > For app viewers** : l'écran
   s'ouvre seul, sans la navigation Snowflake autour.

Deux choses à savoir avant d'inviter : la personne devient utilisateur de ton
compte, et sa visite consomme ton entrepôt (quelques centimes). Les comptes du
Cockpit (direction, toulouse, vendeur) s'ajoutent par-dessus : le rôle
Snowflake ouvre la porte de l'immeuble, le compte du Cockpit décide de l'étage.

## Mettre à jour après une modification du code

```sql
ALTER GIT REPOSITORY MAISON_LAURET.VENTES.DEMO_RETAIL FETCH;
```
Puis recharger la page de l'application. Rien d'autre : pas de redéploiement,
pas de copie de fichiers.

## Les pièges rencontrés, et leur solution

| Symptôme | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: plotly` | Snowflake ignore `requirements.txt` | `environment.yml`, canal `snowflake` |
| Courbe en ligne droite | Streamlit 1.22 ne décode pas les tableaux base64 de Plotly 6+ | versions épinglées dans `environment.yml` |
| `expander() got an unexpected keyword 'icon'` | Streamlit plus ancien dans Snowflake | émojis plutôt que `:material/...` |
| Fond des onglets trop sombre | Snowflake ignore `.streamlit/config.toml` | styles dans `cockpit_theme.py` |
| `COPY INTO` refusé depuis le dépôt Git | fonctionnalité non prise en charge | `INSERT ... SELECT` (fichier 01) |
| Tout semble autorisé pendant un test de rôle | rôles secondaires actifs dans Snowsight | `USE SECONDARY ROLES NONE;` |
| `GRANT ... TO USER prenom.nom` échoue | point dans l'identifiant | guillemets : `"prenom.nom"` |
| Le code semble ne pas se mettre à jour | Snowsight affiche un résultat de FETCH périmé | relire le résultat du `FETCH`, puis `LS @...` pour vérifier que le fichier est arrivé |

## Le coût

**Le vrai poste de coût, c'est l'application ouverte, pas les requêtes.** Tant
qu'un onglet du Cockpit est ouvert dans Snowflake, l'entrepôt reste allumé :
mesuré à 1,22 crédit sur une heure. Fermer l'onglet après une démonstration
vaut toutes les optimisations de requête. Pensez aussi à poser un budget dans
Admin > Cost management, qui prévient par courriel.

L'entrepôt `WH_XS` ne tourne que pendant une requête et se suspend tout seul.
La lecture complète des 33 841 lignes prend moins d'une seconde, et
l'application ne relit l'entrepôt qu'une fois par heure (cache). Une
démonstration d'une heure coûte quelques centimes de crédit.
