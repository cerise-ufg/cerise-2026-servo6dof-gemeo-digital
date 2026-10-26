#!/usr/bin/env python3
"""
Estatisticas do dataset a partir do index.csv (+ integridade_por_imagem.csv se existir):
  - contagens, tamanho total e por modalidade/camera;
  - histogramas dos angulos comandados vs limites do URDF e faixa do plano (5% de folga);
  - cobertura do espaco de juntas (pares de juntas em grade 20x20; distancia ao vizinho
    mais proximo no espaco 5D normalizado comparada a amostras uniformes);
  - correlacao entre juntas (Pearson);
  - diferenca juntas reais x comandadas;
  - fracao de pixels do braco por camera (da integridade).
Saidas: resultados/dataset_estatisticas.json e figuras evidencias/a7_*.png
Uso: python3 dataset_tools/analise/estatisticas.py --meta /dataset_meta
"""
import argparse
import csv
import json
import math
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "modelo_digital"))
import estilo  # noqa: E402

JUNTAS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
CAMERAS = ["camera_frontal", "camera_diagonal"]
MODS = ["image", "depth", "segmentation_labels_map"]
NOME_MOD = {"image": "RGB", "depth": "profundidade", "segmentation_labels_map": "segmentacao"}
LIM = math.pi / 2
LIM_GARRA = (-40 * math.pi / 180, 30 * math.pi / 180)
FOLGA = 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default="/dataset_meta")
    a = ap.parse_args()
    L = list(csv.DictReader(open(os.path.join(a.meta, "index.csv"))))
    n = len(L)
    Q = np.array([[float(l["cmd_" + j]) for j in JUNTAS] for l in L])
    G = np.array([float(l["garra_joint_6"]) for l in L])
    R = np.array([[float(l["real_" + j]) if l["real_" + j] != "" else np.nan for j in JUNTAS] for l in L])
    tam = {}
    for c in CAMERAS:
        for m in MODS:
            v = np.array([int(l["%s_%s_bytes" % (c, m)] or 0) for l in L])
            tam["%s_%s" % (c, m)] = {"total_bytes": int(v.sum()), "media_kb": float(v.mean() / 1024)}
    json_b = int(sum(int(l["json_bytes"]) for l in L))
    total = sum(t["total_bytes"] for t in tam.values()) + json_b
    por_mod = {NOME_MOD[m]: int(sum(tam["%s_%s" % (c, m)]["total_bytes"] for c in CAMERAS)) for m in MODS}

    # cobertura
    lo, hi = -LIM + 2 * LIM * FOLGA, LIM - 2 * LIM * FOLGA
    Qn = (Q - lo) / (hi - lo)
    cob_pares = {}
    for i in range(5):
        for k in range(i + 1, 5):
            H, _, _ = np.histogram2d(Qn[:, i], Qn[:, k], bins=20, range=[[0, 1], [0, 1]])
            cob_pares["%s-%s" % (JUNTAS[i], JUNTAS[k])] = float((H > 0).mean())
    from scipy.spatial import cKDTree
    d_nn = cKDTree(Qn).query(Qn, k=2)[0][:, 1]
    rng = np.random.default_rng(0)
    U = rng.uniform(0, 1, size=Qn.shape)
    d_u = cKDTree(U).query(U, k=2)[0][:, 1]
    C = np.corrcoef(np.c_[Q, G].T)
    dif = np.abs(R - Q)
    res = {
        "n_poses": n, "n_imagens": n * 6, "n_imagens_rgb": n * 2,
        "tamanho_total_bytes": int(total), "tamanho_total_gb": total / 1e9,
        "tamanho_por_modalidade_bytes": por_mod, "tamanho_json_bytes": json_b,
        "tamanho_por_camera_modalidade": tam, "media_mb_por_pose": total / n / 1e6,
        "splits": {s: sum(1 for l in L if l["split"] == s) for s in ("treino", "validacao", "teste")},
        "angulos_graus": {j: {"min": float(np.degrees(Q[:, k].min())), "max": float(np.degrees(Q[:, k].max())),
                              "media": float(np.degrees(Q[:, k].mean())), "desvio": float(np.degrees(Q[:, k].std()))}
                          for k, j in enumerate(JUNTAS)},
        "garra_graus": {"min": float(np.degrees(G.min())), "max": float(np.degrees(G.max()))},
        "faixa_do_plano_graus": [float(np.degrees(lo)), float(np.degrees(hi))],
        "cobertura_pares_grade20": cob_pares,
        "cobertura_pares_media": float(np.mean(list(cob_pares.values()))),
        "dist_vizinho_mais_proximo_5d_norm": {"dataset_media": float(d_nn.mean()), "uniforme_media": float(d_u.mean()),
                                              "dataset_min": float(d_nn.min())},
        "correlacao_max_abs_fora_diagonal": float(np.max(np.abs(C - np.eye(6)))),
        "dif_real_comandada_rad": {"max": float(np.nanmax(dif)), "media": float(np.nanmean(dif)),
                                   "frac_poses_dif>0.01": float((np.nanmax(dif, axis=1) > 0.01).mean())},
    }
    # fracao de braco por camera (integridade)
    pi = os.path.join(a.meta, "integridade_por_imagem.csv")
    FB = {}
    if os.path.exists(pi):
        for r in csv.DictReader(open(pi)):
            if r["modalidade"] == "segmentation_labels_map" and r["frac_braco"] not in ("", None):
                FB.setdefault(r["camera"], []).append(float(r["frac_braco"]))
        res["frac_pixels_braco"] = {c: {"media": float(np.mean(v)), "min": float(np.min(v)), "max": float(np.max(v))}
                                    for c, v in FB.items()}
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    with open(os.path.join(RAIZ, "resultados", "dataset_estatisticas.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: res[k] for k in ("n_poses", "tamanho_total_gb", "tamanho_por_modalidade_bytes", "splits",
                                          "cobertura_pares_media", "correlacao_max_abs_fora_diagonal",
                                          "dif_real_comandada_rad")}, indent=1, ensure_ascii=False))

    # ------------------------------------------------------------- figuras
    estilo.aplicar()
    import matplotlib.pyplot as plt
    # 1) histogramas vs limites
    fig, axs = plt.subplots(2, 3, figsize=(13, 6.4))
    for k in range(6):
        ax = axs.flat[k]
        if k < 5:
            v, lim, fx, nome = np.degrees(Q[:, k]), (-90, 90), (np.degrees(lo), np.degrees(hi)), JUNTAS[k]
        else:
            v = np.degrees(G)
            lim = (np.degrees(LIM_GARRA[0]), np.degrees(LIM_GARRA[1]))
            mg = (lim[1] - lim[0]) * FOLGA
            fx, nome = (lim[0] + mg, lim[1] - mg), "joint_6 (garra)"
        ax.axvspan(lim[0], fx[0], color="#f3d6c9", lw=0)
        ax.axvspan(fx[1], lim[1], color="#f3d6c9", lw=0)
        ax.hist(v, bins=36, range=lim, color=estilo.CATEG[0], edgecolor=estilo.SUPERFICIE, lw=0.6)
        ax.axhline(n / 36 * (lim[1] - lim[0]) / (fx[1] - fx[0]), color=estilo.TEXTO2, lw=0.9, ls="--")
        for x in lim:
            ax.axvline(x, color=estilo.CATEG[7], lw=1.2)
        ax.set_title(nome, loc="left")
        ax.set_xlabel("angulo comandado (graus)")
        ax.set_xlim(lim[0] - 5, lim[1] + 5)
    axs[0, 0].set_ylabel("poses")
    axs[1, 0].set_ylabel("poses")
    fig.suptitle("Distribuicao dos angulos no dataset (%d poses) frente aos limites do URDF" % n,
                 x=0.01, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.925, "linhas vermelhas = limites do URDF; faixas salmao = folga de 5%% excluida pelo plano; "
             "tracejado = contagem esperada para amostragem uniforme", fontsize=9, color=estilo.TEXTO2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_histogramas_angulos.png"))
    plt.close(fig)

    # 2) cobertura (pares) + correlacao
    fig = plt.figure(figsize=(13, 5.2))
    gs = fig.add_gridspec(2, 6, width_ratios=[1, 1, 1, 1, 0.15, 2.2])
    pares = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4), (1, 3), (0, 2), (2, 4)]
    for t, (i, k) in enumerate(pares):
        ax = fig.add_subplot(gs[t // 4, t % 4])
        ax.hexbin(np.degrees(Q[:, i]), np.degrees(Q[:, k]), gridsize=18, cmap=estilo.CMAP_SEQ, mincnt=1,
                  extent=(-90, 90, -90, 90))
        ax.set_xlim(-90, 90)
        ax.set_ylim(-90, 90)
        ax.set_xticks([-90, 0, 90])
        ax.set_yticks([-90, 0, 90])
        ax.tick_params(labelsize=7)
        ax.set_xlabel(JUNTAS[i].replace("joint_", "j"), fontsize=8, labelpad=1)
        ax.set_ylabel(JUNTAS[k].replace("joint_", "j"), fontsize=8, labelpad=1)
        ax.grid(False)
        ax.set_aspect("equal")
    ax = fig.add_subplot(gs[:, 5])
    nomes = [j.replace("joint_", "j") for j in JUNTAS] + ["garra"]
    im = ax.imshow(C, cmap=estilo.CMAP_DIV, vmin=-1, vmax=1)
    for i in range(6):
        for k in range(6):
            ax.text(k, i, "%.2f" % C[i, k], ha="center", va="center", fontsize=8,
                    color="white" if abs(C[i, k]) > 0.6 else estilo.TEXTO)
    ax.set_xticks(range(6))
    ax.set_xticklabels(nomes)
    ax.set_yticks(range(6))
    ax.set_yticklabels(nomes)
    ax.grid(False)
    ax.set_title("Correlacao de Pearson entre juntas", loc="left")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.suptitle("Cobertura do espaco de juntas: pares de juntas (densidade) e correlacoes", x=0.01, ha="left",
                 fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.91, "cobertura media da grade 20x20 (celulas de 8,1 graus) nos 10 pares: %.1f%% | correlacao max. |r| = %.3f | "
             "dist. media ao vizinho mais proximo (5D normalizado): %.3f (uniforme: %.3f)"
             % (100 * res["cobertura_pares_media"], res["correlacao_max_abs_fora_diagonal"], d_nn.mean(), d_u.mean()),
             fontsize=9, color=estilo.TEXTO2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_cobertura_correlacao.png"))
    plt.close(fig)

    # 3) composicao (tamanho por modalidade/camera) + fracao de braco
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axs[0]
    rot, val, cor = [], [], []
    for c_i, c in enumerate(CAMERAS):
        for m_i, m in enumerate(MODS):
            rot.append("%s - %s" % (c.replace("camera_", ""), NOME_MOD[m]))
            val.append(tam["%s_%s" % (c, m)]["total_bytes"] / 1e9)
            cor.append(estilo.CATEG[m_i])
    y = np.arange(len(rot))[::-1]
    ax.barh(y, val, color=cor, height=0.62)
    for yy, v in zip(y, val):
        ax.text(v, yy, "  %.2f GB" % v, va="center", fontsize=8.5, color=estilo.TEXTO2)
    ax.set_yticks(y)
    ax.set_yticklabels(rot)
    ax.set_xlabel("GB")
    ax.set_title("Tamanho por camera e modalidade (total %.2f GB)" % res["tamanho_total_gb"], loc="left")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(val) * 1.25)
    ax = axs[1]
    if FB:
        for k, c in enumerate(CAMERAS):
            if c in FB:
                ax.hist(100 * np.array(FB[c]), bins=40, histtype="step", lw=2, color=estilo.CATEG[k],
                        label="%s (media %.1f%%)" % (c.replace("_", " "), 100 * np.mean(FB[c])))
        ax.set_xlabel("pixels do braco na imagem (%)")
        ax.set_ylabel("imagens")
        ax.legend()
        ax.set_title("Area ocupada pelo braco (mascara de segmentacao)", loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_composicao_dataset.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
