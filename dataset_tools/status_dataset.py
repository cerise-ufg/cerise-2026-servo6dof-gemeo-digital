#!/usr/bin/env python3
"""
Mostra o progresso do dataset em relacao ao plano: quantas poses ja foram
feitas, quantas faltam, quantas imagens, tamanho em disco.

Uso:
    python status_dataset.py
    python status_dataset.py --saida /outra/pasta --plano /outro/plano.json
"""
import argparse
import glob
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plano", default=os.path.join(AQUI, "plano_poses.json"))
    p.add_argument("--saida", default=os.path.join(AQUI, "dataset"))
    args = p.parse_args()

    plano = json.load(open(args.plano))
    ids = [int(x["id"]) for x in plano["poses"]]
    n_cam = plano.get("cameras_por_pose", 2)
    alvo_img = plano.get("imagens_alvo", len(ids) * n_cam)

    feitas = 0
    for i in ids:
        j = os.path.join(args.saida, "{:06d}.json".format(i))
        if os.path.exists(j) and os.path.getsize(j) > 0:
            feitas += 1

    pngs = glob.glob(os.path.join(args.saida, "*.png"))
    bytes_tot = sum(os.path.getsize(x) for x in pngs) if pngs else 0
    falta = len(ids) - feitas
    pct = 100.0 * feitas / len(ids) if ids else 0

    barra_n = int(pct / 2.5)
    barra = "#" * barra_n + "-" * (40 - barra_n)

    print("=" * 52)
    print("  PROGRESSO DO DATASET")
    print("=" * 52)
    print("  [{}] {:.1f}%".format(barra, pct))
    print("  poses feitas ..... {:,} / {:,}".format(feitas, len(ids)))
    print("  poses faltando ... {:,}".format(falta))
    print("  imagens (PNG) .... {:,} / {:,}".format(len(pngs), alvo_img))
    print("  tamanho em disco . {:.2f} GB".format(bytes_tot / 1073741824))
    if feitas:
        print("  media por imagem . {:.0f} KB".format(
            bytes_tot / max(1, len(pngs)) / 1024))
    print("=" * 52)
    if falta == 0:
        print("  COMPLETO! meta de {:,} imagens atingida.".format(alvo_img))
    else:
        # estimativa: ~17 s/pose por worker
        h1 = falta * 17 / 3600
        print("  faltam ~{:,} poses  (~{:.1f} h com 1 worker, "
              "~{:.1f} h com 2)".format(falta, h1, h1 / 2))
        print("  continuar:  bash continuar.sh")


if __name__ == "__main__":
    main()
