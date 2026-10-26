#!/usr/bin/env python3
"""
Gera o PLANO DE POSES do dataset: uma lista fixa e reproduzivel de poses do
braco servo6dof, cada uma com um id proprio.

O plano e' a "fonte da verdade" da geracao em etapas: o script de captura le
este arquivo, pula as poses ja fotografadas e faz so o que falta. Como o plano
e' fixo (semente determinística), parar e continuar sempre gera as MESMAS
poses -- sem duplicar, sem buraco.

Uso:
    python gerar_plano.py                 # 5.000 poses (= 10.000 imagens, 2 cameras)
    python gerar_plano.py --poses 8000    # outro tamanho
    python gerar_plano.py --semente 7     # outro sorteio

Saida: E:\\cerise\\braco\\plano_poses.json
"""
import argparse
import json
import math
import os
import random

# Limites do URDF (mesmos do tirar_fotos.py), com 5% de folga nas pontas para
# nao encostar no batente e o controlador nao recusar a trajetoria.
LIMITES_BRACO = [(-math.pi / 2, math.pi / 2)] * 5
LIMITE_GARRA = (-40 * math.pi / 180, 30 * math.pi / 180)
FOLGA = 0.05

AQUI = os.path.dirname(os.path.abspath(__file__))


def sorteia(rng, lo, hi):
    margem = (hi - lo) * FOLGA
    return round(rng.uniform(lo + margem, hi - margem), 4)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--poses", type=int, default=5000,
                   help="quantas poses (cada uma vira 2 imagens)")
    p.add_argument("--semente", type=int, default=20260909)
    p.add_argument("--saida", default=os.path.join(AQUI, "plano_poses.json"))
    args = p.parse_args()

    rng = random.Random(args.semente)
    poses = []
    for i in range(1, args.poses + 1):
        braco = [sorteia(rng, lo, hi) for lo, hi in LIMITES_BRACO]
        garra = sorteia(rng, *LIMITE_GARRA)
        poses.append({
            "id": i,
            "nome": "p{:06d}".format(i),
            "arm": braco,
            "gripper": garra,
        })

    plano = {
        "versao": 1,
        "semente": args.semente,
        "n_poses": args.poses,
        "cameras_por_pose": 2,
        "imagens_alvo": args.poses * 2,
        "juntas": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"],
        "garra": "joint_6",
        "limites_rad": {
            "braco": [-round(math.pi / 2, 4), round(math.pi / 2, 4)],
            "garra": [round(LIMITE_GARRA[0], 4), round(LIMITE_GARRA[1], 4)],
        },
        "poses": poses,
    }

    with open(args.saida, "w") as f:
        json.dump(plano, f, indent=1)

    tam = os.path.getsize(args.saida) / 1024
    print("plano gerado:", args.saida)
    print("  poses ........ {:,}".format(args.poses))
    print("  imagens alvo . {:,}  (2 cameras por pose)".format(args.poses * 2))
    print("  semente ...... {}".format(args.semente))
    print("  tamanho ...... {:.0f} KB".format(tam))
    print("  1a pose ...... id 1  arm={}".format(poses[0]["arm"]))
    print("  ultima ....... id {}  arm={}".format(
        poses[-1]["id"], poses[-1]["arm"]))


if __name__ == "__main__":
    main()
