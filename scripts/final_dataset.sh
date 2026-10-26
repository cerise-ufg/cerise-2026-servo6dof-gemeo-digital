#!/usr/bin/env bash
# Rodada FINAL apos o termino da geracao (dataset completo): analise do dataset,
# validacao modelo x imagens, renders, reinicio do servidor e capturas.
cd "$(dirname "$0")/.."
set -x
bash dataset_tools/analise/rodar_analise.sh 0
bash scripts/rodar_container.sh rvc "python3 dataset_tools/analise/real_vs_comandado.py --meta /dataset_meta"
bash scripts/rodar_container.sh iou "python3 modelo_digital/validar_projecao.py --n 1000 --proc 6"
bash scripts/rodar_container.sh rend "python3 modelo_digital/render_modelo.py --so sobreposicao --ids 1 2 7"
bash gemeo_digital/capturas/sessao_capturas.sh
echo FINAL_OK
