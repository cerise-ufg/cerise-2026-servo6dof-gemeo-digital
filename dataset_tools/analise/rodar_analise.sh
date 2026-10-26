#!/usr/bin/env bash
# Pipeline completo de analise do dataset (roda no host do Spark; usa o container de ferramentas).
#   bash dataset_tools/analise/rodar_analise.sh [amostra_integridade]   (0 = todas as imagens)
cd "$(dirname "$0")/../.."
AMOSTRA="${1:-0}"
bash scripts/rodar_container.sh idx "python3 dataset_tools/analise/indexar.py --dataset /dataset --saida /dataset_meta --plano /repo/dataset_tools/plano_poses.json"
bash scripts/rodar_container.sh integ "python3 dataset_tools/analise/integridade.py --dataset /dataset --meta /dataset_meta --proc 6 --amostra $AMOSTRA"
bash scripts/rodar_container.sh estat "python3 dataset_tools/analise/estatisticas.py --meta /dataset_meta"
bash scripts/rodar_container.sh grade "python3 dataset_tools/analise/grades.py --dataset /dataset --meta /dataset_meta --n 4 --amostra 8"
bash scripts/rodar_container.sh tempo "python3 dataset_tools/analise/linha_tempo.py --meta /dataset_meta --logs /braco"
cp ~/cerise2026/gemeo/dataset_meta/index_resumo.json resultados/dataset_index_resumo.json
