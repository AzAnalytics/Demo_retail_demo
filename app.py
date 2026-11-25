"""
Le Cockpit — Maison Lauret (démo)
=================================
Tableau de bord de pilotage. Données 100% fictives.
Démonstrateur de l'offre "Le Cockpit" — Alexis Zueras.

Lancer :  streamlit run app.py
"""
import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from cockpit_theme import (
    apply_theme, splash, header, footer, plotly_layout, COCKPIT,
)
import acces                    # verrou d'entrée quand le Cockpit tourne chez un client
import permissions as perm      # qui voit quelles lignes (l'équivalent du RLS)
import comptes                  # les personnes et leurs droits, dans l'entrepôt
import cockpit_calculs as cal   # tous les calculs, testés dans test_cockpit.py
import source_donnees as src   # fichier, table Snowflake, base du client
import cockpit_forecast as cf
import generate_dataset as gen  # la démo se régénère si elle est périmée
import config   # variables externalisées (données, paramètres, secrets) hors du code

# ==================================================================
# CONFIG & CONSTANTES
# ==================================================================
st.set_page_config(page_title="Le Cockpit · Maison Lauret",
                   page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

apply_theme()                                    # 1. charte navy/or

# Générique de sortie, joué juste après un clic sur « Se déconnecter ».
if st.session_state.pop(acces.CLEF_DEBARQUEMENT, False):
    splash("Le Cockpit", sous_titre="Fin de session · à bientôt",
           duree=1.8, once=False, eyebrow="DÉBARQUEMENT")

def dans_snowflake() -> bool:
    """L'application tourne-t-elle à l'intérieur de Snowflake ?"""
    try:
        from snowflake.snowpark.context import get_active_session

        get_active_session()
        return True
    except Exception:
        return False


def fichier_profils() -> str | None:
    """Où lire les comptes, selon l'endroit où l'application tourne.

    Dans Snowflake, la démonstration des rôles est justement ce qu'on vient y
    voir : on charge les comptes livrés avec le dépôt. Ailleurs, on ne lit que
    `profils.json`, qui n'est jamais versionné, pour que la vitrine publique
    reste ouverte au premier visiteur venu.
    """
    if os.environ.get("COCKPIT_PROFILS"):
        return None          # la variable d'environnement a la priorité
    if dans_snowflake():
        demo = Path(__file__).with_name("profils.demo.json")
        return str(demo) if demo.exists() else None
    return None


# Verrou : connexion nominative s'il existe un fichier de profils, sinon mot de
# passe unique s'il est configuré, sinon rien (c'est le cas de la démonstration).
PROFILS = perm.charge_profils(fichier_profils())
COMPTES_EN_BASE = False     # les comptes sont-ils gérés depuis l'écran ?
if dans_snowflake():
    # Dans l'entrepôt, les comptes vivent dans une table : l'administrateur
    # crée et retire des personnes depuis l'écran, sans toucher au code. Au
    # tout premier démarrage la table est vide : on y recopie les comptes du
    # fichier, sinon la première création ferait disparaître les autres.
    try:
        comptes.assure_table()
        comptes.sème_les_comptes_de_demonstration(PROFILS)
        lignes = comptes.lire()
        if lignes:
            PROFILS = comptes.profils_depuis_lignes(lignes)
            COMPTES_EN_BASE = True
    except Exception as erreur:          # droits manquants, table verrouillée
        st.session_state["_comptes_probleme"] = str(erreur)

autorise, profil = acces.session(PROFILS, config.ACCESS_PASSWORD,
                                 enseigne="Maison Lauret")
if not autorise:
    st.stop()


def reglage(nom: str, defaut=None):
    """Un réglage de config.py, tolérant à un module pas encore rechargé.

    Quand on pousse une nouvelle version, l'hébergeur recharge `app.py` avant
    `config.py` : pendant quelques secondes, l'écran demande un réglage qui
    n'existe pas encore dans le module en mémoire, et il plante. Un réglage
    tout neuf ne doit jamais pouvoir casser une page déjà en ligne.
    """
    return getattr(config, nom, defaut)


def autorise_a(droit: str) -> bool:
    """Sans fichier de profils (démonstration publique), tout est permis."""
    return profil is None or profil.peut(droit)

splash("Le Cockpit",                             # 2. écran d'ouverture animé
       sous_titre="Maison Lauret · Pilotage",
       video=str(config.SPLASH_VIDEO))           # vidéo Gemini si présente, sinon anim CSS

MOIS_FR, JOURS_FR = cal.MOIS_FR, cal.JOURS_FR

# Couleurs magasins harmonisées à la charte navy / or
# Mêmes couleurs que la version web du site : Auch en navy, Montauban en
# or, Toulouse en bleu. Un client qui voit les deux doit reconnaître la même
# boutique à la même couleur.
COULEURS_MAG = {"Auch": COCKPIT["navy"],
                "Montauban": COCKPIT["gold"],
                "Toulouse": "#3E6D9C"}
# Valeurs par défaut : un contributeur peut les ajuster pour sa session
# (voir le panneau « Réglages »), un lecteur ne le peut pas.

eur = cal.euros              # formatage français : 1 234 €

# ==================================================================
# DONNÉES
# ==================================================================
# Les colonnes sans lesquelles l'écran ne peut rien calculer.
COLONNES_ATTENDUES = ("date", "magasin", "categorie", "produit", "quantite",
                      "prix_unitaire", "cout_unitaire", "ca_ttc")


@st.cache_data(ttl=reglage("FRAICHEUR_S", 300))
def charger_donnees(chemin: str, taux_tva: float, demo_auto: bool,
                    magasins: tuple = (), mois: int = 0):
    """Lit le fichier de caisse, le contrôle, et ramène les montants hors taxes.

    Renvoie (données, problème). `problème` est une phrase en français destinée
    au visiteur : si le fichier change ou disparaît, il voit un message, jamais
    une erreur Python.

    Convention de prix : le fichier contient des prix boutique, donc TTC. Tout
    ce qui est affiché est hors taxes (`config.TAUX_TVA`). Le coût d'achat est
    déjà hors taxes, parce que le commerçant récupère la TVA sur ses achats.
    """
    chemin = Path(chemin)
    # Dans Snowflake, on lit l'entrepôt : c'est là que vivent les données du
    # client, et elles n'en sortent pas. Si la table est vide ou absente, on
    # se rabat sur le fichier plutôt que d'afficher un écran vide.
    table = reglage("TABLE_SNOWFLAKE", "")
    if table and src.session_snowflake() is not None:
        try:
            brut = src.depuis_table_snowflake(table, magasins=list(magasins),
                                              mois=mois)
            attrs = dict(brut.attrs)
            brut = cal.montants_hors_taxes(brut, taux_tva)
            brut["mois"] = brut["date"].dt.to_period("M").dt.to_timestamp()
            brut["jour_sem"] = brut["date"].dt.day_of_week
            brut.attrs.update(attrs)
            return brut, ""
        except Exception as erreur:        # table vide, absente, droits manquants
            st.session_state["_repli_fichier"] = str(erreur)

    try:
        if demo_auto and gen.est_perime(chemin):
            # Personne ne relance le script sur un hébergement : la démonstration
            # se refabrique au lieu de montrer un mois vieux de cinq mois.
            df = gen.genere()
            try:
                df.to_csv(chemin, index=False)
            except OSError:
                pass                 # disque en lecture seule : on garde en mémoire
            df["date"] = pd.to_datetime(df["date"])
        else:
            df = pd.read_csv(chemin, parse_dates=["date"])
    except FileNotFoundError:
        return None, f"Le fichier de ventes est introuvable ({chemin.name})."
    except Exception as erreur:                      # fichier illisible, encodage, etc.
        return None, f"Le fichier de ventes n'a pas pu être lu ({chemin.name}) : {erreur}"

    manquantes = [c for c in COLONNES_ATTENDUES if c not in df.columns]
    if manquantes:
        return None, ("Le fichier de ventes n'a pas la forme attendue. "
                      f"Colonne(s) absente(s) : {', '.join(manquantes)}.")
    if df.empty:
        return None, "Le fichier de ventes ne contient aucune ligne."

    df = df.dropna(subset=["date"]).copy()
    if df.empty:
        return None, "Aucune date exploitable dans le fichier de ventes."

    for colonne in ("quantite", "prix_unitaire", "cout_unitaire", "ca_ttc"):
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce")
    df = df.dropna(subset=["quantite", "ca_ttc"])
    if df.empty:
        return None, "Aucun montant exploitable dans le fichier de ventes."

    # TTC -> HT, puis marge hors taxes : prix de vente HT moins coût d'achat.
    df = cal.montants_hors_taxes(df, taux_tva)
    df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["jour_sem"] = df["date"].dt.day_of_week
    return df, ""


# Les réglages passent en argument : le cache se renouvelle quand ils changent.
FRAICHEUR = int(reglage("FRAICHEUR_S", 300))

df, probleme = charger_donnees(str(config.DATA_FILE),
                               reglage("TAUX_TVA", 0.20),
                               reglage("DEMO_AUTO", True),
                               tuple(sorted(profil.magasins)) if profil else (),
                               reglage("MOIS_HISTORIQUE", 0))
if probleme:
    st.error(probleme, icon="🚫")
    st.caption("Le Cockpit préfère ne rien afficher plutôt que d'afficher un chiffre faux.")
    st.stop()

# Le périmètre de la personne connectée, appliqué AVANT tout calcul : un
# graphique caché n'est pas une protection, et la prévision travaillerait
# sinon sur des lignes que cette personne n'a pas le droit de voir.
df = perm.applique(df, profil)
if df.empty:
    st.warning("Aucune vente dans votre périmètre.", icon="🔒")
    st.stop()

# En-tête (toujours affiché)
header("Maison Lauret",
       "Concept store déco-maison · 3 boutiques (Toulouse, Auch, Montauban) · données de démonstration")

# ==================================================================
# FILTRES (panneau repliable, masqué par défaut)
# ==================================================================
# Qui est connecté, et comment en sortir. Le bouton est ici, à côté du nom,
# et pas dans la barre latérale repliée que personne n'ouvre.
SESSION_OUVERTE = bool(PROFILS) or bool(config.ACCESS_PASSWORD)
if profil is not None or SESSION_OUVERTE:
    qui, sortie = st.columns([5, 1], vertical_alignment="center")
    if profil is not None:
        # Le détail des droits est dans le panneau d'administration,
        # pas en bandeau.
        marques = [profil.nom or profil.identifiant, profil.role]
        if not profil.voit_tout:
            marques.append(profil.resume().replace("Périmètre, ", ""))
        qui.caption("🔒 " + " · ".join(marques))
    else:
        qui.caption("🔒 Session ouverte.")
    with sortie:
        acces.bouton_deconnexion()

# --- Réglages de session (droit « reglages ») ---
OBJECTIF_CROISSANCE = config.OBJECTIF_CROISSANCE
SEUIL_ALERTE = config.SEUIL_ALERTE
if autorise_a("reglages"):
    with st.sidebar:
        st.subheader("⚙️ Réglages")
        st.caption("Pour cette session seulement. Le fichier de configuration "
                   "n'est pas modifié.")
        OBJECTIF_CROISSANCE = 1 + st.slider(
            "Objectif de croissance (%)", -10, 30,
            int(round((config.OBJECTIF_CROISSANCE - 1) * 100)), 1) / 100
        SEUIL_ALERTE = st.slider(
            "Seuil d'alerte (%)", 2, 40, int(config.SEUIL_ALERTE), 1)

with st.expander("🔎 Filtres", expanded=False):
    f1, f2, f3 = st.columns(3)
    magasins = f1.multiselect("Magasin", sorted(df["magasin"].unique()),
                              default=sorted(df["magasin"].unique()))
    categories = f2.multiselect("Catégorie", sorted(df["categorie"].unique()),
                                default=sorted(df["categorie"].unique()))
    dmin, dmax = df["date"].min(), df["date"].max()
    periode = f3.date_input("Période", value=(dmin, dmax),
                            min_value=dmin, max_value=dmax)

d = df[df["magasin"].isin(magasins) & df["categorie"].isin(categories)]
if isinstance(periode, (list, tuple)) and len(periode) == 2:
    d = d[(d["date"] >= pd.to_datetime(periode[0])) & (d["date"] <= pd.to_datetime(periode[1]))]

# Garde-fou : aucune donnée après filtrage
if d.empty:
    st.warning("Aucune vente ne correspond aux filtres choisis. Ouvre « 🔎 Filtres » et élargis la sélection.")
    st.stop()

# ==================================================================
# MOIS DE RÉFÉRENCE & COMPARAISON
# ==================================================================
# Les calculs vivent dans cockpit_calculs.py : ici on ne fait qu'afficher.
lib_mois = cal.libelle_mois
delta = cal.variation

periode_ref = cal.periode_de_reference(d)
mois_ref, mois_cmp, type_compa = (periode_ref.mois, periode_ref.comparaison,
                                  periode_ref.type_comparaison)
cur = d[d["mois"] == mois_ref]
cmp = d[d["mois"] == mois_cmp] if mois_cmp is not None else cur.iloc[0:0]
# Mois en cours : on tronque la comparaison au même jour, sinon on fabrique
# une baisse qui n'existe pas (vingt jours contre un mois entier).
cmp = cal.a_perimetre_egal(cmp, periode_ref)

ind_c, ind_p = cal.indicateurs(cur), cal.indicateurs(cmp)
ca_c, marge_c, taux_c, panier_c = ind_c.ca, ind_c.marge, ind_c.taux_marge, ind_c.panier
ca_p, marge_p, taux_p, panier_p = ind_p.ca, ind_p.marge, ind_p.taux_marge, ind_p.panier

# ==================================================================
# BLOC KPI (toujours visible)
# ==================================================================
st.subheader(f"Indicateurs : {lib_mois(mois_ref)} comparé à {lib_mois(mois_cmp)}")
st.caption(
    f"Mois analysé : {lib_mois(mois_ref)} "
    f"({cur['date'].min():%d/%m/%Y} au {cur['date'].max():%d/%m/%Y}, {len(cur)} ventes). "
    f"Comparé {type_compa} : {lib_mois(mois_cmp)} ({len(cmp)} ventes).{periode_ref.note} "
    + (f"Montants hors taxes, TVA {config.TAUX_TVA * 100:.0f} % retirée des prix boutique."
       if config.TAUX_TVA else "Montants hors taxes.")
)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Chiffre d'affaires HT", eur(ca_c), delta(ca_c, ca_p))
k2.metric("Marge HT", eur(marge_c), delta(marge_c, marge_p))
k3.metric("Taux de marge", f"{taux_c:.1f} %",
          None if not taux_p else f"{taux_c - taux_p:+.1f} pts")
k4.metric("Panier moyen HT", f"{panier_c:.2f} €", delta(panier_c, panier_p))

# ----- Alertes catégories -----
# Triées par euros, pas par pourcentage : un dirigeant arbitre sur des montants.
st.markdown("##### 🔔 Alertes")
baisses, hausses = cal.alertes_categories(cur, cmp, SEUIL_ALERTE)
if not baisses and not hausses:
    st.info("Rien à signaler ce mois-ci, tout est stable.")
for alerte in baisses:
    st.error(alerte.phrase(type_compa) + " À regarder de près.", icon="⚠️")
for alerte in hausses:
    st.success(alerte.phrase(type_compa) + " Capitalise dessus.", icon="📈")

st.divider()

# ==================================================================
# ONGLETS
# ==================================================================
t_evo, t_mag, t_prod, t_hab, t_obj, t_prev = st.tabs(
    ["📈 Évolution", "🏬 Magasins", "📦 Produits", "🗓️ Habitudes", "🎯 Objectif",
     "🔮 Prévisions"])

# ---- Évolution mensuelle par magasin ----
with t_evo:
    st.markdown("**Chiffre d'affaires mensuel par magasin**")
    evo = (d.groupby(["mois", "magasin"])["ca"].sum().reset_index())
    fig = px.line(evo, x="mois", y="ca", color="magasin",
                  markers=True, color_discrete_map=COULEURS_MAG,
                  labels={"mois": "", "ca": "", "magasin": ""})
    # Axe en milliers (25k €) plutôt qu'en unités : un dirigeant lit un ordre
    # de grandeur, pas sept chiffres.
    fig.update_yaxes(ticksuffix=" €", tickformat="~s")
    # Étiquettes de mois en français, fabriquées à la main (voir mois_court).
    mois_axe = sorted(evo["mois"].unique())
    pas = max(1, len(mois_axe) // 9)
    reperes = mois_axe[::pas]
    fig.update_xaxes(tickmode="array", tickvals=list(reperes),
                     ticktext=[cal.mois_court(m) for m in reperes])
    fig.update_traces(line=dict(width=2), marker=dict(size=5),
                      hovertemplate="%{y:,.0f} €")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  x=0, title=""))
    st.plotly_chart(plotly_layout(fig), width="stretch")

