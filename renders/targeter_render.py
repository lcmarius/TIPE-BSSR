"""Rendus visuels liés au targeter (TIPE BSSR).

Trois charts produits dans `renders/`, chacun défendant une dimension du
découpage en cellules utilisé par le modèle Skellam du targeter :

  * effect_day_type.png  — effet « jour ouvré vs week-end » (saisons confondues)
  * effect_season.png    — effet « froid vs tempéré »      (jours confondus)
  * seasonal_split.png   — combinaison des deux effets (synthèse 4 cellules)

Usage :
    python -m renders.targeter_render
    python -m renders.targeter_render --split-date 2026-03-20
"""

import argparse
import glob
import os
import sqlite3
from datetime import date as date_cls, datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_CLEAN_DIR  = "data/clean"
DEFAULT_OUT_DIR    = "renders"
DEFAULT_SPLIT_DATE = "2026-03-20"  # équinoxe de printemps 2026


# ============================================================================
# A — Chargement multi-jours
# ============================================================================

def load_clean_dir(clean_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Charge tous les `clean_*.sql` et renvoie (history, movements, stations)."""
    files = sorted(glob.glob(os.path.join(clean_dir, "clean_*.sql")))
    if not files:
        raise FileNotFoundError(f"Aucun clean_*.sql dans {clean_dir}")

    histories, movements = [], []
    stations_df: pd.DataFrame | None = None
    for f in files:
        con = sqlite3.connect(f)
        h = pd.read_sql_query(
            "SELECT station_number, available_bikes, timestamp FROM station_history",
            con, parse_dates=['timestamp'])
        m = pd.read_sql_query(
            "SELECT bike_id, station_number, movement_type, timestamp, source "
            "FROM bike_movements",
            con, parse_dates=['timestamp'])
        if stations_df is None:
            stations_df = pd.read_sql_query(
                "SELECT station_number, name, capacity, geo_lat AS lat, geo_long AS long "
                "FROM stations", con)
        con.close()
        histories.append(h)
        movements.append(m)
    return (pd.concat(histories, ignore_index=True),
            pd.concat(movements, ignore_index=True),
            stations_df)


# ============================================================================
# B — Rendus
# ============================================================================

def _render_single_dimension(movements: pd.DataFrame,
                              group_col: str,
                              group_values: list[tuple[object, str, str]],
                              output_file: str,
                              title: str | None,
                              source_filter: str | None) -> None:
    """Helper : trace 2 courbes superposées (1 par valeur du groupe) avec
    bandes ±1σ et un encart résumant les totaux journaliers.

    `group_values` : liste de (valeur, label_lisible, couleur).
    Suppose que `movements[group_col]` est déjà calculé en amont par l'appelant.
    """
    df = movements.copy()
    if source_filter:
        df = df[df['source'] == source_filter]
    df = df[df['movement_type'] == 'ARRIVAL']
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour

    all_dates = sorted(df['date'].unique())
    full_idx  = pd.MultiIndex.from_product([all_dates, range(24)],
                                            names=['date', 'hour'])
    counts = (df.groupby(['date', 'hour']).size()
                .reindex(full_idx, fill_value=0).reset_index(name='count'))
    date_meta = df.groupby('date').agg(**{group_col: (group_col, 'first')}).reset_index()
    counts = counts.merge(date_meta, on='date')

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_facecolor("#fafafa")

    daily_totals: dict[object, float] = {}
    for value, label, color in group_values:
        sub = counts[counts[group_col] == value]
        if sub.empty:
            continue
        pivot = (sub.pivot_table(index='date', columns='hour',
                                  values='count', fill_value=0)
                    .reindex(columns=range(24), fill_value=0))
        mean = pivot.mean(axis=0)
        std  = pivot.std(axis=0)
        ax.fill_between(range(24), mean - std, mean + std,
                        color=color, alpha=0.18, linewidth=0)
        ax.plot(range(24), mean.values, color=color, lw=2.4,
                label=label, alpha=0.92)
        daily_totals[value] = pivot.sum(axis=1).mean()

    if len(group_values) == 2 and all(v[0] in daily_totals for v in group_values):
        (v0, lbl0, _), (v1, lbl1, _) = group_values[0], group_values[1]
        t0, t1 = daily_totals[v0], daily_totals[v1]
        if min(t0, t1) > 0:
            if t0 >= t1:
                hi_lbl, lo_lbl, delta = lbl0, lbl1, (t0 - t1) / t1 * 100
            else:
                hi_lbl, lo_lbl, delta = lbl1, lbl0, (t1 - t0) / t0 * 100
            ax.text(0.02, 0.97, f"{hi_lbl} : +{delta:.0f}% vs {lo_lbl}",
                    transform=ax.transAxes, ha='left', va='top', fontsize=10,
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                              edgecolor='#bbb', alpha=0.95))

    ax.set_xlabel("Heure de la journée")
    ax.set_ylabel("Mouvements / heure  (moyenne ± 1σ)")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
    ax.set_xlim(-0.3, 23.3)
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, frameon=True, framealpha=0.95)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    if title:
        ax.set_title(title, fontsize=12)

    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)


def render_day_type_effect(movements: pd.DataFrame, output_file: str,
                            title: str | None = None,
                            source_filter: str | None = "USER") -> None:
    """Effet « jour ouvré vs week-end », saisons confondues.

    Justifie isolément la première dimension du découpage en cellules.
    """
    df = movements.copy()
    df['day_type'] = np.where(df['timestamp'].dt.dayofweek >= 5, 'WE', 'ouvré')
    _render_single_dimension(
        df, 'day_type',
        [('ouvré', "Jours ouvrés", '#5a2d82'),
         ('WE',    "Week-end",    '#2e7d32')],
        output_file=output_file,
        title=title or "Effet du type de jour sur la demande (saisons confondues)",
        source_filter=source_filter,
    )


def render_season_effect(movements: pd.DataFrame, output_file: str,
                          title: str | None = None,
                          split_date: str = DEFAULT_SPLIT_DATE,
                          source_filter: str | None = "USER") -> None:
    """Effet « froid vs tempéré », jours ouvrés et week-end confondus.

    Justifie isolément la seconde dimension du découpage en cellules.
    """
    split = date_cls.fromisoformat(split_date)
    df = movements.copy()
    df['regime'] = np.where(
        df['timestamp'].dt.date.astype('object') < split, 'froid', 'tempéré')
    _render_single_dimension(
        df, 'regime',
        [('froid',   "Régime froid",   '#1f4e79'),
         ('tempéré', "Régime tempéré", '#c14a09')],
        output_file=output_file,
        title=title or "Effet de la saison sur la demande (jours confondus)",
        source_filter=source_filter,
    )

def render_seasonal_split(movements: pd.DataFrame, output_file: str,
                          title: str | None = None,
                          split_date: str = DEFAULT_SPLIT_DATE,
                          source_filter: str | None = "USER") -> None:
    """Compare deux régimes (avant/après équinoxe) sur 2 panneaux : ouvré + WE.

    Chaque courbe = moyenne ± 1σ des mouvements/heure pour le régime.
    Un encart resume les totaux journaliers et l'ecart relatif.
    """
    df = movements.copy()
    if source_filter:
        df = df[df['source'] == source_filter]
    df = df[df['movement_type'] == 'ARRIVAL']
    df['date']       = df['timestamp'].dt.date
    df['hour']       = df['timestamp'].dt.hour
    df['is_weekend'] = df['timestamp'].dt.dayofweek >= 5

    split = date_cls.fromisoformat(split_date)
    df['regime'] = np.where(df['date'].astype('object') < split, 'froid', 'tempéré')

    # Grille complète (date × heure) pour ne pas oublier les heures sans mouvement.
    all_dates = sorted(df['date'].unique())
    full_idx  = pd.MultiIndex.from_product([all_dates, range(24)],
                                            names=['date', 'hour'])
    counts = (df.groupby(['date', 'hour']).size()
                .reindex(full_idx, fill_value=0).reset_index(name='count'))
    date_meta = df.groupby('date').agg(
        is_weekend=('is_weekend', 'first'),
        regime    =('regime',     'first')).reset_index()
    counts = counts.merge(date_meta, on='date')

    REGIME_COLORS = {'froid': '#1f4e79', 'tempéré': '#c14a09'}
    REGIME_LABEL  = {'froid':   "Régime froid",
                     'tempéré': "Régime tempéré"}

    fig, (ax_wd, ax_we) = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    if title:
        fig.suptitle(title, fontsize=12, y=1.01)

    for ax, is_weekend, panel_title in [
        (ax_wd, False, "Jours ouvrés (Lun → Ven)"),
        (ax_we, True,  "Week-end (Sam + Dim)"),
    ]:
        subset = counts[counts['is_weekend'] == is_weekend]
        for regime in ('froid', 'tempéré'):
            r = subset[subset['regime'] == regime]
            if r.empty:
                continue
            pivot = (r.pivot_table(index='date', columns='hour',
                                    values='count', fill_value=0)
                       .reindex(columns=range(24), fill_value=0))
            mean = pivot.mean(axis=0)
            std  = pivot.std(axis=0)
            ax.fill_between(range(24), mean - std, mean + std,
                            color=REGIME_COLORS[regime], alpha=0.18, linewidth=0)
            ax.plot(range(24), mean.values,
                    color=REGIME_COLORS[regime], lw=2.4,
                    label=REGIME_LABEL[regime], alpha=0.92)

        daily_totals = subset.groupby(['date', 'regime'])['count'].sum().reset_index()
        cold = daily_totals[daily_totals['regime'] == 'froid']['count'].values
        warm = daily_totals[daily_totals['regime'] == 'tempéré']['count'].values
        if len(cold) > 0 and len(warm) > 0 and min(cold.mean(), warm.mean()) > 0:
            if warm.mean() >= cold.mean():
                hi_lbl, lo_lbl = REGIME_LABEL['tempéré'], REGIME_LABEL['froid']
                delta = (warm.mean() - cold.mean()) / cold.mean() * 100
            else:
                hi_lbl, lo_lbl = REGIME_LABEL['froid'], REGIME_LABEL['tempéré']
                delta = (cold.mean() - warm.mean()) / warm.mean() * 100
            ax.text(0.02, 0.97, f"{hi_lbl} : +{delta:.0f}% vs {lo_lbl}",
                    transform=ax.transAxes, ha='left', va='top', fontsize=10,
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                              edgecolor='#bbb', alpha=0.95))

        ax.set_title(panel_title, fontsize=11, fontweight='bold')
        ax.set_xlabel("Heure de la journée")
        ax.set_xticks(range(0, 24, 2))
        ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
        ax.set_xlim(-0.3, 23.3)
        ax.set_facecolor("#fafafa")
        ax.grid(alpha=0.3)
        ax.legend(loc='upper right', fontsize=9, frameon=True, framealpha=0.95)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)

    ax_wd.set_ylabel("Mouvements / heure  (moyenne ± 1σ)")
    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# C — Orchestration
# ============================================================================

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--clean-dir",  default=DEFAULT_CLEAN_DIR)
    p.add_argument("--out-dir",    default=DEFAULT_OUT_DIR)
    p.add_argument("--split-date", default=DEFAULT_SPLIT_DATE,
                   help="Date de séparation froid/tempéré (défaut: équinoxe de printemps)")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    out = lambda name: os.path.join(args.out_dir, name)

    print(f"[{datetime.now():%H:%M:%S}] Chargement de tous les clean_*.sql dans {args.clean_dir}")
    _, movements, _ = load_clean_dir(args.clean_dir)
    n_days = movements['timestamp'].dt.date.nunique()
    print(f"  {len(movements):,} mouvements · {n_days} jours")

    print(f"[{datetime.now():%H:%M:%S}] (1/3) effect_day_type.png")
    render_day_type_effect(
        movements, output_file=out("effect_day_type.png"),
        source_filter="USER")

    print(f"[{datetime.now():%H:%M:%S}] (2/3) effect_season.png")
    render_season_effect(
        movements, output_file=out("effect_season.png"),
        split_date=args.split_date, source_filter="USER")

    print(f"[{datetime.now():%H:%M:%S}] (3/3) seasonal_split.png")
    render_seasonal_split(
        movements, output_file=out("seasonal_split.png"),
        title="Synthèse 4 cellules — combinaison saison × type de jour",
        split_date=args.split_date, source_filter="USER")

    print(f"[{datetime.now():%H:%M:%S}] Écrits dans {args.out_dir}/ : "
          f"effect_day_type.png, effect_season.png, seasonal_split.png")


if __name__ == "__main__":
    main()
