#!/usr/bin/env bash
# avaliacao completa: GPU (malha fechada nas 2 cameras + fps fixos) e depois SwiftShader (40 quadros)
cd ~/cerise2026/gemeo/repo
I=~/cerise2026/gemeo/integracao
mkdir -p $I/logs_teste $I/resultados
mv $I/logs/*.jsonl $I/logs_teste/ 2>/dev/null
echo "=== inicio $(date '+%F %T')"
curl -s http://127.0.0.1:8091/api/recursos; echo
GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh avaliar --saida /integ/resultados/cliente_avaliacao_gpu.json
echo "=== gpu fim $(date '+%F %T')"
curl -s http://127.0.0.1:8091/api/recursos; echo
mkdir -p $I/logs/gpu && mv $I/logs/sessao_*.jsonl $I/logs/gpu/
GL=swiftshader bash gemeo_digital/integracao/rodar_playwright.sh avaliar --cameras camera_frontal --n_max 40 --fps_fixos --saida /integ/resultados/cliente_avaliacao_swiftshader.json
mkdir -p $I/logs/swiftshader && mv $I/logs/sessao_*.jsonl $I/logs/swiftshader/
echo "=== fim $(date '+%F %T')"
curl -s http://127.0.0.1:8091/api/recursos; echo