# ---- Magasins : CA et marge ----
with t_mag:
    c1, c2 = st.columns(2)
    par_mag = d.groupby("magasin").agg(CA=("ca", "sum"), Marge=("marge", "sum")).reset_index()
    with c1:
        f1 = px.bar(par_mag, x="magasin", y="CA", color="magasin",
                    color_discrete_map=COULEURS_MAG, labels={"magasin": "", "CA": "CA"})
        f1.update_yaxes(ticksuffix=" €", tickformat=",.0f")
        f1.update_traces(hovertemplate="%{x} · %{y:,.0f} €", showlegend=False)
        st.markdown("**Chiffre d'affaires par magasin**")
        st.plotly_chart(plotly_layout(f1, 320), width="stretch")
    with c2:
        f2 = px.bar(par_mag, x="magasin", y="Marge", color="magasin",
                    color_discrete_map=COULEURS_MAG, labels={"magasin": "", "Marge": "Marge"})
        f2.update_yaxes(ticksuffix=" €", tickformat=",.0f")
        f2.update_traces(hovertemplate="%{x} · %{y:,.0f} €", showlegend=False)
        st.markdown("**Marge par magasin**")
        st.plotly_chart(plotly_layout(f2, 320), width="stretch")

    st.markdown("**Répartition du CA par catégorie et par magasin**")
    mix = d.groupby(["magasin", "categorie"])["ca"].sum().reset_index()
    f3 = px.bar(mix, x="magasin", y="ca", color="categorie",
                labels={"magasin": "", "ca": "CA", "categorie": "Catégorie"})
    f3.update_yaxes(ticksuffix=" €", tickformat=",.0f")
    st.plotly_chart(plotly_layout(f3, 340), width="stretch")

