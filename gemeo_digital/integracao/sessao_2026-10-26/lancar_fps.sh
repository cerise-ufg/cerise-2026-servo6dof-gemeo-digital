#!/usr/bin/env bash
# refaz as sessoes com taxa-alvo fixa (a 1a rodada caiu em malha fechada: ?fps=2.0 nao casava com as opcoes do select)
cd ~/cerise2026/gemeo/repo
I=~/cerise2026/gemeo/integracao
mkdir -p $I/logs_invalidas
mv $I/logs/gpu/sessao_20261026_100227_s8.jsonl $I/logs/gpu/sessao_20261026_100237_s9.jsonl $I/logs_invalidas/ 2>/dev/null
mv $I/logs/sessao_*.jsonl $I/logs/swiftshader/ 2>/dev/null
echo "=== fps fixos $(date '+%F %T')"
GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh avaliar --cameras --fps_fixos 2 5 10 --n_fps 60 --saida /integ/resultados/cliente_avaliacao_gpu_fps.json
mv $I/logs/sessao_*.jsonl $I/logs/gpu/
curl -s http://127.0.0.1:8091/api/recursos > $I/resultados/recursos_servidor_pos_avaliacao.json
echo "=== fim fps $(date '+%F %T')"
ls $I/logs/gpu $I/logs/swiftshader
