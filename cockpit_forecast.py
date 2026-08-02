"""
cockpit_forecast.py — Moteur de prévision du Cockpit
====================================================
Prévoit le chiffre d'affaires des prochains mois (global, par magasin ou par
catégorie). Le moteur teste PLUSIEURS modèles et retient automatiquement celui
qui prédit le mieux l'historique récent (backtest), série par série.

Modèles candidats :
  1. Saisonnier-naïf ajusté (même mois l'an dernier × croissance annuelle)
  2. Régression Ridge sur log(CA) + saisonnalité de Fourier
  3. Tendance log-linéaire × profil saisonnier mensuel

Le meilleur est choisi par erreur de backtest (MAPE) sur les derniers mois.
Aucune donnée réelle client : conçu pour la démo Maison Lauret et réutilisable.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


# ==================================================================
# Régression Ridge (numpy, sans dépendance externe)
# ==================================================================
def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Ridge en forme fermée : w = (XᵀX + αI)⁻¹Xᵀy. L'intercept n'est pas pénalisé."""
    n = X.shape[0]
    Xb = np.column_stack([np.ones(n), X])          # colonne d'intercept
    reg = np.eye(Xb.shape[1]) * alpha
    reg[0, 0] = 0.0                                 # on ne régularise pas l'intercept
    return np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)


def _ridge_predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(X.shape[0]), X]) @ w


# ==================================================================
# Utilitaires
# ==================================================================
def serie_mensuelle(df: pd.DataFrame, group_col: str | None = None,
                    entity: str | None = None,
                    date_col: str = "date", val_col: str = "ca_ttc") -> pd.Series:
    """Agrège les transactions en série mensuelle de CA (filtrée sur une entité)."""
    d = df
    if group_col and entity is not None:
        d = d[d[group_col] == entity]
    s = (d.set_index(pd.to_datetime(d[date_col]))[val_col]
           .resample("MS").sum().sort_index())
    return s


def _mois_index(idx, t0):
    return np.array([(d.year - t0.year) * 12 + (d.month - t0.month) for d in idx], float)


# ==================================================================
# Modèles candidats  ->  renvoient une Series de prévision (valeurs centrales)
# ==================================================================
def _m_snaive(s: pd.Series, horizon: int) -> pd.Series:
    """Saisonnier-naïf : mois M+12 = mois M × croissance annuelle (moy. géométrique)."""
    s = s.sort_index()
    if len(s) >= 13:
        ratios = [s.iloc[i] / s.iloc[i - 12]
                  for i in range(12, len(s)) if s.iloc[i - 12] > 0]
        g = float(np.exp(np.mean(np.log(ratios)))) if ratios else 1.0
    else:
        g = 1.0
    last12 = s.iloc[-12:].values
    n = len(last12)
    fut = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    vals = [last12[i % n] * g for i in range(horizon)]
    return pd.Series(vals, fut)


def _m_fourier(s: pd.Series, horizon: int, n_harm: int = 3, alpha: float = 1.0) -> pd.Series:
    s = s.sort_index(); t0 = s.index[0]

    def X(idx):
        t = _mois_index(idx, t0)
        m = np.array([d.month for d in idx], float)
        f = [t]
        for k in range(1, n_harm + 1):
            f += [np.sin(2 * np.pi * k * m / 12), np.cos(2 * np.pi * k * m / 12)]
        return np.column_stack(f)

    y = np.log(np.maximum(s.values, 1e-9))
    w = _ridge_fit(X(s.index), y, alpha)
    fut = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return pd.Series(np.exp(_ridge_predict(w, X(fut))), fut)


def _m_seasonal(s: pd.Series, horizon: int) -> pd.Series:
    s = s.sort_index(); t0 = s.index[0]
    t = _mois_index(s.index, t0)
    y = np.log(np.maximum(s.values, 1e-9))
    b = np.polyfit(t, y, 1)
    prof = pd.Series(s.values / np.exp(np.polyval(b, t)),
                     index=[d.month for d in s.index]).groupby(level=0).mean()
    prof = prof / prof.mean()
    fut = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    tf = _mois_index(fut, t0)
    tr = np.exp(np.polyval(b, tf))
    vals = [tr[i] * prof.get(d.month, 1.0) for i, d in enumerate(fut)]
    return pd.Series(vals, fut)


