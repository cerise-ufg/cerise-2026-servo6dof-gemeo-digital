#!/usr/bin/env python3
"""
Atualiza o numero de imagens citado na slide "Atividades Realizadas".

Conta os PNGs da pasta do dataset e reescreve a frase
"dataset concluido com N imagens" dentro do .pptx.

Uso:
    python atualizar_numero.py                      # conta ../dataset
    python atualizar_numero.py --dataset D:\\outro   # outra pasta
    python atualizar_numero.py --n 5200             # forca um numero

Rode isso antes de apresentar: se a geracao continuou depois que o deck foi
montado, o numero no slide fica defasado.
"""
import argparse
import glob
import os
import re
import shutil
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))

p = argparse.ArgumentParser()
p.add_argument("--pptx", default=os.path.join(AQUI, "Slides Eduardo - dataset.pptx"))
p.add_argument("--dataset", default=os.path.join(AQUI, "..", "dataset"))
p.add_argument("--n", type=int, default=None)
args = p.parse_args()

if args.n is not None:
    n = args.n
    origem = "informado na linha de comando"
else:
    n = len(glob.glob(os.path.join(args.dataset, "*.png")))
    origem = os.path.abspath(args.dataset)

if n == 0:
    raise SystemExit("nenhum PNG encontrado em " + origem)

if not os.path.exists(args.pptx):
    raise SystemExit("pptx nao encontrado: " + args.pptx)

ALVO = "ppt/slides/slide3.xml"
PADRAO = re.compile(r"(dataset conclu\u00eddo com )([\d\.]+|__N_IMAGENS__)( imagens)")

with zipfile.ZipFile(args.pptx) as z:
    partes = {nome: z.read(nome) for nome in z.namelist()}
    ordem = z.namelist()

xml = partes[ALVO].decode("utf-8")
achou = PADRAO.search(xml)
if not achou:
    raise SystemExit("frase alvo nao encontrada na slide 3 -- o texto mudou?")

antigo = achou.group(2)
# separador de milhar no padrao brasileiro
formatado = "{:,}".format(n).replace(",", ".")
xml_novo = PADRAO.sub(lambda m: m.group(1) + formatado + m.group(3), xml)
partes[ALVO] = xml_novo.encode("utf-8")

backup = args.pptx + ".bak"
shutil.copyfile(args.pptx, backup)

with zipfile.ZipFile(args.pptx, "w", zipfile.ZIP_DEFLATED) as z:
    for nome in ordem:
        z.writestr(nome, partes[nome])

print("fonte da contagem:", origem)
print("imagens:", n)
print("slide 3: '{}' -> '{}'".format(antigo, formatado))
print("backup do anterior em:", backup)
