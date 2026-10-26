"""Estilo comum dos graficos (matplotlib, 150 dpi, textos em portugues).

Paleta categorica de ordem fixa (validada para daltonismo nos pares adjacentes),
rampa sequencial azul de um so matiz, grade e eixos discretos.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO2 = "#52514e"
GRADE = "#e4e3df"
CATEG = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP_SEQ = LinearSegmentedColormap.from_list("seq_azul", SEQ)
# divergente: laranja <- cinza -> azul
CMAP_DIV = LinearSegmentedColormap.from_list("div", ["#c2461a", "#eb6834", "#f3b79c", "#e9e8e4",
                                                     "#9ec5f4", "#2a78d6", "#184f95"])
DPI = 150


def aplicar():
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE,
        "axes.edgecolor": "#b9b8b2",
        "axes.labelcolor": TEXTO2,
        "axes.titlecolor": TEXTO,
        "axes.titlesize": 11,
        "axes.titleweight": "semibold",
        "axes.labelsize": 9.5,
        "axes.grid": True,
        "grid.color": GRADE,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": TEXTO2,
        "ytick.color": TEXTO2,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "legend.frameon": False,
        "font.size": 9.5,
        "lines.linewidth": 2.0,
        "axes.prop_cycle": matplotlib.cycler(color=CATEG),
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
    })


def titulo_fig(fig, texto, sub=None):
    fig.suptitle(texto, x=0.01, ha="left", fontsize=12.5, fontweight="semibold", color=TEXTO)
    if sub:
        fig.text(0.01, 0.955 if fig.get_figheight() > 5 else 0.93, sub, ha="left",
                 fontsize=9, color=TEXTO2)
