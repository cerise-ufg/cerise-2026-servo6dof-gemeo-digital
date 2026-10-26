#!/usr/bin/env bash
# controle: latencia do predictor alternando as cameras quadro a quadro (mesmo momento de carga da GPU)
I=$HOME/cerise2026/gemeo/integracao
OUT=$I/resultados/controle_latencia_cameras_alternadas.json
python3 - "$OUT" <<'PY'
import json, sys, time, urllib.request, statistics as st, subprocess
res = {"camera_frontal": [], "camera_diagonal": []}
util = []
for k in range(120):
    cam = ["camera_frontal", "camera_diagonal"][k % 2]
    idx = k // 2
    q = json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/quadro/%d?camera=%s" % (idx, cam)))
    res[cam].append(q["latencia_predictor_ms"])
    if k % 10 == 0:
        try:
            util.append(int(subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]).decode().strip()))
        except Exception:
            pass
out = {"descricao": "120 chamadas /api/quadro alternando frontal/diagonal (60 cada), predictor PosePredictor; mede se a diferenca de latencia entre as sessoes vem da camera ou da carga da GPU no momento",
       "data": time.strftime("%Y-%m-%d %H:%M:%S"),
       "util_gpu_amostras_pct": util}
for c, v in res.items():
    v = sorted(v)
    out[c] = {"n": len(v), "mediana_ms": st.median(v), "media_ms": st.mean(v), "p95_ms": v[int(0.95 * (len(v) - 1))], "min_ms": v[0], "max_ms": v[-1]}
json.dump(out, open(sys.argv[1], "w"), indent=2)
print(json.dumps(out, indent=1))
PY
