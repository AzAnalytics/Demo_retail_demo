# Brancher Le Cockpit sur une base de données

Oracle, SQL Server, PostgreSQL, MySQL, un fichier SQLite, BigQuery. La réponse
courte : **une requête SQL remplace le fichier CSV, et rien d'autre ne change**
dans le Cockpit.

Tout passe par `source_donnees.py`. L'écran, les calculs et la prévision ne
voient qu'un tableau avec les colonnes du Cockpit, peu importe d'où il vient.

## 1. Le principe, en trois lignes de code

```python
import source_donnees as src

cx = src.connexion_oracle(utilisateur, mot_de_passe, "srv.client.fr:1521/PROD")
ventes = src.depuis_base(cx, requete)      # contrôlé, typé, prêt à afficher
cx.close()
```

`depuis_base` vérifie la forme de ce qui revient : colonnes attendues, dates
lisibles, montants numériques. Une base de données ne protège de rien. Une vue
modifiée par l'éditeur de l'ERP, une colonne renommée, et le tableau de bord
afficherait des chiffres faux sans prévenir. Le contrôle est donc à l'entrée,
toujours, et il est testé (`test_source_donnees.py`).

## 2. Le pilote, par base

| Base | À installer | Connexion |
|---|---|---|
| **Oracle** | `pip install oracledb` | `src.connexion_oracle(user, mdp, "serveur:1521/SERVICE")` |
| PostgreSQL | `pip install psycopg` | `src.connexion_postgres("postgresql://user:mdp@hote/base")` |
| SQL Server | `pip install pyodbc` + pilote ODBC 18 | `src.connexion_sqlserver(chaine_odbc)` |
| MySQL / MariaDB | `pip install mysql-connector-python` | une connexion DBAPI, même usage |
| SQLite | rien, c'est dans Python | `src.connexion_sqlite("ventes.db")` |
| **Snowflake** | `pip install snowflake-connector-python` | `src.connexion_snowflake(user, compte, entrepot, base)` |
| BigQuery | `pip install google-cloud-bigquery` | passe par son client, puis `valide(df)` |

**Oracle, le point qui bloque d'habitude** : le pilote `oracledb` fonctionne en
mode « thin », c'est-à-dire **sans installer le client Oracle** sur la machine.
C'était la grosse corvée de l'ancien `cx_Oracle`. Plus besoin.

Le `dsn` est de la forme `serveur:1521/NOM_DU_SERVICE`. Si l'informaticien du
client parle de `SID` plutôt que de service, la forme change un peu : lui
demander la chaîne de connexion exacte, c'est deux minutes pour lui.

## 2 bis. Reprendre une connexion qui existe déjà (le cas le plus fréquent)

Quand un classeur Excel interroge déjà l'ERP du client, tout est là : la
chaîne de connexion et la requête. C'est le chemin le plus court.

Dans Excel : Données, Connexions, Propriétés, onglet Définition. On y lit la
**chaîne de connexion** et le **texte de la commande** (le SQL).

```
COCKPIT_SOURCE=odbc
COCKPIT_DB_CHAINE=DRIVER={Oracle in instantclient_19_5x64};SERVER=...;UID=...;PWD=...
COCKPIT_SOURCE_REQUETE=SELECT ...
```

Deux pièges, et ils comptent :

- Cette chaîne contient **le mot de passe en clair**. Il n'est pas chiffré dans
  le fichier de connexion Excel non plus. Demander un compte dédié en lecture
  seule pour le tableau de bord, et ne jamais recopier cette chaîne dans un
  document, une capture d'écran ou un dépôt.
- Le pilote ODBC (`Oracle in instantclient_19_5x64`) doit être **installé sur
  la machine qui exécute le Cockpit**. C'est vrai sur le poste du client, faux
  sur un hébergement. Pour sortir de cette dépendance, passer à `oracledb` en
  mode « thin » : il ne demande que `hote:port/service`, qu'on lit dans le
  fichier `tnsnames.ora` du client (dossier `network/admin` de l'instant
  client), à l'entrée qui porte le nom du `SERVER` ou du `DBQ`.

