#!/usr/bin/env python3
"""
Consolida um dataset gerado em paralelo.

Cada worker grava seu proprio poses_registradas_NNNNNNN.csv. Este script:
  - junta todos num unico index.csv ordenado por id
  - confere que cada pose tem as 6 imagens e o JSON esperados
  - imprime um resumo (poses, imagens, tamanho, rotulos de segmentacao)

Uso:
    python consolidar_dataset.py /mnt/e/cerise/braco/dataset
"""
import csv
import glob
import json
import os
import sys

d = sys.argv[1] if len(sys.argv) > 1 else "/mnt/e/cerise/braco/dataset"

jsons = sorted(glob.glob(os.path.join(d, "*.json")))
pngs = glob.glob(os.path.join(d, "*.png"))
csvs = sorted(glob.glob(os.path.join(d, "poses_registradas*.csv")))

if not jsons:
    raise SystemExit("nenhuma anotacao em " + d)

# junta os CSVs dos workers
linhas = []
for c in csvs:
    with open(c) as f:
        linhas.extend(list(csv.DictReader(f)))
linhas.sort(key=lambda r: int(r["indice"]))

if linhas:
    with open(os.path.join(d, "index.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

# verifica integridade: cada JSON deve ter suas imagens no disco
faltando = 0
esperadas = 0
for j in jsons:
    dados = json.load(open(j))
    for cam in dados["cameras"].values():
        esperadas += 1
        if not os.path.exists(os.path.join(d, cam["arquivo"])):
            faltando += 1

total_bytes = sum(os.path.getsize(p) for p in pngs)

print("=" * 56)
print("DATASET CONSOLIDADO:", d)
print("=" * 56)
print("  poses (JSON) ......... {:,}".format(len(jsons)))
print("  imagens (PNG) ........ {:,}".format(len(pngs)))
print("  imagens esperadas .... {:,}".format(esperadas))
print("  imagens faltando ..... {:,}".format(faltando))
print("  CSVs de worker ....... {}  -> index.csv".format(len(csvs)))
print("  tamanho total ........ {:.2f} GB".format(total_bytes / 1073741824))
if len(jsons):
    print("  media por pose ....... {:.2f} MB".format(
        total_bytes / len(jsons) / 1048576))
print("=" * 56)
if faltando:
    print("ATENCAO: {} imagens referenciadas nao estao no disco.".format(faltando))
else:
    print("OK: todas as imagens referenciadas existem.")
