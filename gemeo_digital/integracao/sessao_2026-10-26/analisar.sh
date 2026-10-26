#!/usr/bin/env bash
cd ~/cerise2026/gemeo/repo
I=$HOME/cerise2026/gemeo/integracao
EXTRA="-v $I:/integ -v $HOME/cerise2026/pose:/pose:ro" CPUS=4 MEM=8g bash scripts/rodar_container.sh analise \
  "python3 gemeo_digital/integracao/analisar_gemeo.py --integ /integ --dataset /dataset --pose /pose --repo /repo --recursos /integ/resultados/recursos_servidor_pos_avaliacao.json" 2>&1 | tee $I/resultados/analise_terminal.log