**Et le réseau ?** Un tableau de bord hébergé sur internet ne voit pas la base
d'un client posée dans ses locaux. Trois réponses possibles, dans l'ordre de
simplicité : faire tourner le Cockpit sur un poste du client, programmer une
extraction nocturne vers un fichier que le Cockpit lit, ou ouvrir un accès
(VPN, liste d'adresses autorisées) ce que l'informatique accepte rarement pour
un prestataire. La deuxième réponse est celle qui passe presque toujours.

## 2 ter. Le cas Snowflake

Snowflake peut jouer trois rôles différents, et il faut les distinguer avant
d'en parler à un client.

### Comme source de données (fait)

```
COCKPIT_SOURCE=snowflake
COCKPIT_SF_COMPTE=xy12345.eu-west-1
COCKPIT_SF_UTILISATEUR=COCKPIT_LECTURE
COCKPIT_SF_MOTDEPASSE=...
COCKPIT_SF_ENTREPOT=WH_XS
COCKPIT_SF_BASE=VENTES
COCKPIT_SF_SCHEMA=PUBLIC
COCKPIT_SF_ROLE=ROLE_COCKPIT
COCKPIT_SOURCE_REQUETE=SELECT ...
```

`pip install snowflake-connector-python`, et c'est tout : le Cockpit ne voit
aucune différence avec Oracle ou un CSV. Le connecteur accepte aussi une clé
privée ou un SSO (`authenticator="externalbrowser"`) à la place du mot de
passe.

Deux points de vigilance propres à Snowflake : l'**entrepôt** (warehouse) est
ce qui coûte, pas le stockage, donc un XS avec mise en pause automatique
suffit pour un tableau de bord ; et le **rôle** de connexion décide de ce que
la requête rapporte.

### Comme hébergeur : Streamlit in Snowflake

Snowflake exécute l'application chez lui. C'est séduisant et ça règle d'un coup
trois choses dont on a parlé : **plus de mise en veille**, les **données ne
sortent jamais** de l'entrepôt du client, et l'accès est gouverné par les
**rôles Snowflake** plutôt que par un fichier de comptes.

Quatre contraintes à vérifier avant de le promettre :

- les bibliothèques se prennent dans le canal Anaconda de Snowflake (pandas,
  numpy et plotly y sont), et il n'y a pas d'accès internet sortant par défaut ;
- la version de Streamlit y est **en retard** sur la dernière : certaines
  fonctions récentes utilisées ici (conteneur identifié par `key`, largeurs
  `stretch`, icônes `:material/...`) peuvent manquer, donc l'habillage est à
  tester avant d'annoncer une date ;
- pas d'écriture de fichiers : mettre `COCKPIT_DEMO_AUTO=0`, ce qui est de
  toute façon la règle chez un client ;
- l'application peut tourner avec les droits de son **propriétaire** plutôt que
  ceux de l'utilisateur connecté. Dans ce cas, les politiques de sécurité par
  ligne du client ne s'appliquent pas comme on le croit : c'est le premier
  point à faire confirmer par leur administrateur.

### Comme couche de sécurité

C'est son meilleur apport. Les **row access policies** de Snowflake filtrent les
lignes dans la base, selon le rôle de la personne connectée. C'est exactement
le niveau 3 du chapitre sur les périmètres, en mieux : les lignes interdites ne
sortent jamais du serveur, et c'est l'administrateur du client qui en répond,
pas toi. Les périmètres de `permissions.py` deviennent alors inutiles, et seuls
les rôles d'application (lecteur, contributeur, admin) gardent un sens.

### Quand le proposer, et quand se taire

Snowflake n'a de sens que si **le client en est déjà client**. Une PME de trois
boutiques ou une salaison ne le sera jamais : lui proposer Snowflake, c'est lui
vendre une facture mensuelle pour lire ses propres ventes. En revanche, face à
une ETI, un grand compte ou une ESN, pouvoir dire « le Cockpit se branche sur
votre Snowflake, et il peut même tourner dedans » change la conversation.

## 3. La requête : écrite une fois, relue par le client

```sql
SELECT v.date_vente    AS date,
       m.libelle       AS magasin,
       f.libelle       AS categorie,
       a.libelle       AS produit,
       l.quantite      AS quantite,
       l.prix_unitaire AS prix_unitaire,
       a.cout_standard AS cout_unitaire,
       l.montant_ttc   AS ca_ttc
FROM lignes_vente l
JOIN ventes   v ON v.id = l.vente_id
JOIN magasins m ON m.id = v.magasin_id
JOIN articles a ON a.id = l.article_id
JOIN familles f ON f.id = a.famille_id
WHERE v.date_vente >= :debut
```

Trois règles qui évitent des ennuis :

- **Renommer côté SQL** (`AS date`, `AS magasin`), jamais côté Python. La
  correspondance reste lisible par l'informaticien du client, qui est souvent
  celui qui la relira dans six mois.
- **Filtrer la période dans la requête**, jamais après. On ne rapatrie pas dix
  ans de lignes pour en afficher dix-huit mois.
- **Jamais de `SELECT *`** sur une table de production : le jour où l'éditeur
  ajoute une colonne, on ne veut pas que le tableau de bord change tout seul.
- **Ne pas transformer la date en texte.** `TO_CHAR(date, 'DD/MM/YYYY')` oblige
  à la reconvertir côté Python, et un format mal écrit passe inaperçu : un
  `'DD/MM/YYY'` (trois Y) donne une année à trois chiffres sans que rien ne
  proteste. On renvoie la date telle quelle, et pandas la lit.

## 4. Où mettent les identifiants (jamais dans le code)

En local, dans `.env` (déjà ignoré par git) :

```
COCKPIT_SOURCE=oracle
COCKPIT_DB_UTILISATEUR=cockpit_lecture
COCKPIT_DB_MOTDEPASSE=...
COCKPIT_DB_DSN=srv.client.fr:1521/PROD
COCKPIT_SOURCE_REQUETE=SELECT ...
```

Sur **Streamlit Community Cloud** : les secrets se collent dans l'interface de
l'application (menu Settings, Secrets), au format TOML, et se lisent avec
`st.secrets`. Sur **Cloud Run** : des variables d'environnement, ou Secret
Manager pour faire les choses proprement.

Dans tous les cas : rien de tout cela ne part sur GitHub. Si un identifiant
client est commité par erreur, il est à considérer comme compromis, et il faut
le faire changer, pas seulement supprimer le fichier.

## 5. Ne pas assommer la base du client

Le tableau de bord se recharge à chaque clic. Sans précaution, chaque filtre
déclenche une requête sur la base de production, et l'informaticien du client
appelle au bout d'une journée.

```python
@st.cache_data(ttl=3600)       # une lecture par heure, pas une par clic
def charger_donnees(...):
    ...
```

C'est déjà en place dans `app.py`. Pour un gros volume, deux solutions, dans
cet ordre : faire les regroupements en SQL (`GROUP BY` mois, magasin, famille)
plutôt que de rapatrier les lignes, ou mettre en place une extraction nocturne
dans un fichier que le Cockpit lit. La deuxième est souvent la plus simple à
faire accepter : elle ne touche pas à la production aux heures ouvrées.

### Le montrer, plutôt que de le promettre

Le panneau `🔧 État technique` affiche, pour un profil administrateur, un bloc
**« Ce que le Cockpit demande à votre base »** : nombre de lectures depuis
l'ouverture de l'écran, temps total demandé, lecture la plus lente, lignes
ramenées, et la requête telle qu'elle part. Tout est mesuré par l'application
elle-même (`couts.py`, alimenté par `source_donnees._marque`) : **aucun
privilège n'est demandé à la base du client**, pas de `V$SESSION`, pas de vue
d'administration à ouvrir.

C'est la réponse à la question que pose l'informaticien avant d'accorder un
accès. Sur Snowflake, le même bloc affiche des crédits et des euros, parce que
l'entrepôt facture à l'usage. Sur Oracle, SQL Server ou Postgres, il n'affiche
aucun euro et il le dit : le serveur est déjà payé, le Cockpit ne coûte rien de
plus. Afficher « 0 € » serait un mensonge poli, afficher la charge est une
preuve.

> « Vous voulez savoir ce que ça prend à votre base ? C'est écrit dans l'écran :
> une lecture par heure, trois dixièmes de seconde, et voilà la requête. »

## 6. Ce qu'il faut demander à l'informaticien du client

À envoyer tel quel, ça fait sérieux et ça évite trois allers-retours :

1. Un **compte en lecture seule**, dédié au tableau de bord.
2. La **chaîne de connexion** exacte (serveur, port, service ou SID).
3. Une **vue** si possible, plutôt qu'un accès direct aux tables : elle protège
   le tableau de bord des changements de schéma, et lui garde la main.
4. Le **volume** : combien de lignes de vente par mois.
5. Une **fenêtre horaire** acceptable pour les lectures, et s'il faut un VPN.
6. Qui prévenir si la structure change.

## 7. Ce qui se passe vraiment en mission

Dans une PME, l'accès direct à la base arrive rarement au premier rendez-vous.
L'ordre habituel est : un **export CSV ou Excel** pour démarrer (ce que le
Cockpit lit déjà), puis un **accès en lecture seule** une fois la confiance
installée, parfois jamais si l'ERP est hébergé par un éditeur qui ne donne rien.

Ce n'est pas un problème : le Cockpit lit les deux, et c'est exactement
l'argument à donner en rendez-vous.

> « On démarre avec un export, vous n'avez rien à ouvrir. Quand vous voulez que
> ce soit automatique, on branche un compte en lecture seule sur votre base, et
> le tableau de bord ne change pas d'une ligne. »
