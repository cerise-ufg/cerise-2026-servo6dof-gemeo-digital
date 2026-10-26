#!/usr/bin/env python3
"""
Analise do espaco de trabalho do servo6dof por amostragem de Monte Carlo.

Amostra N configuracoes uniformes nos limites do URDF (joint_1..joint_5; a
garra nao altera a posicao do efetuador) e calcula, por FK vetorizada, a
posicao de dois pontos de referencia:
  - origem de base_garra (link de ponta do grupo 'arm' do MoveIt / SRDF);
  - "ponta da garra" (TCP): ponto medio das origens das duas pincas
    (garra_elo3a/garra_elo3b) com a garra em joint_6 = 0, expresso em base_garra.

Saidas: resultados/espaco_trabalho.json (estatisticas de alcance, volume do
fecho convexo e volume ocupado por voxels), resultados/espaco_trabalho_amostra.npz
(nuvem), evidencias/a11_espaco_trabalho.png (3D + topo + lateral).

Uso:  python3 modelo_digital/espaco_trabalho.py --n 100000
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cinematica import JUNTAS_BRACO, ModeloURDF, URDF_PADRAO  # noqa: E402
import estilo  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100000)
    ap.add_argument("--semente", type=int, default=2026)
    ap.add_argument("--voxel", type=float, default=0.05, help="aresta do voxel (m)")
    a = ap.parse_args()

    m = ModeloURDF(URDF_PADRAO)
    rng = np.random.default_rng(a.semente)
    lims = np.array([(m.juntas[j].inf, m.juntas[j].sup) for j in JUNTAS_BRACO])
    t0 = time.time()
    Q = rng.uniform(lims[:, 0], lims[:, 1], size=(a.n, 5))

    # TCP no referencial de base_garra (garra em zero)
    p0 = m.fk({})
    Tbg = p0["base_garra"]
    meio = 0.5 * (p0["garra_elo3a"][:3, 3] + p0["garra_elo3b"][:3, 3])
    tcp_local = (np.linalg.inv(Tbg) @ np.r_[meio, 1])[:3]

    P_bg = m.fk_lote(Q, "base_garra", nomes=JUNTAS_BRACO)
    P_tcp = m.fk_lote(Q, "base_garra", ponto_local=tcp_local, nomes=JUNTAS_BRACO)
    t_fk = time.time() - t0

    # eixo de joint_1 (vertical passando pela origem de primeiro_elo)
    eixo1 = p0["primeiro_elo"][:3, 3]
    ombro = p0["segundo_elo"][:3, 3]

    def stats(P):
        r_xy = np.linalg.norm(P[:, :2] - eixo1[:2], axis=1)
        r_ombro = np.linalg.norm(P - ombro, axis=1)
        out = {
            "x_min_max_m": [float(P[:, 0].min()), float(P[:, 0].max())],
            "y_min_max_m": [float(P[:, 1].min()), float(P[:, 1].max())],
            "z_min_max_m": [float(P[:, 2].min()), float(P[:, 2].max())],
            "alcance_horizontal_max_m": float(r_xy.max()),
            "alcance_horizontal_p50_m": float(np.median(r_xy)),
            "distancia_ombro_min_max_m": [float(r_ombro.min()), float(r_ombro.max())],
            "frac_abaixo_do_chao_z<0": float((P[:, 2] < 0).mean()),
        }
        try:
            from scipy.spatial import ConvexHull
            out["volume_fecho_convexo_m3"] = float(ConvexHull(P).volume)
        except Exception as e:  # pragma: no cover
            out["volume_fecho_convexo_m3"] = None
            out["erro_hull"] = str(e)
        vox = np.unique(np.floor(P / a.voxel).astype(np.int64), axis=0)
        out["volume_voxels_m3"] = float(len(vox) * a.voxel ** 3)
        out["n_voxels"] = int(len(vox))
        return out

    res = {
        "n_configuracoes": a.n, "semente": a.semente, "juntas": JUNTAS_BRACO,
        "limites_rad": lims.tolist(), "tempo_fk_lote_s": round(t_fk, 3),
        "voxel_m": a.voxel, "tcp_em_base_garra_m": tcp_local.round(4).tolist(),
        "eixo_joint1_xy_m": eixo1[:2].round(4).tolist(), "ombro_joint2_m": ombro.round(4).tolist(),
        "base_garra": stats(P_bg), "tcp": stats(P_tcp),
    }
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    with open(os.path.join(RAIZ, "resultados", "espaco_trabalho.json"), "w") as f:
        json.dump(res, f, indent=2)
    np.savez_compressed(os.path.join(RAIZ, "resultados", "espaco_trabalho_amostra.npz"),
                        Q=Q[:20000].astype(np.float32), P_tcp=P_tcp[:20000].astype(np.float32))
    print(json.dumps(res["tcp"], indent=1))
    print("FK em lote: %d configuracoes em %.3f s" % (a.n, t_fk))

    # ------------------------------------------------------------ figura
    estilo.aplicar()
    import matplotlib.pyplot as plt
    P = P_tcp
    r = np.linalg.norm(P[:, :2] - eixo1[:2], axis=1)
    k = min(len(P), 50000)
    idx = rng.choice(len(P), k, replace=False)
    fig = plt.figure(figsize=(15, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1, 1])
    ax3 = fig.add_subplot(gs[0], projection="3d")
    sc = ax3.scatter(P[idx, 0], P[idx, 1], P[idx, 2], c=P[idx, 2], cmap=estilo.CMAP_SEQ, s=0.6,
                     alpha=0.35, linewidths=0)
    ax3.scatter([0], [0], [0], c=estilo.CATEG[1], s=30, marker="^", label="base (world)")
    ax3.set_xlabel("x (m)", labelpad=2)
    ax3.set_ylabel("y (m)", labelpad=2)
    ax3.set_zlabel("z (m)", labelpad=4)
    ax3.tick_params(labelsize=7.5, pad=0)
    ax3.dist = 8.6
    ax3.set_title("Nuvem 3D da ponta da garra", loc="left", pad=14)
    ax3.view_init(elev=22, azim=-58)
    ax3.legend(loc="upper left")
    for eix in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
        eix.pane.set_facecolor(estilo.SUPERFICIE)
    ax3.set_box_aspect((np.ptp(P[:, 0]), np.ptp(P[:, 1]), np.ptp(P[:, 2])))

    ax = fig.add_subplot(gs[1])
    ax.grid(False)
    h = ax.hexbin(P[:, 0], P[:, 1], gridsize=70, cmap=estilo.CMAP_SEQ, mincnt=1, bins="log")
    ax.plot(eixo1[0], eixo1[1], marker="+", color=estilo.CATEG[1], markersize=10, mew=2)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Vista de topo (XY)", loc="left")
    ax.grid(False)

    ax = fig.add_subplot(gs[2])
    ax.grid(False)
    ax.hexbin(r, P[:, 2], gridsize=70, cmap=estilo.CMAP_SEQ, mincnt=1, bins="log")
    ax.axhline(0, color=estilo.TEXTO2, lw=0.8, ls="--")
    ax.text(r.max(), 0.02, "chao (z = 0)", ha="right", va="bottom", fontsize=8, color=estilo.TEXTO2)
    ax.set_aspect("equal")
    ax.set_xlabel("distancia radial ao eixo de joint_1 (m)")
    ax.set_ylabel("z (m)")
    ax.set_title("Vista lateral (r x z)", loc="left")
    ax.grid(False)
    fig.subplots_adjust(left=0.0, right=0.93, top=0.82, bottom=0.11, wspace=0.32)
    cb = fig.colorbar(h, ax=fig.axes[1:], fraction=0.025, pad=0.02)
    cb.set_label("amostras por celula (log)")
    s = res["tcp"]
    fig.suptitle("Espaco de trabalho do servo6dof - %d configuracoes uniformes nos limites (+-90 graus em joint_1..5)"
                 % a.n, x=0.01, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.915, "alcance horizontal max %.2f m | z em [%.2f, %.2f] m | volume do fecho convexo %.2f m3 | "
             "volume ocupado (voxel %.0f cm) %.2f m3" % (s["alcance_horizontal_max_m"], s["z_min_max_m"][0],
                                                       s["z_min_max_m"][1], s["volume_fecho_convexo_m3"],
                                                       a.voxel * 100, s["volume_voxels_m3"]),
             fontsize=9, color=estilo.TEXTO2)
    fig.savefig(os.path.join(RAIZ, "evidencias", "a11_espaco_trabalho.png"))


if __name__ == "__main__":
    main()
