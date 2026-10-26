"""
Servidor do Gemeo Digital do servo6dof (FastAPI + WebSocket).

Transmite, quadro a quadro, uma sequencia de teste do dataset: imagem da
camera, juntas de referencia (verdade-base do Gazebo) e juntas previstas por
um Predictor plugavel (ver predictors.py). O front-end (static/) carrega o
URDF + malhas STL com three.js/urdf-loader e desenha dois bracos: a
referencia e o gemeo digital.

Rotas:
  GET  /                      front-end
  GET  /api/info              metadados (predictor, sequencia, cameras, limites)
  GET  /api/quadro/{idx}      um quadro (JSON) - util para testes
  GET  /saude                 verificacao simples
  WS   /ws                    fluxo de quadros; comandos JSON:
                              {"cmd":"pausar"|"continuar"} {"cmd":"fps","valor":2}
                              {"cmd":"camera","valor":"camera_diagonal"} {"cmd":"ir","idx":10}
  GET  /urdf/servo6dof.urdf   URDF gerado do xacro (package:// mantido)
  GET  /pkg/servo6dof_description/...  malhas do pacote de descricao

Variaveis de ambiente: GEMEO_DATASET (/dataset), GEMEO_REPO (/repo),
GEMEO_PREDICTOR (auto|gt|ruido|pose|http), GEMEO_POSE_DIR (/pose),
GEMEO_N_QUADROS (150), GEMEO_SPLIT (teste).
Subir:  uvicorn app:app --host 0.0.0.0 --port 8091  (no container; publicado so em 127.0.0.1)
"""
import asyncio
import base64
import glob
import io
import json
import math
import os
import sys
import time

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import predictors  # noqa: E402

REPO = os.environ.get("GEMEO_REPO", os.path.abspath(os.path.join(AQUI, "..", "..")))
sys.path.insert(0, os.path.join(REPO, "modelo_digital"))
from cinematica import CAMERAS, ModeloURDF  # noqa: E402

DATASET = os.environ.get("GEMEO_DATASET", "/dataset")
URDF = os.path.join(REPO, "modelo_digital", "urdf", "servo6dof.urdf")
PKG_DESC = os.path.join(REPO, "ros2_ws", "src", "servo6dof", "servo6dof_description")
N_QUADROS = int(os.environ.get("GEMEO_N_QUADROS", "150"))
SPLIT = os.environ.get("GEMEO_SPLIT", "teste")
JUNTAS = predictors.JUNTAS


def split_de(i):
    """Divisao recomendada no DATASET.md: id % 10 -> 0..7 treino, 8 validacao, 9 teste."""
    r = i % 10
    return "treino" if r < 8 else ("validacao" if r == 8 else "teste")


def carregar_sequencia():
    metas = {}
    for p in glob.glob(os.path.join(DATASET, "[0-9]" * 6 + ".json")):
        i = int(os.path.basename(p)[:6])
        if split_de(i) != SPLIT:
            continue
        try:
            metas[i] = json.load(open(p))
        except Exception:
            continue
    if not metas:
        return [], {}
    ids = sorted(metas)
    vet = {i: np.array([metas[i]["juntas_comandadas"][j] for j in JUNTAS[:5]]) for i in ids}
    # ordem por vizinho mais proximo no espaco de juntas -> animacao mais suave
    atual = min(ids, key=lambda i: np.linalg.norm(vet[i]))
    restantes = set(ids) - {atual}
    ordem = [atual]
    while restantes and len(ordem) < N_QUADROS:
        atual = min(restantes, key=lambda i: np.linalg.norm(vet[i] - vet[ordem[-1]]))
        restantes.discard(atual)
        ordem.append(atual)
    return ordem, {i: metas[i] for i in ordem}


SEQ, METAS = carregar_sequencia()
PREDICTOR, AVISO_PREDICTOR = predictors.carregar_predictor()
MODELO = ModeloURDF(URDF)
LIMITES = {j: [MODELO.juntas[j].inf, MODELO.juntas[j].sup] for j in JUNTAS}
CACHE = {}

app = FastAPI(title="Gemeo Digital servo6dof - CERISE 2026")
app.mount("/static", StaticFiles(directory=os.path.join(AQUI, "static")), name="static")
app.mount("/pkg/servo6dof_description", StaticFiles(directory=PKG_DESC), name="pkg")


