"""
Le Cockpit — Maison Lauret (démo)
=================================
Tableau de bord de pilotage. Données 100% fictives.
Démonstrateur de l'offre "Le Cockpit" — Alexis Zueras.

Lancer :  streamlit run app.py
"""
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
import cockpit_calculs as cal   # tous les calculs, testés dans test_cockpit.py
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

# Verrou : connexion nominative s'il existe un fichier de profils, sinon mot de
# passe unique s'il est configuré, sinon rien (c'est le cas de la démonstration).
PROFILS = perm.charge_profils()
autorise, profil = acces.session(PROFILS, config.ACCESS_PASSWORD,
                                 enseigne="Maison Lauret")
if not autorise:
    st.stop()


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


@st.cache_data(ttl=3600)
def charger_donnees(chemin: str, taux_tva: float, demo_auto: bool):
    """Lit le fichier de caisse, le contrôle, et ramène les montants hors taxes.

    Renvoie (données, problème). `problème` est une phrase en français destinée
    au visiteur : si le fichier change ou disparaît, il voit un message, jamais
    une erreur Python.

    Convention de prix : le fichier contient des prix boutique, donc TTC. Tout
    ce qui est affiché est hors taxes (`config.TAUX_TVA`). Le coût d'achat est
    déjà hors taxes, parce que le commerçant récupère la TVA sur ses achats.
    """
    chemin = Path(chemin)
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
df, probleme = charger_donnees(str(config.DATA_FILE), config.TAUX_TVA, config.DEMO_AUTO)
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
if config.EXPORT_AUTORISE:
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
                f"**Fichier ou base** : {origine}",
                f"**TVA appliquée** : {config.TAUX_TVA * 100:.0f} %",
                f"**Régénération auto** : {'oui' if config.DEMO_AUTO else 'non'}",
            ])
        )
        droite_t.markdown(
            "\n".join([
                f"**Lignes lues** : {lignes}",
                f"**Période** : du {df['date'].min():%d/%m/%Y} "
                f"au {df['date'].max():%d/%m/%Y}",
                "**Relecture** : au plus une fois par heure (cache)",
                f"**Profils chargés** : {len(PROFILS) if PROFILS else 'aucun'}",
            ])
        )
        # Les versions et les types : ce sont eux qui expliquent une figure
        # qui ne rend pas pareil d'un hébergement à l'autre.
        st.caption(f"Versions : {versions}")
        st.caption(f"Types des colonnes : {types}")

if autorise_a("administrer") and PROFILS:
    with st.expander("👤 Comptes et périmètres"):
        st.dataframe(
            pd.DataFrame([
                {"Identifiant": p.identifiant, "Nom": p.nom, "Rôle": p.role,
                 "Périmètre": "tout" if p.voit_tout else p.resume().replace("Périmètre, ", "")}
                for p in PROFILS.values()
            ]),
            hide_index=True, width="stretch",
        )
        st.caption("Les comptes se modifient dans **profils.json**, à côté du code. "
                   "Ce fichier n'est jamais versionné.")
        st.markdown("**Fabriquer l'empreinte d'un mot de passe**")
        mot = st.text_input("Mot de passe à transformer", type="password",
                            key="_empreinte")
        if mot:
            st.code(perm.empreinte(mot), language="text")
            st.caption("À recopier dans le champ « empreinte » du profil. "
                       "Le mot de passe en clair n'est stocké nulle part.")

footer("Le Cockpit — démonstrateur réalisé par Alexis Zueras · Data Analyst · Python / Power BI / SQL")
