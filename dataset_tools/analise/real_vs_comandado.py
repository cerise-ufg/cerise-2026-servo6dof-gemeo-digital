#!/usr/bin/env python3
"""
Juntas REAIS (joint_states no instante da foto) x COMANDADAS (plano) no dataset.

Para cada pose calcula |real - comandado| por junta e, pela FK do modelo digital,
a altura minima (z) das origens dos elos e da ponta da garra na configuracao
COMANDADA e na REAL - para testar a hipotese de que as divergencias vem de
contato com o chao (o plano sorteia configuracoes que atravessariam z = 0).

Saidas: resultados/dataset_real_vs_comandado.json, evidencias/a7_real_vs_comandado.png
Uso: python3 dataset_tools/analise/real_vs_comandado.py --meta /dataset_meta
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "modelo_digital"))
import estilo  # noqa: E402
from cinematica import JUNTAS_BRACO, ModeloURDF  # noqa: E402

ELOS = ["segundo_elo", "terceiro_elo", "quarto_elo", "base_garra"]


def z_min(m, Q, tcp_local):
    zs = [m.fk_lote(Q, e, nomes=JUNTAS_BRACO)[:, 2] for e in ELOS]
    zs.append(m.fk_lote(Q, "base_garra", ponto_local=tcp_local, nomes=JUNTAS_BRACO)[:, 2])
    return np.min(np.vstack(zs), axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default="/dataset_meta")
    ap.add_argument("--limiar", type=float, default=0.01, help="rad")
    a = ap.parse_args()
    L = list(csv.DictReader(open(os.path.join(a.meta, "index.csv"))))
    C = np.array([[float(l["cmd_" + j]) for j in JUNTAS_BRACO] for l in L])
    R = np.array([[float(l["real_" + j]) for j in JUNTAS_BRACO] for l in L])
    D = np.abs(R - C)
    Dm = D.max(axis=1)
    m = ModeloURDF()
    p0 = m.fk({})
    meio = 0.5 * (p0["garra_elo3a"][:3, 3] + p0["garra_elo3b"][:3, 3])
    tcp = (np.linalg.inv(p0["base_garra"]) @ np.r_[meio, 1])[:3]
    zc, zr = z_min(m, C, tcp), z_min(m, R, tcp)
    div = Dm > a.limiar
    abaixo = zc < 0
    res = {
        "n_poses": len(L), "limiar_rad": a.limiar,
        "frac_poses_divergentes": float(div.mean()),
        "por_junta_frac_divergente": {j: float((D[:, k] > a.limiar).mean()) for k, j in enumerate(JUNTAS_BRACO)},
        "por_junta_dif_media_rad": {j: float(D[:, k].mean()) for k, j in enumerate(JUNTAS_BRACO)},
        "dif_max_rad": float(Dm.max()), "dif_p95_rad": float(np.percentile(Dm, 95)),
        "frac_comandadas_atravessam_chao": float(abaixo.mean()),
        "frac_divergentes_entre_as_que_atravessam_chao": float(div[abaixo].mean()) if abaixo.any() else None,
        "frac_divergentes_entre_as_acima_do_chao": float(div[~abaixo].mean()) if (~abaixo).any() else None,
        "z_min_real_m_das_divergentes": {"media": float(zr[div].mean()) if div.any() else None,
                                         "p5": float(np.percentile(zr[div], 5)) if div.any() else None},
        "frac_reais_abaixo_de_-5cm": float((zr < -0.05).mean()),
    }
    with open(os.path.join(RAIZ, "resultados", "dataset_real_vs_comandado.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))

    estilo.aplicar()
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.9))
    ax = axs[0]
    ax.bar(range(5), [100 * res["por_junta_frac_divergente"][j] for j in JUNTAS_BRACO], color=estilo.CATEG[0],
           width=0.6)
    ax.set_xticks(range(5))
    ax.set_xticklabels(JUNTAS_BRACO)
    ax.set_ylabel("poses com |real - comandado| > %.2f rad (%%)" % a.limiar)
    ax.set_title("Divergencia por junta", loc="left")
    ax.grid(axis="x", visible=False)
    ax = axs[1]
    ax.scatter(zc[~div], Dm[~div], s=5, color=estilo.CATEG[0], alpha=0.4, linewidths=0, label="sem divergencia")
    ax.scatter(zc[div], Dm[div], s=5, color=estilo.CATEG[1], alpha=0.5, linewidths=0, label="divergente")
    ax.axvline(0, color=estilo.TEXTO2, lw=0.8, ls="--")
    ax.set_xlabel("z minimo do braco na config. COMANDADA (m)")
    ax.set_ylabel("max |real - comandado| (rad)")
    ax.set_title("Divergencia x altura minima comandada", loc="left")
    ax.legend(loc="upper right", markerscale=3)
    ax = axs[2]
    b = np.linspace(min(zc.min(), zr.min()), max(zc.max(), zr.max()), 50)
    ax.hist(zc, bins=b, histtype="step", lw=2, color=estilo.CATEG[0], label="comandada")
    ax.hist(zr, bins=b, histtype="step", lw=2, color=estilo.CATEG[1], label="real (no instante da foto)")
    ax.axvline(0, color=estilo.TEXTO2, lw=0.8, ls="--")
    ax.set_xlabel("z minimo do braco (m)")
    ax.set_ylabel("poses")
    ax.set_title("Altura minima: comandada x real", loc="left")
    ax.legend(loc="upper left")
    fig.suptitle("Juntas reais x comandadas no dataset (%d poses): %.1f%% divergem mais que %.2f rad"
                 % (len(L), 100 * res["frac_poses_divergentes"], a.limiar), x=0.01, ha="left", fontsize=12,
                 fontweight="semibold")
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_real_vs_comandado.png"))


if __name__ == "__main__":
    main()
