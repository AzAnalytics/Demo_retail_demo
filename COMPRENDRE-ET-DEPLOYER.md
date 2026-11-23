# Le Cockpit Maison Lauret : comprendre, vendre, déployer

Notice écrite le 23/11/2026 à partir du code réel, fichier par fichier. Objectif :
que tu puisses répondre à n'importe quelle question d'un prospect sans ouvrir le
code, et mettre la démo en ligne sans dépendre de quelqu'un.

---

## 1. La carte du code, en sept lignes

| Fichier | Ce qu'il fait | Tu y touches quand |
|---|---|---|
| `app.py` (340 l.) | L'écran : filtres, 4 indicateurs, alertes, 6 onglets, export CSV | tu changes ce qui s'affiche |
| `cockpit_theme.py` (348 l.) | La charte navy/or, l'écran d'embarquement, l'en-tête, le pied de page, le style des graphiques | tu changes l'apparence |
| `cockpit_forecast.py` (196 l.) | Le moteur de prévision : 3 modèles, choix automatique du meilleur | tu changes la prévision |
| `config.py` (61 l.) | Les réglages (fichier de données, objectif +8 %, seuil d'alerte 10 %, horizon 12 mois) | tu changes un paramètre sans toucher au code |
| `generate_dataset.py` (71 l.) | Fabrique le CSV de démonstration | tu refais des données |
| `ventes_maison_lauret.csv` | 33 940 ventes, 18 mois, 3 boutiques | jamais à la main |
| `version-web/` | Une copie du tableau de bord en HTML/JS, sans Python | tu veux l'intégrer au site |

**Le chemin d'exécution**, quand quelqu'un ouvre la page : le thème s'applique,
l'écran d'embarquement passe (2,8 secondes, une seule fois par visite), le CSV
est chargé en mémoire, les filtres réduisent les données, le dernier mois du
fichier devient le mois de référence, les indicateurs et les alertes se
calculent, les six onglets s'affichent, la prévision tourne à la demande.

---

## 2. Chaque chiffre de l'écran, d'où il sort

C'est la partie à connaître par coeur : un prospect te demandera « ça veut dire
quoi exactement ? », et la réponse vaut mieux que le graphique.

### Les quatre indicateurs du haut

| Affiché | Calcul exact | Ce que tu dis | La limite à dire aussi |
|---|---|---|---|
| **Chiffre d'affaires** 69 646 € | somme de `ca_ttc` sur le dernier mois du fichier | « le réalisé du mois, comparé au même mois l'an dernier, pas au mois d'avant : c'est la seule comparaison honnête quand l'activité est saisonnière » | si le mois n'existe pas l'an dernier, le Cockpit compare au mois précédent et l'écrit à l'écran |
| **Marge** 36 952 € | somme de `marge`, soit quantité × (prix de vente moins coût d'achat) | « la marge commerciale, article par article, pas une estimation globale » | elle ne déduit ni les salaires ni les charges : c'est une marge brute |
| **Taux de marge** 53,1 % | marge ÷ chiffre d'affaires | « il descend quand tu vends plus de produits à faible marge, même si le CA monte » | le nom de la colonne (`ca_ttc`) ne correspond pas au calcul, voir le point 1 du chapitre 4 : à corriger avant de le montrer |
| **Panier moyen** 36,10 € | chiffre d'affaires ÷ nombre de lignes du fichier | « ce que dépense un client en moyenne par passage en caisse » | vrai ici parce qu'une ligne du fichier est un ticket ; chez un vrai client, un ticket a plusieurs lignes et il faut un numéro de ticket |

Les variations affichées en petit sous chaque chiffre sont des pourcentages
d'écart avec le même mois l'an dernier. Le taux de marge, lui, varie en
**points** (de 53,1 à 52,9, c'est 0,2 point, pas 0,2 %). C'est une erreur
classique en rendez-vous, et ton écran l'écrit correctement.

### Les alertes

Pour chaque catégorie de produits, le Cockpit compare le mois de référence au
même mois l'an dernier. Si l'écart dépasse **10 %** (réglable dans `config.py`),
il affiche une ligne rouge en cas de baisse, verte en cas de hausse. S'il n'y a
rien, il le dit au lieu de laisser un blanc.

Ce que tu dis : « le Cockpit regarde chaque famille de produits tout seul, tous
les mois, et ne parle que quand il y a quelque chose à dire. »

### Les six onglets

1. **Évolution** : le CA mois par mois, une courbe par boutique.
2. **Magasins** : CA et marge par boutique, puis le mix de catégories de chacune.
3. **Produits** : top 10 et flop 10 par CA, puis la contribution de chaque
   catégorie à la marge (la couleur donne le taux, la longueur donne les euros).
4. **Habitudes** : le CA par jour de la semaine, avec le meilleur jour nommé.
5. **Objectif** : le réalisé face à un objectif fixé à l'an dernier +8 %
   (réglable), et le taux d'atteinte.
6. **Prévisions** : voir ci-dessous.

### L'export

Le bouton du bas exporte **les données filtrées**, pas tout le fichier. Un
dirigeant qui veut vérifier dans Excel peut le faire : c'est un argument de
confiance, utilise-le.

---

## 3. La prévision, expliquée pour pouvoir la défendre

C'est ton meilleur argument et le plus risqué : si tu ne sais pas l'expliquer,
tu passes pour quelqu'un qui a copié un modèle sur internet.

### Ce que fait la machine, en six étapes

1. Elle agrège les ventes en **une valeur par mois** (18 mois ici).
2. Elle met **trois modèles en concurrence** :
   - *Saisonnier ajusté* : « le mois de mars prochain ressemblera au mars
     dernier, multiplié par la croissance annuelle moyenne ».
   - *Ridge + Fourier* : une régression qui apprend une tendance de fond et des
     cycles annuels, sur le logarithme du CA (donc en pourcentage, pas en euros).
   - *Tendance × saisonnalité* : une tendance de fond multipliée par le profil
     mensuel habituel.
3. Elle **cache les 3 derniers mois**, entraîne les trois modèles sur le reste,
   leur fait prédire ces 3 mois, et compare à la réalité.
4. L'écart moyen en pourcentage (le **MAPE**) départage : le plus précis gagne.
   C'est le « ± 3,4 % » affiché, et le nom du gagnant est écrit à l'écran.
5. Le modèle gagnant est réentraîné sur **tout** l'historique et projette 12 mois.
6. La **zone dorée** autour de la courbe est un intervalle à 95 %, calculé sur la
   dispersion des variations d'une année sur l'autre, et qui s'élargit avec le
   temps : plus on va loin, moins on sait.

### Les quatre phrases à dire au client

> « Je ne vous vends pas une boule de cristal. Le Cockpit essaie trois méthodes,
> leur cache les trois derniers mois, et garde celle qui avait vu juste. »
>
> « Le chiffre affiché à côté, c'est son erreur mesurée sur ce test : ± 3,4 %.
> Vous savez donc ce que vaut la prévision avant de l'utiliser. »
>
> « La zone claire autour de la courbe, c'est l'incertitude. Elle s'élargit avec
> le temps, parce que personne ne sait ce qui se passera dans douze mois. »
>
> « Et le nom de la méthode retenue est écrit à l'écran. Rien n'est caché. »

### Les trois questions pièges, et tes réponses

- **« Pourquoi pas de l'intelligence artificielle ? »** Avec 18 mois de
  données, un modèle lourd apprend le passé par coeur au lieu de comprendre la
  tendance, et les modèles à arbres (random forest, gradient boosting) sont
  incapables de sortir des valeurs déjà vues : ils ne peuvent donc pas prévoir
  une croissance. Le bon modèle est celui qui gagne le test, pas le plus
  impressionnant.
- **« C'est fiable à combien ? »** Le MAPE affiché, et seulement lui. Ici 3,4 %
  sur le global ; par boutique ou par catégorie il est plus élevé, parce que les
  petites séries bougent plus. Le tableau récapitulatif de l'onglet le montre
  honnêtement.
- **« Et si mon activité change du tout au tout ? »** Aucune prévision ne voit
  venir un évènement qui n'est pas dans l'historique. C'est pour ça que le
  Cockpit sert surtout à voir ce qui décroche **maintenant**, et que la prévision
  est le dernier onglet, pas le premier.

---

## 4. Ce qui n'est pas prêt pour la production

Dix points trouvés en lisant le code, du plus grave au plus petit. Les quatre
premiers se voient en rendez-vous.

1. **La colonne s'appelle `ca_ttc`, mais la TVA n'apparaît nulle part.** Le coût
   d'achat est calculé comme un pourcentage du prix de vente
   (`cout = prix × (1 − taux de marge)`), sans jamais retirer de TVA. Deux
   lectures possibles, et les deux posent problème : soit les prix sont en
   réalité hors taxes et la colonne est mal nommée, soit ce sont des prix
   boutique TTC, et alors le taux de marge affiché (53,1 %) compte comme de la
   marge la TVA que le commerçant reverse. Dans ce second cas, à 20 % de TVA, le
   vrai taux sur chiffre d'affaires hors taxes tourne autour de 46 %. Choisis une
   convention, renomme la colonne (`ca_ht`), et écris-le à l'écran : un
   dirigeant vérifie toujours son taux de marge.
2. **Les données s'arrêtent au 30/06/2026.** L'écran affiche « juin 2026 comparé
   à juin 2025 », et il affichera la même chose l'an prochain. Un prospect lit
   ça comme une démo abandonnée. Il faut que la période glisse avec la date du
   jour, comme je viens de le faire sur l'autre version.
3. **Aucun test sur 950 lignes de code.** Rien ne t'avertit si une modification
   casse un calcul : tu le découvres à l'écran, ou le client le découvre.
4. **L'écran plante en public si le fichier change.** Une colonne renommée ou
   absente, et le prospect voit une erreur Python rouge sur fond blanc. Il faut
   un message en français et un arrêt propre.
5. **L'onglet Prévisions ignore les filtres, sans le dire.** C'est volontaire
   (la prévision se fait sur tout l'historique), mais quelqu'un qui filtre sur
   Toulouse verra une prévision « toutes boutiques » sans comprendre. Une phrase
   à l'écran suffit.
6. **Les alertes sont en pourcentage seulement.** Une catégorie à 2 000 € qui
   recule de 11 % déclenche la même alerte qu'une catégorie à 200 000 €. Un
   dirigeant agit sur des euros, pas sur des pourcentages : il faut afficher
   l'écart en euros et trier par là.
7. **Le cache des données n'expire jamais.** Si tu remplaces le CSV sans
   redémarrer, l'écran continue d'afficher les anciens chiffres.
8. **La version web statique est incomplète** : `index.html` cherche un
   `data.json` qui n'existe pas dans le dossier. Il faut lancer `export_data.py`
   pour le fabriquer, sinon la page reste vide.
9. **Le mot de passe prévu n'est branché nulle part.** `config.ACCESS_PASSWORD`
   est lu puis jamais utilisé : la page est publique. Sans gravité pour une
   démo, bloquant le jour où tu mets les vraies données d'un client.
10. **Le réveil automatique dit quelque chose.** Tu as ajouté le 23/10 une tâche
    GitHub qui réveille l'application trois fois par jour, parce que
    l'hébergement gratuit l'endort. Ses exécutions se sont arrêtées le 04/11, et
    l'adresse `demoretaildemo.streamlit.app` répond aujourd'hui « You do not have
    access to this app or it does not exist ». Le dépôt GitHub, lui, est intact
    et public.

---

## 5. Déployer : les trois voies

Ton dépôt public `AzAnalytics/Demo_retail_demo` contient déjà tout le nécessaire
(sauf le dossier `version-web`, qui n'est que sur ton disque).

### Voie A, remettre en ligne ce soir : Streamlit Community Cloud

Gratuit, dix minutes, c'est ce qui était en place.

1. Va sur `share.streamlit.io` et connecte-toi avec ton compte GitHub.
2. Regarde si l'application `Demo_retail_demo` est encore listée. Si oui, elle est
   en pause : un bouton la relance. Si non, elle a été supprimée.
3. Si elle a disparu : « New app », dépôt `AzAnalytics/Demo_retail_demo`, branche
   `main`, fichier `app.py`, et tu choisis l'adresse.

Limite à connaître : l'application s'endort après quelques heures sans visite, et
le premier visiteur attend trente secondes de réveil. C'est exactement pour ça
que tu avais ajouté la tâche de réveil. L'adresse se termine par
`.streamlit.app` et la page affiche la mention Streamlit.

### Voie B, la version que tu envoies en rendez-vous : Google Cloud Run

Ton `Dockerfile` et ton `DEPLOIEMENT_GCP.md` sont déjà écrits et corrects.

Avantages : une adresse à toi (`cockpit.alexiszueras.fr` par exemple), pas de
mise en veille visible, pas de mention d'un hébergeur gratuit, et un coût réel de
quelques centimes par mois tant que personne ne l'utilise (le service descend à
zéro instance). Il faut une carte bancaire sur le compte Google Cloud, même sans
dépense.

Ce que tu dois faire toi : créer le projet Google Cloud, activer la facturation,
et lancer `gcloud auth login` (je ne me connecte pas à ta place). Ensuite je peux
dérouler le déploiement avec toi.

### Voie C, la page publique du site : la version web statique

`version-web/` est une copie du tableau de bord en HTML et JavaScript, sans
Python : aucune mise en veille, aucun temps de réveil, un coût nul, et elle
s'intègre dans une page de ton site Odoo. En échange, tout est figé au moment de
l'export : les filtres et la prévision ne recalculent plus rien.

Il manque le `data.json` : il se fabrique avec `export_data.py`.

**Mon conseil** : la voie A ce soir pour ne plus avoir de lien mort, la voie C
dans le tunnel de vente (page publique, zéro entretien), et la voie B le jour où
tu veux envoyer une adresse à ton nom à un prospect sérieux.

---

## 6. Ce que je propose comme suite

Dans cet ordre, parce que chaque étape rend la suivante plus sûre :

1. Corriger les quatre points qui se voient (`ca_ttc`, données figées, plantage
   en public, filtres de la prévision).
2. Écrire les tests qui gèlent les calculs : indicateurs, alertes, prévision,
   et un test qui ouvre l'écran de bout en bout comme le fait un visiteur.
3. Passer les alertes en euros et les trier par enjeu.
4. Fabriquer le `data.json` et vérifier la version web.
5. Remettre en ligne, et mettre le lien dans tes bios une fois qu'il tient.