# ---- Produits : top et flop ----
with t_prod:
    perf = (d.groupby("produit")
              .agg(CA=("ca", "sum"), Quantité=("quantite", "sum"), Marge=("marge", "sum"))
              .reset_index())
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🏆 Top 10 produits (CA)**")
        top = perf.sort_values("CA", ascending=False).head(10)
        ft = px.bar(top.sort_values("CA"), x="CA", y="produit", orientation="h",
                    labels={"CA": "CA", "produit": ""})
        ft.update_xaxes(ticksuffix=" €", tickformat=",.0f")
        ft.update_traces(marker_color=COCKPIT["green"], hovertemplate="%{y} · %{x:,.0f} €")
        st.plotly_chart(plotly_layout(ft, 380), width="stretch")
    with c2:
        st.markdown("**🐢 Flop 10 produits (CA)**")
        flop = perf.sort_values("CA").head(10)
        ff = px.bar(flop.sort_values("CA", ascending=False), x="CA", y="produit",
                    orientation="h", labels={"CA": "CA", "produit": ""})
        ff.update_xaxes(ticksuffix=" €", tickformat=",.0f")
        ff.update_traces(marker_color=COCKPIT["red"], hovertemplate="%{y} · %{x:,.0f} €")
        st.plotly_chart(plotly_layout(ff, 380), width="stretch")

    st.markdown("**Contribution à la marge par catégorie**")
    marge_cat = d.groupby("categorie").agg(CA=("ca", "sum"), Marge=("marge", "sum")).reset_index()
    marge_cat["Taux"] = (marge_cat["Marge"] / marge_cat["CA"] * 100).round(1)
    fm = px.bar(marge_cat.sort_values("Marge"), x="Marge", y="categorie", orientation="h",
                color="Taux", color_continuous_scale=["#E4DFD3", COCKPIT["gold"], COCKPIT["navy"]],
                labels={"Marge": "Marge", "categorie": "", "Taux": "Taux %"})
    fm.update_xaxes(ticksuffix=" €", tickformat=",.0f")
    st.plotly_chart(plotly_layout(fm, 320), width="stretch")

