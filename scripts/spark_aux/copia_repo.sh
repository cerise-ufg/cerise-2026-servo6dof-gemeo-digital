#!/bin/bash
# Copia (nao move) o workspace e os scripts de ~/braco para ~/cerise2026/gemeo/repo
set -e
B=~/braco
R=~/cerise2026/gemeo/repo
mkdir -p $R/ros2_ws $R/docker $R/dataset_tools/legado_wsl $R/docs/slides
cp -a $B/src $R/ros2_ws/
cp -a $B/Dockerfile.spark $R/docker/
cp -a $B/gerar_hd_spark.sh $B/finalizar.sh $B/cams_hd.yaml $B/gerar_plano.py $B/plano_poses.json $B/status_dataset.py $R/dataset_tools/
cp -a $B/rodar.sh $B/continuar.sh $B/gerar_dataset_paralelo.sh $B/ambiente.sh $B/params_*.yaml $B/_teste_*.py $B/_mv.py $B/_watch.py $R/dataset_tools/legado_wsl/
cp -a $B/README.md $R/docs/README_braco_original.md
cp -a $B/GUIA_MOVEIT.md $R/docs/
cp -a $B/slides/. $R/docs/slides/ 2>/dev/null || true
[ -f $B/dataset_run_restore.sh ] && echo "(restore script existe, nao copiado - pertence a producao)"
cd $R && find . -type f | wc -l && du -sh .