def quadro(idx, camera):
    if not SEQ:
        return {"tipo": "erro", "mensagem": "sequencia vazia (dataset em %s?)" % DATASET}
    idx = idx % len(SEQ)
    chave = (idx, camera)
    i = SEQ[idx]
    meta = METAS[i]
    t0 = time.time()
    rgb = np.asarray(Image.open(os.path.join(DATASET, "%06d_%s_image.png" % (i, camera))).convert("RGB"))
    t1 = time.time()
    pred = predictors.chamar(PREDICTOR, rgb, camera, meta)
    t2 = time.time()
    gt = predictors.GroundTruthPredictor().predict(None, camera, meta)
    erro = {j: math.degrees(pred[j] - gt[j]) for j in JUNTAS if j in pred and j in gt}
    braco = [abs(erro[j]) for j in JUNTAS[:5] if j in erro]
    if chave in CACHE:
        img64 = CACHE[chave]
    else:
        buf = io.BytesIO()
        Image.fromarray(rgb).resize((640, 360), Image.BILINEAR).save(buf, format="JPEG", quality=82)
        img64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        if len(CACHE) < 4 * N_QUADROS:
            CACHE[chave] = img64
    # posicao do efetuador (FK) para referencia e gemeo
    p_gt = MODELO.fk(gt)["base_garra"][:3, 3]
    p_pr = MODELO.fk(pred)["base_garra"][:3, 3]
    return {
        "tipo": "quadro", "idx": idx, "total": len(SEQ), "id": i, "camera": camera,
        "imagem": img64, "gt": gt, "pred": pred, "erro_graus": erro,
        "mae_graus": float(np.mean(braco)) if braco else None,
        "max_graus": float(np.max(braco)) if braco else None,
        "erro_efetuador_m": float(np.linalg.norm(p_gt - p_pr)),
        "efetuador_gt_m": [round(float(x), 6) for x in p_gt],
        "efetuador_pred_m": [round(float(x), 6) for x in p_pr],
        "latencia_predictor_ms": 1000 * (t2 - t1), "leitura_ms": 1000 * (t1 - t0),
        "predictor": PREDICTOR.nome,
    }


@app.get("/")
def raiz():
    return FileResponse(os.path.join(AQUI, "static", "index.html"))


@app.get("/saude")
def saude():
    return {"ok": True, "quadros": len(SEQ), "predictor": PREDICTOR.nome}


@app.get("/urdf/servo6dof.urdf")
def urdf():
    return FileResponse(URDF, media_type="application/xml")


@app.get("/api/info")
def info():
    return {
        "predictor": PREDICTOR.nome, "aviso_predictor": AVISO_PREDICTOR,
        "n_quadros": len(SEQ), "split": SPLIT, "ids": SEQ, "juntas": JUNTAS, "limites_rad": LIMITES,
        "cameras": CAMERAS, "urdf": "/urdf/servo6dof.urdf",
        "pacotes": {"servo6dof_description": "/pkg/servo6dof_description"},
    }


@app.get("/api/quadro/{idx}")
async def api_quadro(idx: int, camera: str = "camera_frontal"):
    loop = asyncio.get_running_loop()
    return JSONResponse(await loop.run_in_executor(None, quadro, idx, camera))


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    est = {"idx": 0, "rodando": True, "fps": 2.0, "camera": "camera_frontal", "passo": False}
    loop = asyncio.get_running_loop()

    async def receber():
        while True:
            msg = json.loads(await websocket.receive_text())
            c = msg.get("cmd")
            if c == "pausar":
                est["rodando"] = False
            elif c == "continuar":
                est["rodando"] = True
            elif c == "fps":
                est["fps"] = max(0.2, min(15.0, float(msg.get("valor", 2))))
            elif c == "camera" and msg.get("valor") in CAMERAS:
                est["camera"] = msg["valor"]
                est["passo"] = True
            elif c == "ir":
                est["idx"] = int(msg.get("idx", 0)) % max(len(SEQ), 1)
                est["passo"] = True

    tarefa = asyncio.create_task(receber())
    try:
        while True:
            if est["rodando"] or est["passo"]:
                q = await loop.run_in_executor(None, quadro, est["idx"], est["camera"])
                await websocket.send_text(json.dumps(q))
                if est["rodando"] and not est["passo"]:
                    est["idx"] = (est["idx"] + 1) % max(len(SEQ), 1)
                est["passo"] = False
            await asyncio.sleep(1.0 / est["fps"])
            if tarefa.done():
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        tarefa.cancel()