_MODELES = {
    "Saisonnier ajusté": _m_snaive,
    "Ridge + Fourier": _m_fourier,
    "Tendance × saisonnalité": _m_seasonal,
}


# ==================================================================
# Backtest & sélection automatique
# ==================================================================
def _mape(reel: np.ndarray, prev: np.ndarray) -> float:
    reel = np.asarray(reel, float); prev = np.asarray(prev, float)
    ok = reel > 0
    return float(np.mean(np.abs(reel[ok] - prev[ok]) / reel[ok]) * 100) if ok.any() else np.nan


def _choisir_modele(s: pd.Series, test_h: int = 3):
    """Retourne (nom, fonction, mape) du meilleur modèle sur les derniers mois."""
    if len(s) <= test_h + 2:
        return "Saisonnier ajusté", _m_snaive, np.nan
    train, test = s.iloc[:-test_h], s.iloc[-test_h:]
    best = None
    for nom, fn in _MODELES.items():
        try:
            prev = fn(train, test_h).values
            score = _mape(test.values, prev)
        except Exception:
            score = np.nan
        if not np.isnan(score) and (best is None or score < best[2]):
            best = (nom, fn, score)
    return best or ("Saisonnier ajusté", _m_snaive, np.nan)


def _bande(s: pd.Series, horizon: int, fut_idx) -> float:
    """Écart-type (log) pour l'intervalle : dispersion des variations annuelles."""
    if len(s) >= 14:
        lr = np.log([s.iloc[i] / s.iloc[i - 12]
                     for i in range(12, len(s)) if s.iloc[i - 12] > 0])
        sig = float(np.std(lr, ddof=1)) if len(lr) > 1 else 0.12
    else:
        sig = 0.12
    return max(sig, 0.03)


def prevoir(df: pd.DataFrame, group_col: str | None = None, entity: str | None = None,
            horizon: int = 12) -> dict:
    """
    Prévision de CA pour une entité (globale si group_col=None).

    Retour : dict avec history, forecast, lower, upper (Series), model (str),
    mape (float %), growth (%), total_next, total_prev.
    """
    s = serie_mensuelle(df, group_col, entity)
    s = s[s.index.notna()]
    nom, fn, mape = _choisir_modele(s)
    fc = fn(s, horizon)
    fc = fc.clip(lower=0)
    sig = _bande(s, horizon, fc.index)
    widen = np.sqrt(1 + np.arange(1, horizon + 1) / horizon)
    lower = (fc.values * np.exp(-1.96 * sig * widen)).clip(min=0)
    upper = fc.values * np.exp(1.96 * sig * widen)
    total_prev = float(s.iloc[-12:].sum())
    total_next = float(fc.iloc[:12].sum())
    growth = (total_next / total_prev - 1) * 100 if total_prev else 0.0
    return {
        "history": s,
        "forecast": fc,
        "lower": pd.Series(lower, fc.index),
        "upper": pd.Series(upper, fc.index),
        "model": nom,
        "mape": mape,
        "growth": growth,
        "total_next": total_next,
        "total_prev": total_prev,
    }


def recap_entites(df: pd.DataFrame, group_col: str, horizon: int = 12) -> pd.DataFrame:
    """Tableau récap : par entité, CA prévu 12 mois, croissance %, modèle, fiabilité."""
    lignes = []
    for ent in sorted(df[group_col].dropna().unique()):
        r = prevoir(df, group_col, ent, horizon)
        lignes.append({
            group_col.capitalize(): ent,
            "CA prévu 12 mois": round(r["total_next"]),
            "Croissance": round(r["growth"], 1),
            "Modèle retenu": r["model"],
            "Fiabilité (MAPE)": round(r["mape"], 1) if not np.isnan(r["mape"]) else None,
        })
    return pd.DataFrame(lignes).sort_values("CA prévu 12 mois", ascending=False)