# ---- Habitudes : jour de la semaine ----
with t_hab:
    st.markdown("**Chiffre d'affaires moyen par jour de la semaine**")
    par_jour = d.groupby("jour_sem")["ca"].sum().reindex(range(7), fill_value=0)
    par_jour.index = JOURS_FR
    fj = px.bar(x=par_jour.index, y=par_jour.values, labels={"x": "", "y": "CA"})
    fj.update_yaxes(ticksuffix=" €", tickformat=",.0f")
    fj.update_traces(marker_color="#3E6D9C", hovertemplate="%{x} · %{y:,.0f} €")
    st.plotly_chart(plotly_layout(fj, 340), width="stretch")
    meilleur = par_jour.idxmax()
    st.info(f"Jour le plus fort : **{meilleur}**. Idéal pour renforcer les équipes et les opérations commerciales.")

# ---- Objectif : réel vs cible ----
with t_obj:
    objectif = cal.objectif_du_mois(ca_p, OBJECTIF_CROISSANCE)
    if objectif:
        atteinte = ca_c / objectif * 100
        st.markdown(f"**{lib_mois(mois_ref)} : réel vs objectif** "
                    f"(objectif = {lib_mois(mois_cmp)} +{(OBJECTIF_CROISSANCE-1)*100:.0f} %)")
        comp = pd.DataFrame({"Type": ["Objectif", "Réel"], "Montant": [objectif, ca_c]})
        fo = px.bar(comp, x="Montant", y="Type", orientation="h",
                    color="Type", color_discrete_map={"Objectif": "#C9C2B4", "Réel": COCKPIT["navy"]},
                    labels={"Montant": "", "Type": ""})
        fo.update_xaxes(ticksuffix=" €", tickformat=",.0f")
        fo.update_traces(hovertemplate="%{y} · %{x:,.0f} €", showlegend=False)
        st.plotly_chart(plotly_layout(fo, 240), width="stretch")
        c1, c2 = st.columns(2)
        c1.metric("Objectif du mois", eur(objectif))
        c2.metric("Taux d'atteinte", f"{atteinte:.0f} %",
                  f"{atteinte-100:+.0f} pts vs objectif")
    else:
        st.info("Pas assez d'historique pour calculer un objectif sur cette sélection.")

