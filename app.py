"""
Le Cockpit — Maison Lauret (démo)
=================================
Tableau de bord de pilotage. Données 100% fictives.
Démonstrateur de l'offre "Le Cockpit" — Alexis Zueras.

Lancer :  streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from cockpit_theme import (
    apply_theme, splash, header, footer, plotly_layout, COCKPIT,
)
import cockpit_forecast as cf
import config   # variables externalisées (données, paramètres, secrets) hors du code

# ==================================================================
# CONFIG & CONSTANTES
# ==================================================================
st.set_page_config(page_title="Le Cockpit · Maison Lauret",
                   page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

apply_theme()                                    # 1. charte navy/or
splash("Le Cockpit",                             # 2. écran d'ouverture animé
       sous_titre="Maison Lauret · Pilotage",
       video=str(config.SPLASH_VIDEO))           # vidéo Gemini si présente, sinon anim CSS

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# Couleurs magasins harmonisées à la charte navy / or
COULEURS_MAG = {"Toulouse": COCKPIT["navy"],
                "Auch": COCKPIT["gold"],
                "Montauban": "#3E6D9C"}
OBJECTIF_CROISSANCE = config.OBJECTIF_CROISSANCE   # objectif vs même mois l'an dernier

def eur(x):                  # formatage français : 1 234 €
    return f"{x:,.0f} €".replace(",", " ")

# ==================================================================
# DONNÉES
# ==================================================================
@st.cache_data
def charger_donnees():
    df = pd.read_csv(config.DATA_FILE, parse_dates=["date"])
    df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["jour_sem"] = df["date"].dt.dayofweek
    return df

df = charger_donnees()

# En-tête (toujours affiché)
header("Maison Lauret",
       "Concept store déco-maison · 3 boutiques (Toulouse, Auch, Montauban) · données de démonstration")

# ==================================================================
# FILTRES (panneau repliable, masqué par défaut)
# ==================================================================
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
def lib_mois(ts):
    return f"{MOIS_FR[ts.month - 1]} {ts.year}" if pd.notna(ts) else "—"

mois_ref = d["mois"].max()
cur = d[d["mois"] == mois_ref]

mois_cmp = mois_ref - pd.DateOffset(years=1)
cmp = d[d["mois"] == mois_cmp]
type_compa = "au même mois un an avant"
if cmp.empty:
    mois_cmp = d.loc[d["mois"] < mois_ref, "mois"].max()
    cmp = d[d["mois"] == mois_cmp] if pd.notna(mois_cmp) else cur.iloc[0:0]
    type_compa = "au mois précédent disponible"

def kpis(x):
    ca = x["ca_ttc"].sum(); marge = x["marge"].sum()
    return ca, marge, (marge / ca * 100 if ca else 0), (ca / len(x) if len(x) else 0)

ca_c, marge_c, taux_c, panier_c = kpis(cur)
ca_p, marge_p, taux_p, panier_p = kpis(cmp)

def delta(c, p, suff="%"):
    return None if not p else f"{(c - p) / p * 100:+.1f}{suff}"

# ==================================================================
# BLOC KPI (toujours visible)
# ==================================================================
st.subheader(f"Indicateurs : {lib_mois(mois_ref)} comparé à {lib_mois(mois_cmp)}")
st.caption(
    f"Mois analysé : {lib_mois(mois_ref)} "
    f"({cur['date'].min():%d/%m/%Y} au {cur['date'].max():%d/%m/%Y}, {len(cur)} ventes). "
    f"Comparé {type_compa} : {lib_mois(mois_cmp)} ({len(cmp)} ventes)."
)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Chiffre d'affaires", eur(ca_c), delta(ca_c, ca_p))
k2.metric("Marge", eur(marge_c), delta(marge_c, marge_p))
k3.metric("Taux de marge", f"{taux_c:.1f} %",
          None if not taux_p else f"{taux_c - taux_p:+.1f} pts")
k4.metric("Panier moyen", f"{panier_c:.2f} €", delta(panier_c, panier_p))

# ----- Alertes catégories -----
st.markdown("##### 🔔 Alertes")
SEUIL = config.SEUIL_ALERTE
cc = cur.groupby("categorie")["ca_ttc"].sum()
cp = cmp.groupby("categorie")["ca_ttc"].sum()
baisses, hausses = [], []
for cat in cc.index:
    p = cp.get(cat, 0)
    if p > 0:
        v = (cc[cat] - p) / p * 100
        if v <= -SEUIL:
            baisses.append((cat, v))
        elif v >= SEUIL:
            hausses.append((cat, v))
if not baisses and not hausses:
    st.info("Rien à signaler ce mois-ci, tout est stable.")
for cat, v in sorted(baisses, key=lambda t: t[1]):
    st.error(f"⚠️ **{cat}** recule de {v:.1f} % {type_compa.replace('au ', 'vs ')}. À regarder de près.")
for cat, v in sorted(hausses, key=lambda t: -t[1]):
    st.success(f"📈 **{cat}** progresse de +{v:.1f} %. Capitalise dessus.")

st.divider()

# ==================================================================
# ONGLETS
# ==================================================================
t_evo, t_mag, t_prod, t_hab, t_obj, t_prev = st.tabs(
    ["📈 Évolution", "🏬 Magasins", "📦 Produits", "🗓️ Habitudes", "🎯 Objectif",
     "🔮 Prévisions"])

# ---- Évolution mensuelle par magasin ----
with t_evo:
    evo = (d.groupby(["mois", "magasin"])["ca_ttc"].sum().reset_index())
    fig = px.line(evo, x="mois", y="ca_ttc", color="magasin",
                  markers=True, color_discrete_map=COULEURS_MAG,
                  labels={"mois": "", "ca_ttc": "CA", "magasin": "Magasin"})
    fig.update_yaxes(tickprefix="", ticksuffix=" €", tickformat=",.0f")
    fig.update_traces(hovertemplate="%{x|%b %Y} · %{y:,.0f} €")
    st.plotly_chart(plotly_layout(fig), width="stretch")

# ---- Magasins : CA et marge ----
with t_mag:
    c1, c2 = st.columns(2)
    par_mag = d.groupby("magasin").agg(CA=("ca_ttc", "sum"), Marge=("marge", "sum")).reset_index()
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
    mix = d.groupby(["magasin", "categorie"])["ca_ttc"].sum().reset_index()
    f3 = px.bar(mix, x="magasin", y="ca_ttc", color="categorie",
                labels={"magasin": "", "ca_ttc": "CA", "categorie": "Catégorie"})
    f3.update_yaxes(ticksuffix=" €", tickformat=",.0f")
    st.plotly_chart(plotly_layout(f3, 340), width="stretch")

# ---- Produits : top et flop ----
with t_prod:
    perf = (d.groupby("produit")
              .agg(CA=("ca_ttc", "sum"), Quantité=("quantite", "sum"), Marge=("marge", "sum"))
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
    marge_cat = d.groupby("categorie").agg(CA=("ca_ttc", "sum"), Marge=("marge", "sum")).reset_index()
    marge_cat["Taux"] = (marge_cat["Marge"] / marge_cat["CA"] * 100).round(1)
    fm = px.bar(marge_cat.sort_values("Marge"), x="Marge", y="categorie", orientation="h",
                color="Taux", color_continuous_scale=["#E4DFD3", COCKPIT["gold"], COCKPIT["navy"]],
                labels={"Marge": "Marge", "categorie": "", "Taux": "Taux %"})
    fm.update_xaxes(ticksuffix=" €", tickformat=",.0f")
    st.plotly_chart(plotly_layout(fm, 320), width="stretch")

# ---- Habitudes : jour de la semaine ----
with t_hab:
    st.markdown("**Chiffre d'affaires moyen par jour de la semaine**")
    par_jour = d.groupby("jour_sem")["ca_ttc"].sum().reindex(range(7), fill_value=0)
    par_jour.index = JOURS_FR
    fj = px.bar(x=par_jour.index, y=par_jour.values, labels={"x": "", "y": "CA"})
    fj.update_yaxes(ticksuffix=" €", tickformat=",.0f")
    fj.update_traces(marker_color="#3E6D9C", hovertemplate="%{x} · %{y:,.0f} €")
    st.plotly_chart(plotly_layout(fj, 340), width="stretch")
    meilleur = par_jour.idxmax()
    st.info(f"Jour le plus fort : **{meilleur}**. Idéal pour renforcer les équipes et les opérations commerciales.")

# ---- Objectif : réel vs cible ----
with t_obj:
    objectif = ca_p * OBJECTIF_CROISSANCE if ca_p else None
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
               "Prévision sur 12 mois, basée sur tout l'historique disponible.")
    vue = st.radio("Niveau d'analyse", ["Global", "Par magasin", "Par catégorie"],
                   horizontal=True, key="vue_prev")
    if vue == "Global":
        bloc_prevision(cf.prevoir(df, None, None, config.HORIZON_PREVISION), "toutes boutiques")
    else:
        col = "magasin" if vue == "Par magasin" else "categorie"
        choix = sorted(df[col].dropna().unique())
        ent = st.selectbox(vue.replace("Par ", "").capitalize(), choix, key=f"sel_{col}")
        bloc_prevision(cf.prevoir(df, col, ent, config.HORIZON_PREVISION), str(ent))
        st.markdown(f"**Récapitulatif — {vue.lower()}**")
        recap = cf.recap_entites(df, col, config.HORIZON_PREVISION).copy()
        recap["CA prévu 12 mois"] = recap["CA prévu 12 mois"].map(lambda v: eur(v))
        recap["Croissance"] = recap["Croissance"].map(lambda v: f"{v:+.1f} %")
        recap["Fiabilité (MAPE)"] = recap["Fiabilité (MAPE)"].map(
            lambda v: "—" if pd.isna(v) else f"± {v:.1f} %")
        st.dataframe(recap, width="stretch", hide_index=True)

# ==================================================================
# EXPORT
# ==================================================================
st.divider()
st.download_button("⬇️ Télécharger les données filtrées (CSV)",
                   data=d.to_csv(index=False).encode("utf-8"),
                   file_name="export_maison_lauret.csv", mime="text/csv")
footer("Le Cockpit — démonstrateur réalisé par Alexis Zueras · Data Analyst · Python / Power BI / SQL")
