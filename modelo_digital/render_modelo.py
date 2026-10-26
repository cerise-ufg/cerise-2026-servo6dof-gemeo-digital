#!/usr/bin/env python3
"""
Renders do modelo digital (malhas STL + FK) sem GPU e sem ROS:

  A) evidencias/a11_render_modelo_poses.png - o braco em 4 poses nomeadas do
     SRDF/MoveIt (home, recolhido, estendido, giro_esquerda), renderizado com
     matplotlib (sombreamento lambertiano por face).
  B) evidencias/a11_sobreposicao_modelo_dataset.png - para poses do dataset, a
     silhueta do modelo digital (malhas transformadas pela FK e projetadas com
     o modelo pinhole das cameras do estudio) sobreposta a imagem RGB gerada
     pelo Gazebo, mais o esqueleto da cadeia cinematica.

Uso: python3 modelo_digital/render_modelo.py --dataset /dataset --ids 1 2 3
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estilo  # noqa: E402
from cinematica import JUNTAS_BRACO, ModeloURDF, URDF_PADRAO, malhas_no_mundo, projetar  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE = os.path.join(RAIZ, "ros2_ws", "src", "servo6dof")  # contem servo6dof_description/
CADEIA = ["base_link", "primeiro_elo", "segundo_elo", "terceiro_elo", "quarto_elo", "base_garra"]

POSES_NOMEADAS = [
    ("home", [0, 0, 0, 0, 0], 0.0),
    ("recolhido", [0, -1.2, 1.2, 0, 0], 0.0),
    ("estendido", [0, 0.9, -0.6, 0, 0.3], -0.6),
    ("giro_esquerda", [1.2, 0.55, -0.35, 0.4, 0.0], 0.45),
]


def q_de(arm, garra):
    q = dict(zip(JUNTAS_BRACO, arm))
    q["joint_6"] = garra
    return q


def sombrear(tri, rgba, luz=np.array([0.4, -0.5, 0.75])):
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    luz = luz / np.linalg.norm(luz)
    k = 0.35 + 0.65 * np.abs(n @ luz)
    base = np.asarray(rgba[:3])
    cor = np.clip(base[None] * k[:, None], 0, 1)
    return np.c_[cor, np.ones(len(cor))]


def render_poses(modelo, saida):
    estilo.aplicar()
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    cache = {}
    fig = plt.figure(figsize=(13, 9.6))
    for k, (nome, arm, garra) in enumerate(POSES_NOMEADAS):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        malhas = malhas_no_mundo(modelo, q_de(arm, garra), SHARE, cache)
        todos = np.concatenate([t for t, _, _ in malhas])
        cores = np.concatenate([sombrear(t, rgba) for t, rgba, _ in malhas])
        pc = Poly3DCollection(todos, facecolors=cores, edgecolors="none", linewidths=0)
        ax.add_collection3d(pc)
        poses = modelo.fk(q_de(arm, garra))
        pts = np.array([poses[n][:3, 3] for n in CADEIA])
        ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], color=estilo.CATEG[1], lw=2, marker="o", ms=4, zorder=10)
        ax.set_xlim(-1.1, 1.1)
        ax.set_ylim(-0.7, 1.5)
        ax.set_zlim(0.0, 2.2)
        ax.set_box_aspect((2.2, 2.2, 2.2))
        ax.view_init(elev=18, azim=-35)
        ax.dist = 7.2
        ax.set_xlabel("x (m)", labelpad=-4)
        ax.set_ylabel("y (m)", labelpad=-4)
        ax.set_zlabel("z (m)", labelpad=-4)
        ax.tick_params(pad=-2, labelsize=7)
        for eix in (ax.xaxis, ax.yaxis, ax.zaxis):
            eix.pane.set_facecolor("#f4f3f0")
        ax.set_title("%s\nq = [%s] rad, garra %.2f" % (nome, ", ".join("%.2f" % v for v in arm), garra),
                     loc="left", fontsize=10, y=0.93)
    fig.suptitle("Modelo digital do servo6dof - malhas STL do URDF posicionadas pela cinematica direta",
                 x=0.01, ha="left", fontsize=12.5, fontweight="semibold")
    fig.text(0.01, 0.945, "Render por software (matplotlib); linha laranja = cadeia base_link -> base_garra "
             "(origens dos referenciais das juntas)", fontsize=9, color=estilo.TEXTO2)
    fig.subplots_adjust(left=0.0, right=1.0, bottom=0.02, top=0.92, wspace=0.0, hspace=0.16)
    fig.savefig(saida)
    print("figura:", saida)


def sobreposicao(modelo, dataset, ids, saida):
    estilo.aplicar()
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from PIL import Image
    cache = {}
    cams = ["camera_frontal", "camera_diagonal"]
    fig, axs = plt.subplots(len(ids), 2, figsize=(12.5, 3.75 * len(ids)))
    axs = np.atleast_2d(axs)
    for r, i in enumerate(ids):
        meta = json.load(open(os.path.join(dataset, "%06d.json" % i)))
        jr = meta.get("juntas_reais") or meta["juntas_comandadas"]
        q = dict(jr)
        q["joint_6"] = meta["garra_comandada"]["joint_6"]
        malhas = malhas_no_mundo(modelo, q, SHARE, cache)
        poses = modelo.fk(q)
        esq = np.array([poses[n][:3, 3] for n in CADEIA])
        for c, cam in enumerate(cams):
            ax = axs[r, c]
            img = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_image.png" % (i, cam))).convert("RGB"))
            ax.imshow(img)
            polys = []
            for tri, _, _ in malhas:
                uv, prof = projetar(tri.reshape(-1, 3), cam)
                uv = uv.reshape(-1, 3, 2)
                ok = (prof.reshape(-1, 3) > 0).all(axis=1) & (tri[:, :, 2] > -1e-3).any(axis=1)
                polys.append(uv[ok])
            polys = np.concatenate(polys)
            ax.add_collection(PolyCollection(polys, facecolors=(0.11, 0.69, 0.48, 0.18), edgecolors="none"))
            uv, _ = projetar(esq, cam)
            ax.plot(uv[:, 0], uv[:, 1], color=estilo.CATEG[1], lw=2, marker="o", ms=4)
            ax.set_xlim(0, img.shape[1])
            ax.set_ylim(img.shape[0], 0)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
            ax.set_title("pose %06d - %s" % (i, cam.replace("_", " ")), loc="left", fontsize=10)
    fig.suptitle("Modelo digital projetado sobre as imagens do dataset (Gazebo)", x=0.01, ha="left",
                 y=1 - 0.12 / fig.get_figheight(), va="top", fontsize=12.5, fontweight="semibold")
    fig.text(0.01, 1 - 0.5 / fig.get_figheight(), "verde translucido = malhas do URDF posicionadas pela FK com as "
             "juntas registradas no JSON e projetadas pelo modelo pinhole da camera (hfov 60 graus, 1280x720); "
             "laranja = esqueleto da cadeia", fontsize=8.8, color=estilo.TEXTO2)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    fig.savefig(saida)
    print("figura:", saida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--ids", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--so", choices=["poses", "sobreposicao", "tudo"], default="tudo")
    a = ap.parse_args()
    m = ModeloURDF(URDF_PADRAO)
    if a.so in ("poses", "tudo"):
        render_poses(m, os.path.join(RAIZ, "evidencias", "a11_render_modelo_poses.png"))
    if a.so in ("sobreposicao", "tudo"):
        sobreposicao(m, a.dataset, a.ids, os.path.join(RAIZ, "evidencias", "a11_sobreposicao_modelo_dataset.png"))


if __name__ == "__main__":
    main()