# ---- Prévisions : CA des prochains mois ----
# Streamlit exécute le contenu de TOUS les onglets à chaque interaction. Sans
# ce cache, les trois modèles et leur backtest tournaient à chaque clic.
@st.cache_data(ttl=3600, show_spinner="Calcul de la prévision...")
def prevision(col: str | None, entite: str | None, horizon: int) -> dict:
    return cf.prevoir(df, col, entite, horizon)


@st.cache_data(ttl=3600, show_spinner="Calcul des prévisions par entité...")
def recapitulatif(col: str, horizon: int):
    return cf.recap_entites(df, col, horizon)


def graphe_prevision(r):
    """Historique + prévision + zone d'incertitude, charte navy/or."""
    h, fpast = r["history"], r["forecast"]
    fig = go.Figure()
    # zone d'incertitude
    fig.add_trace(go.Scatter(
        x=list(r["upper"].index) + list(r["lower"].index[::-1]),
        y=list(r["upper"].values) + list(r["lower"].values[::-1]),
        fill="toself", fillcolor="rgba(198,161,91,0.18)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        name="Incertitude (95 %)"))
    # historique
    fig.add_trace(go.Scatter(
        x=h.index, y=h.values, mode="lines+markers", name="Historique",
        line=dict(color=COCKPIT["navy"], width=2.5),
        hovertemplate="%{x|%b %Y} · %{y:,.0f} €<extra></extra>"))
    # raccord visuel historique -> prévision
    pont_x = [h.index[-1], fpast.index[0]]
    pont_y = [h.values[-1], fpast.values[0]]
    fig.add_trace(go.Scatter(x=pont_x, y=pont_y, mode="lines",
                             line=dict(color=COCKPIT["gold"], width=2.5, dash="dot"),
                             showlegend=False, hoverinfo="skip"))
    # prévision
    fig.add_trace(go.Scatter(
        x=fpast.index, y=fpast.values, mode="lines+markers", name="Prévision",
        line=dict(color=COCKPIT["gold"], width=2.5, dash="dot"),
        marker=dict(symbol="diamond", size=6),
        hovertemplate="%{x|%b %Y} · %{y:,.0f} € (prévu)<extra></extra>"))
    fig.update_yaxes(ticksuffix=" €", tickformat=",.0f")
    fig = plotly_layout(fig, 420)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0),
                      margin=dict(l=10, r=10, t=20, b=10))
    return fig


def bloc_prevision(r, libelle):
    c1, c2, c3 = st.columns(3)
    c1.metric("CA prévu · 12 prochains mois", eur(r["total_next"]),
              f"{r['growth']:+.1f} % vs 12 derniers mois")
    fiab = "—" if pd.isna(r["mape"]) else f"± {r['mape']:.1f} %"
    c2.metric("Fiabilité (erreur test)", fiab)
    c3.metric("Modèle retenu", r["model"])
    st.markdown(f"**Chiffre d'affaires — {libelle} : historique et prévision 12 mois**")
    st.plotly_chart(graphe_prevision(r), width="stretch")
    g = r["growth"]
    if g <= -2:
        st.error(f"⚠️ Tendance à la baisse anticipée : **{g:+.1f} %** sur 12 mois pour « {libelle} ». "
                 f"À anticiper dès maintenant.")
    elif g >= 2:
        st.success(f"📈 Croissance anticipée : **{g:+.1f} %** sur 12 mois pour « {libelle} ». "
                   f"Sécurise les stocks et les équipes des mois forts.")
    else:
        st.info(f"Activité stable anticipée pour « {libelle} » (**{g:+.1f} %** sur 12 mois).")

