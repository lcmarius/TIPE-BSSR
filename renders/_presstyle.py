# =============================================================================
# Style commun pour les figures intégrées dans pres/main.tex
# =============================================================================
#
# Match le thème Beamer 4:3 metropolis :
#   - palette identique (cf. pres/main.tex:30-36)
#   - sans-serif (Fira Sans cible, DejaVu Sans fallback)
#   - tailles calibrées pour `\fig[\linewidth]` (\linewidth ≈ 4.7 in sur 4:3)
#   - PDF vectoriel dans pres/fig/, fonttype 42 (pas de Type 3)
#
# Usage type :
#     from renders._presstyle import apply_style, palette as P, figsize, save_pres
#     apply_style()
#     fig, ax = plt.subplots(figsize=figsize("std"))
#     ax.plot(xs, ys, color=P.deficit)
#     save_pres(fig, "rupture_daily")    # → pres/fig/rupture_daily.pdf
# =============================================================================

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


PRES_FIG_DIR = Path("pres/fig")


# Palette alignée sur pres/main.tex
@dataclass(frozen=True)
class Palette:
    surplus:       str = "#27AE60"   # vert  — gain de vélos
    deficit:       str = "#C0392B"   # rouge — perte de vélos
    depot:         str = "#2980B9"   # bleu  — dépôt
    accent:        str = "#F39C12"   # orange — mise en valeur
    tdark:         str = "#23373B"   # texte foncé
    tlight:        str = "#F4F4F4"   # fond clair
    textmuted:     str = "#5A6C72"   # gris secondaire

    # Variantes utiles pour des séries multiples
    deficit_dark:  str = "#7F1D1D"   # rouge foncé (timeout, extrapolation)
    surplus_dark:  str = "#1E7E34"
    accent_dark:   str = "#A86409"
    depot_dark:    str = "#1B4F72"
    purple:        str = "#5A2D82"   # violet (jours ouvrés)


palette = Palette()


# Cycle pour les courbes multiples (ex : 5 configs sur un panneau)
COLOR_CYCLE = [
    palette.deficit, palette.depot, palette.surplus, palette.accent,
    palette.purple,  palette.tdark, palette.deficit_dark, palette.depot_dark,
    palette.surplus_dark, palette.accent_dark,
]


def apply_style() -> None:
    """Configure matplotlib pour matcher Beamer/metropolis 4:3."""
    mpl.rcParams.update({
        # Typo
        "font.family":        "sans-serif",
        "font.sans-serif":    ["Fira Sans", "DejaVu Sans", "Helvetica", "Arial"],
        "font.size":          10.5,
        "axes.titlesize":     11,
        "axes.labelsize":     10,
        "xtick.labelsize":    9,
        "ytick.labelsize":    9,
        "legend.fontsize":    9,
        "figure.titlesize":   12,
        # Fond transparent : la figure adopte automatiquement le fond du slide
        # Beamer (blanc en mode light metropolis). Évite tout désalignement
        # visuel entre la figure et le reste de la slide.
        "axes.facecolor":     "none",
        "figure.facecolor":   "none",
        "savefig.facecolor":  "none",
        "savefig.transparent": True,
        # Axes / texte en tdark
        "axes.edgecolor":     palette.tdark,
        "axes.labelcolor":    palette.tdark,
        "xtick.color":        palette.tdark,
        "ytick.color":        palette.tdark,
        "text.color":         palette.tdark,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        # Grille très discrète
        "axes.grid":          True,
        "grid.color":         palette.tlight,
        "grid.linewidth":     0.6,
        "grid.alpha":         0.9,
        # Sortie PDF vectorielle, polices embarquées
        "pdf.fonttype":       42,
        "ps.fonttype":        42,
        "savefig.bbox":       "tight",
        "savefig.pad_inches": 0.05,
        "savefig.dpi":        200,
        # Cycle de couleurs cohérent avec la palette
        "axes.prop_cycle":    mpl.cycler(color=COLOR_CYCLE),
        # Légende sobre
        "legend.frameon":     False,
        "legend.borderpad":   0.4,
        # Lignes
        "lines.linewidth":    1.8,
        "lines.markersize":   5,
    })


# Tailles standardisées (en pouces). Le slide 4:3 a \linewidth ≈ 4.7 in
# et \textheight ≈ 3.15 in sous le frametitle. On crée des figures
# légèrement plus grandes pour conserver la lisibilité après inclusion.
_FIGSIZES = {
    "wide":   (5.0, 2.8),   # panoramique (1 axe long)
    "std":    (5.0, 3.2),   # standard (1 axe carré-ish)
    "tall":   (5.0, 3.6),   # plus de hauteur
    "double": (6.6, 3.0),   # 2 panneaux côte à côte
    "square": (3.6, 3.6),
    "map":    (5.0, 5.0),
}


def figsize(kind: str = "std") -> tuple[float, float]:
    """Renvoie (largeur_in, hauteur_in) pour un slide Beamer 4:3."""
    return _FIGSIZES[kind]


def save_pres(fig, name: str, *, width: str = "\\linewidth",
              height: str | None = None) -> Path:
    """Sauve `fig` en PDF dans pres/fig/<name>.pdf et imprime la ligne LaTeX
    prête à coller dans pres/main.tex.

    Par défaut : `\\fig[\\linewidth]{<name>.pdf}`. Passer `height=` pour
    obtenir `\\figh[<height>]{<name>.pdf}`.
    """
    PRES_FIG_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PRES_FIG_DIR / f"{name}.pdf"
    fig.savefig(pdf_path)
    plt.close(fig)

    if height:
        latex = f"\\figh[{height}]{{{name}.pdf}}"
    else:
        latex = f"\\fig[{width}]{{{name}.pdf}}"
    print(f"  écrit {pdf_path}")
    print(f"  LaTeX : {latex}")
    return pdf_path
