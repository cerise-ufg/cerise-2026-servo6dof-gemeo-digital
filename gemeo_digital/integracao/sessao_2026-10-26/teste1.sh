for c in camera_frontal camera_diagonal; do
for i in 0 1 2; do
curl -s "http://127.0.0.1:8091/api/quadro/$i?camera=$c" | python3 -c '
import json,sys
q=json.load(sys.stdin)
print(q["camera"], q["idx"], q["id"], "mae %.2f max %.2f ee %.3f m | pred_ms %.1f interno %.1f leitura %.1f pos %.1f | kp %s" % (q["mae_graus"], q["max_graus"], q["erro_efetuador_m"], q["latencia_predictor_ms"], q["latencia_predictor_interna_ms"], q["leitura_ms"], q["pos_ms"], (q["kp2d_pred"] or [])[:2]))
print("  erro", {k: round(v,1) for k,v in q["erro_graus"].items()})
'
done; done
curl -s http://127.0.0.1:8091/api/recursos; echo