with t_prev:
    st.caption("Le Cockpit teste plusieurs modèles (saisonnier ajusté, régression Ridge + Fourier, "
               "tendance × saisonnalité) et retient le plus fiable sur l'historique récent. "
               "Prévision sur 12 mois, en euros hors taxes.")
    st.info(
        "Cet onglet travaille sur **tout l'historique**, sans tenir compte des filtres du haut : "
        "une prévision a besoin de la série complète. Choisis le périmètre ci-dessous.",
        icon="ℹ️",
    )
    vue = st.radio("Niveau d'analyse", ["Global", "Par magasin", "Par catégorie"],
                   horizontal=True, key="vue_prev")
    if vue == "Global":
        bloc_prevision(prevision(None, None, config.HORIZON_PREVISION), "toutes boutiques")
    else:
        col = "magasin" if vue == "Par magasin" else "categorie"
        choix = sorted(df[col].dropna().unique())
        ent = st.selectbox(vue.replace("Par ", "").capitalize(), choix, key=f"sel_{col}")
        bloc_prevision(prevision(col, ent, config.HORIZON_PREVISION), str(ent))
        st.markdown(f"**Récapitulatif — {vue.lower()}**")
        recap = recapitulatif(col, config.HORIZON_PREVISION).copy()
        recap["CA prévu 12 mois"] = recap["CA prévu 12 mois"].map(lambda v: eur(v))
        recap["Croissance"] = recap["Croissance"].map(lambda v: f"{v:+.1f} %")
        recap["Fiabilité (MAPE)"] = recap["Fiabilité (MAPE)"].map(
            lambda v: "—" if pd.isna(v) else f"± {v:.1f} %")
        st.dataframe(recap, width="stretch", hide_index=True)

# ==================================================================
# EXPORT
# ==================================================================
st.divider()
# L'export n'existe que si on l'a demandé (config.EXPORT_AUTORISE), et alors
# seulement pour les profils qui en ont le droit.
if reglage("EXPORT_AUTORISE", False):
    if autorise_a("exporter"):
        st.download_button("⬇️ Télécharger les données filtrées (CSV)",
                           data=d.to_csv(index=False).encode("utf-8"),
                           file_name="export_maison_lauret.csv", mime="text/csv")
    else:
        st.caption("L'export des données n'est pas ouvert à votre profil.")

# ==================================================================
# PANNEAUX RÉSERVÉS (diagnostic, administration)
# ==================================================================
if autorise_a("diagnostic"):
    with st.expander("🔧 État technique"):
        table_sf = reglage("TABLE_SNOWFLAKE", "")
        dans_sf = src.session_snowflake() is not None
        repli = st.session_state.get("_repli_fichier")
        if dans_sf and table_sf and not repli:
            source = "entrepôt Snowflake"
            origine = table_sf
            etiquette_origine = ("Vue sécurisée" if "PAR_ROLE" in table_sf.upper()
                                 else "Table")
        else:
            etiquette_origine = "Fichier ou base"
            source = getattr(config, "SOURCE", "csv")
            origine = (Path(str(config.DATA_FILE)).name
                       if source in ("csv", "excel") else source)
        lignes = f"{len(df):,}".replace(",", " ")
        import plotly as _plotly        # juste pour la version affichée
        versions = (f"Streamlit {st.__version__}, pandas {pd.__version__}, "
                    f"Plotly {_plotly.__version__}")
        types = ", ".join(f"{c} : {d[c].dtype}" for c in ("ca", "marge", "mois")
                          if c in d.columns)
        gauche_t, droite_t = st.columns(2)
        gauche_t.markdown(
            "\n".join([
                f"**Source** : {source}",
                f"**{etiquette_origine}** : {origine}",
                f"**TVA appliquée** : {reglage('TAUX_TVA', 0.20) * 100:.0f} %",
                f"**Régénération auto** : {'oui' if reglage('DEMO_AUTO', True) else 'non'}",
            ])
        )
        droite_t.markdown(
            "\n".join([
                f"**Lignes lues** : {lignes}",
                f"**Période** : du {df['date'].min():%d/%m/%Y} "
                f"au {df['date'].max():%d/%m/%Y}",
                ("**Lecture de l'entrepôt** : "
                 f"{df.attrs['duree_ms']} ms" if df.attrs.get("duree_ms")
                 else "**Relecture** : au plus une fois par heure (cache)"),
                f"**Profils chargés** : {len(PROFILS) if PROFILS else 'aucun'}",
            ])
        )
        # Les versions et les types : ce sont eux qui expliquent une figure
        # qui ne rend pas pareil d'un hébergement à l'autre.
        if df.attrs.get("lu_a"):
            # L'ancienneté plutôt que l'heure : l'horloge du serveur Snowflake
            # n'est pas celle du client, et une heure fausse à l'écran coûte
            # plus cher en confiance qu'elle ne rapporte en précision.
            age = max(0, int(time.time() - df.attrs["lu_a"]))
            quand = f"il y a {age} s" if age < 90 else f"il y a {age // 60} min"
            st.caption(f"Entrepôt lu {quand}, relecture automatique toutes "
                       f"les {FRAICHEUR // 60} minutes.")
        if st.button("Relire maintenant", icon="🔄",
                     help="Sans attendre la prochaine actualisation."):
            st.cache_data.clear()
            st.rerun()
        if st.session_state.get("_repli_fichier"):
            st.caption("Repli sur le fichier : "
                       + st.session_state["_repli_fichier"][:160])
        st.caption(f"Versions : {versions}")
        st.caption(f"Types des colonnes : {types}")
        # Les contrôles tournent dans l'entrepôt, pas ici : c'est son métier,
        # et la réponse tient en une ligne au lieu de traverser le réseau.
        if dans_sf and table_sf and not repli:
            @st.cache_data(ttl=reglage("FRAICHEUR_S", 300), show_spinner=False)
            def controles(objet: str):
                try:
                    return src.controle_qualite(objet)
                except Exception as erreur:
                    return {"erreur": str(erreur)}

            q = controles(table_sf)
            if q and "erreur" not in q:
                anomalies = (int(q["dates_manquantes"]) + int(q["montants_negatifs"])
                             + int(q["quantites_nulles"]))
                st.markdown("**Contrôles exécutés dans l'entrepôt**")
                resume = (f"{int(q['lignes']):,} lignes · {int(q['magasins'])} magasins"
                          f" · {int(q['categories'])} catégories · dernier jour "
                          f"{pd.Timestamp(q['dernier_jour']):%d/%m/%Y}")
                st.caption(resume.replace(",", " "))
                detail = (f"dates manquantes : {int(q['dates_manquantes'])} · "
                          f"montants négatifs : {int(q['montants_negatifs'])} · "
                          f"quantités nulles ou négatives : {int(q['quantites_nulles'])}")
                if anomalies:
                    st.warning(f"{anomalies} ligne(s) à regarder — {detail}", icon="⚠️")
                else:
                    st.caption(f"Aucune anomalie — {detail}")
        # La requête, telle qu'elle part dans l'entrepôt. Un informaticien
        # veut la lire avant d'ouvrir un accès : autant la montrer.
        if df.attrs.get("requete"):
            st.markdown("**La requête exécutée dans l'entrepôt**")
            st.code(df.attrs["requete"], language="sql")
            if "MAGASIN IN" in df.attrs["requete"]:
                st.caption("Le périmètre du compte est dans la requête : "
                           "les lignes des autres magasins ne sortent jamais "
                           "de l'entrepôt.")

