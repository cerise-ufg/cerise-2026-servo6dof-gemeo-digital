cd ~/cerise2026/gemeo/repo
bash gemeo_digital/subir_servidor.sh auto > /dev/null 2>&1
{
echo '$ sudo docker ps --filter name=cerise26_gemeo --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"'
sudo docker ps --filter name=cerise26_gemeo --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
echo
echo '$ curl -s http://127.0.0.1:8091/saude'
curl -s http://127.0.0.1:8091/saude; echo
echo
echo '$ curl -s http://127.0.0.1:8091/api/info | python3 -m json.tool | head -12'
curl -s http://127.0.0.1:8091/api/info | python3 -m json.tool | head -12
echo
echo '$ curl -s "http://127.0.0.1:8091/api/quadro/0?camera=camera_frontal" | python3 -c (resumo sem a imagem)'
curl -s "http://127.0.0.1:8091/api/quadro/0?camera=camera_frontal" | python3 -c 'import json,sys; d=json.load(sys.stdin); d["imagem"]=d["imagem"][:40]+"..."; print(json.dumps({k:d[k] for k in ("idx","total","id","camera","imagem","mae_graus","erro_efetuador_m","latencia_predictor_ms","predictor")}, ensure_ascii=False, indent=1))'
echo
echo '$ ss -ltnp | grep 8091   # publicado so no loopback'
ss -ltn | grep 8091
} > ~/cerise2026/gemeo/repo/resultados/servidor_print.log 2>&1
cat ~/cerise2026/gemeo/repo/resultados/servidor_print.log
