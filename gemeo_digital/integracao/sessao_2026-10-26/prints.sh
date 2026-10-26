#!/usr/bin/env bash
I=$HOME/cerise2026/gemeo/integracao
mkdir -p $I/prints
{
echo '$ sudo docker ps --filter name=cerise26_gemeo --format "{{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}"'
sudo docker ps --filter name=cerise26_gemeo --format "{{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}"
echo '$ sudo docker inspect cerise26_gemeo --format "{{.Config.Env}}" | tr " " "\n" | grep GEMEO_'
sudo docker inspect cerise26_gemeo --format "{{.Config.Env}}" | tr " " "\n" | grep GEMEO_
echo '$ sudo docker logs cerise26_gemeo 2>&1 | grep -v "GET\|POST" | head -6'
sudo docker logs cerise26_gemeo 2>&1 | grep -v "GET\|POST" | grep -v "^$" | head -6
echo '$ curl -s http://127.0.0.1:8091/saude'
curl -s http://127.0.0.1:8091/saude; echo
echo '$ curl -s http://127.0.0.1:8091/api/recursos | python3 -m json.tool'
curl -s http://127.0.0.1:8091/api/recursos | python3 -m json.tool
} > $I/prints/servidor.txt 2>&1
{
echo '$ GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh avaliar           # 07:00 (malha fechada, 2 cameras)'
grep "malha fechada" $I/aval.log | head -2
echo '$ GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh avaliar --cameras --fps_fixos 2 5 10   # 07:12'
python3 - $I/resultados/cliente_avaliacao_gpu_fps.json <<'PY'
import json, sys
for s in json.load(open(sys.argv[1]))["sessoes"]:
    print("%-16s fps_alvo=%-14s %4d quadros em %6.1f s -> %.2f quadros/s (cliente) | recebido->desenhado mediana %.1f ms"
          % (s["camera"], s["fps_alvo"], s["acks"], s["duracao_s"], s["fps_cliente"], s["recebido_ate_desenhado_ms"]["mediana"]))
PY
echo '$ GL=swiftshader bash gemeo_digital/integracao/rodar_playwright.sh avaliar --cameras camera_frontal --n_max 40 --fps_fixos'
grep "malha fechada" $I/aval.log | sed -n 3p
echo '$ python3 gemeo_digital/integracao/analisar_gemeo.py --integ /integ --dataset /dataset --pose /pose'
cat $I/resultados/analise_terminal.log
} > $I/prints/avaliacao.txt 2>&1
cp $I/resultados/ros2_twin_pose_terminal.log $I/prints/ros2.txt
wc -l $I/prints/*