# ------------------------------------------------------------------
# Gérer les personnes depuis l'écran
# ------------------------------------------------------------------
ETIQUETTES_ROLE = {
    "lecteur": "lecteur : consulte son périmètre",
    "contributeur": "contributeur : consulte, exporte, règle l'objectif",
    "admin": "administrateur : tout, y compris les comptes",
}


def _apres_ecriture(texte: str, bon: bool = True) -> None:
    """Garde le message, garde le panneau ouvert, et relance l'écran.

    Sans le rechargement, la liste affichée resterait celle d'avant la
    modification : un administrateur ne doit pas avoir à deviner si son
    clic a été pris en compte.
    """
    st.session_state["_comptes_message"] = ("ok" if bon else "ko", texte)
    st.session_state["_comptes_ouvert"] = True
    st.rerun()


def gestion_des_comptes(donnees: pd.DataFrame) -> None:
    """Créer, modifier et retirer des personnes, sans toucher au code.

    Le droit est revérifié ici : une protection qui dépend de l'endroit d'où
    on appelle la fonction n'en est pas une. Aucun rechargement de page après
    une écriture, sinon le panneau se refermerait sous les doigts de
    l'administrateur ; la liste est relue et réaffichée à la place.
    """
    if profil is not None and not profil.peut("administrer"):
        return

    magasins_connus = sorted(str(m) for m in donnees["magasin"].dropna().unique())
    ajout, entretien = st.tabs(["➕ Ajouter une personne", "✏️ Modifier ou retirer"])

    with ajout:
        with st.form("ajout_compte", clear_on_submit=True):
            c1, c2 = st.columns(2)
            identifiant = c1.text_input("Identifiant", placeholder="marie")
            nom = c2.text_input("Nom affiché", placeholder="Marie Dupont")
            c3, c4 = st.columns(2)
            role = c3.selectbox("Rôle", list(perm.ROLES),
                                format_func=lambda r: ETIQUETTES_ROLE.get(r, r))
            perimetre = c4.multiselect("Magasins (vide : tout voir)",
                                       magasins_connus)
            mdp = st.text_input("Mot de passe, huit caractères au minimum",
                                type="password")
            if st.form_submit_button("Créer la personne", type="primary"):
                try:
                    comptes.ajoute(identifiant, nom, role, mdp, magasins=perimetre)
                except comptes.CompteInvalide as erreur:
                    st.error(str(erreur), icon="🚫")
                else:
                    _apres_ecriture(f"« {identifiant.strip().lower()} » peut "
                                    "maintenant se connecter.")

    with entretien:
        lignes = comptes.lire()
        if not lignes:
            st.info("Aucun compte dans la table.")
            return
        noms = [l["identifiant"] for l in lignes]
        qui = st.selectbox("Personne", noms, key="_compte_choisi")
        ligne = next(l for l in lignes if l["identifiant"] == qui)
        actif = bool(ligne.get("actif", True))

        c1, c2 = st.columns(2)
        role_actuel = ligne.get("role") or "lecteur"
        nouveau_role = c1.selectbox(
            "Rôle", list(perm.ROLES),
            index=list(perm.ROLES).index(role_actuel) if role_actuel in perm.ROLES else 0,
            format_func=lambda r: ETIQUETTES_ROLE.get(r, r), key="_role_modif")
        nouveau_perimetre = c2.multiselect(
            "Magasins (vide : tout voir)", magasins_connus,
            default=[m for m in comptes._liste(ligne.get("magasins"))
                     if m in magasins_connus], key="_perimetre_modif")
        if st.button("Enregistrer le rôle et le périmètre", key="_enregistre"):
            try:
                comptes.modifie(qui, role=nouveau_role, magasins=nouveau_perimetre)
            except comptes.CompteInvalide as erreur:
                st.error(str(erreur), icon="🚫")
            else:
                _apres_ecriture(f"« {qui} » mis à jour.")

        st.divider()
        c3, c4 = st.columns([2, 1])
        neuf = c3.text_input("Nouveau mot de passe", type="password", key="_mdp_reset")
        if c4.button("Réinitialiser", key="_bouton_reset"):
            try:
                comptes.change_mot_de_passe(qui, neuf)
            except comptes.CompteInvalide as erreur:
                st.error(str(erreur), icon="🚫")
            else:
                _apres_ecriture(f"Nouveau mot de passe actif pour « {qui} ».")

        c5, c6 = st.columns(2)
        if c5.button("Réactiver l'accès" if not actif else "Couper l'accès",
                     key="_bascule"):
            try:
                comptes.active(qui, not actif)
            except comptes.CompteInvalide as erreur:
                st.error(str(erreur), icon="🚫")
            else:
                _apres_ecriture(f"Accès {'rendu' if not actif else 'coupé'} "
                                f"pour « {qui} ».")
        confirme = c6.checkbox("Je veux supprimer définitivement", key="_confirme")
        if c6.button("Supprimer", key="_supprime", disabled=not confirme):
            try:
                comptes.supprime(qui)
            except comptes.CompteInvalide as erreur:
                st.error(str(erreur), icon="🚫")
            else:
                _apres_ecriture(f"« {qui} » a été supprimé.")

        st.caption("Couper l'accès vaut mieux que supprimer : la personne ne peut "
                   "plus se connecter, et son historique reste.")
        st.dataframe(
            pd.DataFrame([
                {"Identifiant": l["identifiant"], "Nom": l["nom"],
                 "Rôle": l["role"],
                 "Périmètre": ", ".join(comptes._liste(l.get("magasins"))) or "tout",
                 "Actif": "oui" if l.get("actif", True) else "non"}
                for l in comptes.lire()
            ]),
            hide_index=True, width="stretch",
        )


if autorise_a("administrer") and PROFILS:
    with st.expander("👤 Comptes et périmètres",
                     expanded=bool(st.session_state.get("_comptes_ouvert"))):
        # Une écriture relance la page, ce qui refermerait le panneau et
        # ferait disparaître la confirmation sous les doigts de
        # l'administrateur. On garde donc l'état et le message de côté.
        message = st.session_state.pop("_comptes_message", None)
        if message:
            (st.success if message[0] == "ok" else st.error)(message[1])
        st.dataframe(
            pd.DataFrame([
                {"Identifiant": p.identifiant, "Nom": p.nom, "Rôle": p.role,
                 "Périmètre": "tout" if p.voit_tout else p.resume().replace("Périmètre, ", "")}
                for p in PROFILS.values()
            ]),
            hide_index=True, width="stretch",
        )
        if not COMPTES_EN_BASE:
            st.caption("Les comptes se modifient dans **profils.json**, à côté du "
                       "code. Ce fichier n'est jamais versionné.")
            st.markdown("**Fabriquer l'empreinte d'un mot de passe**")
            mot = st.text_input("Mot de passe à transformer", type="password",
                                key="_empreinte")
            if mot:
                st.code(perm.empreinte(mot), language="text")
                st.caption("À recopier dans le champ « empreinte » du profil. "
                           "Le mot de passe en clair n'est stocké nulle part.")
        else:
            st.caption(f"Les comptes sont rangés dans la table "
                       f"**{comptes.TABLE_COMPTES}**. Le mot de passe n'y est "
                       "jamais écrit : seule son empreinte l'est.")
            gestion_des_comptes(df)

# ------------------------------------------------------------------
# Actualisation automatique
# ------------------------------------------------------------------
# Personne ne doit cliquer pour voir les chiffres du jour. Ce bloc minuscule
# se réveille tout seul, regarde l'âge de la lecture, et relance l'écran quand
# elle a dépassé le délai. Entre deux réveils il ne redessine que lui-même :
# la page ne clignote pas pendant une démonstration.
if FRAICHEUR and df.attrs.get("lu_a"):

    @st.fragment(run_every=30)
    def actualisation_automatique():
        if time.time() - df.attrs["lu_a"] > FRAICHEUR:
            st.cache_data.clear()
            st.rerun(scope="app")

    actualisation_automatique()

footer("Le Cockpit — démonstrateur réalisé par Alexis Zueras · Data Analyst · Python / Power BI / SQL")
