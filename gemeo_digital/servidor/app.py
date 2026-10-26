"""
Servidor do Gemeo Digital do servo6dof (FastAPI + WebSocket).

Transmite, quadro a quadro, uma sequencia do dataset: imagem da camera, juntas
de referencia (verdade-base do Gazebo) e juntas previstas por um Predictor
plugavel (ver predictors.py) A PARTIR SOMENTE DA IMAGEM. O front-end (static/)
carrega o URDF + malhas STL com three.js/urdf-loader e desenha dois bracos: a
referencia e o gemeo digital.

Rotas:
  GET  /                      front-end
  GET  /api/info              metadados (predictor, sequencia, split, cameras, limites)
  GET  /api/quadro/{idx}      um quadro (JSON) - util para testes
  POST /api/prever            {"camera": "camera_frontal"|"frontal", "png_b64": "..."} -> juntas previstas
                              (usado pelo no ROS 2 com predictor=http)
  GET  /api/recursos          memoria (GPU do torch, RSS, cgroup) e contadores
  GET  /saude                 verificacao simples
  WS   /ws?camera=&fps=&idx=  fluxo de quadros; comandos JSON:
                              {"cmd":"pausar"|"continuar"} {"cmd":"fps","valor":2} (0 = malha fechada:
                              o proximo quadro so sai quando o cliente confirma a renderizacao do anterior)
                              {"cmd":"camera","valor":"camera_diagonal"} {"cmd":"ir","idx":10}
                              {"cmd":"ack","seq":n,"t_cli_recebido":s,"t_cli_render":s}  (confirmacao do
                              front-end apos desenhar o quadro -> latencia ponta a ponta)
  GET  /urdf/servo6dof.urdf   URDF gerado do xacro (package:// mantido)
  GET  /pkg/servo6dof_description/...  malhas do pacote de descricao

Variaveis de ambiente: GEMEO_DATASET (/dataset), GEMEO_REPO (/repo),
GEMEO_PREDICTOR (auto|gt|ruido|pose|http), GEMEO_POSE_DIR (/pose),
GEMEO_N_QUADROS (150; 0 = todos), GEMEO_SPLIT (teste|validacao|treino),
GEMEO_SPLIT_FONTE (auto|pose|mod10: 'pose' = mesmo split 80/10/10 da frente de pose,
semente 2026, lido de <pose>/dados/final/index.npz), GEMEO_LOG_DIR (se definido, grava
um JSONL por sessao WebSocket com todas as medicoes de cada quadro).
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
import threading
import time

import numpy as np
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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
SPLIT_FONTE = os.environ.get("GEMEO_SPLIT_FONTE", "auto").lower()
POSE_DIR = os.environ.get("GEMEO_POSE_DIR", "/pose")
LOG_DIR = os.environ.get("GEMEO_LOG_DIR", "")
JUNTAS = predictors.JUNTAS
T_INICIO_SERVIDOR = time.time()


def split_mod10(i):
    """Divisao do DATASET.md: id % 10 -> 0..7 treino, 8 validacao, 9 teste."""
    r = i % 10
    return "treino" if r < 8 else ("validacao" if r == 8 else "teste")


def ids_split_pose():
    """Ids do split da FRENTE DE POSE (80/10/10 por pose, semente 2026): avaliar o gemeo no
    mesmo conjunto de teste em que o modelo foi avaliado (nenhuma imagem de treino)."""
    nome = {"teste": "teste", "validacao": "val", "treino": "treino"}[SPLIT]
    idx = os.path.join(POSE_DIR, "dados", "final", "index.npz")
    if os.path.exists(idx):
        d = np.load(idx)
        return set(int(i) for i in d[nome + "_ids"]), "frente de pose (index.npz, semente 2026)"
    perm = np.random.default_rng(2026).permutation(np.arange(1, 5001))
    faixa = {"treino": perm[:4000], "validacao": perm[4000:4500], "teste": perm[4500:]}[SPLIT]
    return set(int(i) for i in faixa), "frente de pose (semente 2026 recalculada)"


def carregar_sequencia():
    fonte = SPLIT_FONTE
    if fonte == "auto":
        fonte = "pose" if os.path.exists(os.path.join(POSE_DIR, "READY.json")) else "mod10"
    if fonte == "pose":
        aceitos, desc = ids_split_pose()
        no_split = aceitos.__contains__
    else:
        desc = "id mod 10 (DATASET.md)"
        no_split = lambda i: split_mod10(i) == SPLIT  # noqa: E731
    metas = {}
    for p in glob.glob(os.path.join(DATASET, "[0-9]" * 6 + ".json")):
        i = int(os.path.basename(p)[:6])
        if not no_split(i):
            continue
        try:
            metas[i] = json.load(open(p))
        except Exception:
            continue
    if not metas:
        return [], {}, desc
    ids = sorted(metas)
    vet = {i: np.array([(metas[i].get("juntas_reais") or metas[i]["juntas_comandadas"])[j] for j in JUNTAS[:5]])
           for i in ids}
    limite = len(ids) if N_QUADROS <= 0 else min(N_QUADROS, len(ids))
    # ordem por vizinho mais proximo no espaco de juntas -> animacao mais suave
    atual = min(ids, key=lambda i: np.linalg.norm(vet[i]))
    restantes = set(ids) - {atual}
    ordem = [atual]
    while restantes and len(ordem) < limite:
        atual = min(restantes, key=lambda i: np.linalg.norm(vet[i] - vet[ordem[-1]]))
        restantes.discard(atual)
        ordem.append(atual)
    return ordem, {i: metas[i] for i in ordem}, desc


SEQ, METAS, SPLIT_DESC = carregar_sequencia()
PREDICTOR, AVISO_PREDICTOR = predictors.carregar_predictor()
TRAVA_PRED = threading.Lock()   # o predictor (GPU) atende o WebSocket e o POST /api/prever
MODELO = ModeloURDF(URDF)
LIMITES = {j: [MODELO.juntas[j].inf, MODELO.juntas[j].sup] for j in JUNTAS}
CACHE = {}
CONTADORES = {"quadros": 0, "acks": 0, "prever": 0, "sessoes": 0}

app = FastAPI(title="Gemeo Digital servo6dof - CERISE 2026")
app.mount("/static", StaticFiles(directory=os.path.join(AQUI, "static")), name="static")
app.mount("/pkg/servo6dof_description", StaticFiles(directory=PKG_DESC), name="pkg")


def prever(rgb, camera, meta=None):
    with TRAVA_PRED:
        t0 = time.perf_counter()
        pred = predictors.chamar(PREDICTOR, rgb, camera, meta)
        dt = 1000 * (time.perf_counter() - t0)
    return pred, dt


def quadro(idx, camera):
    if not SEQ:
        return {"tipo": "erro", "mensagem": "sequencia vazia (dataset em %s?)" % DATASET}
    t_ini = time.time()
    idx = idx % len(SEQ)
    chave = (idx, camera)
    i = SEQ[idx]
    meta = METAS[i]
    t0 = time.perf_counter()
    rgb = np.asarray(Image.open(os.path.join(DATASET, "%06d_%s_image.png" % (i, camera))).convert("RGB"))
    t1 = time.perf_counter()
    # o gemeo recebe SO a imagem (meta so vai para os oraculos gt/ruido, que declaram usa_meta)
    pred, pred_ms = prever(rgb, camera, meta)
    t2 = time.perf_counter()
    gt = predictors.GroundTruthPredictor().predict(None, camera, meta)
    erro = {j: math.degrees(pred[j] - gt[j]) for j in JUNTAS if j in pred and j in gt}
    braco = [abs(erro[j]) for j in JUNTAS[:5] if j in erro]
    if chave in CACHE:
        img64 = CACHE[chave]
    else:
        buf = io.BytesIO()
        Image.fromarray(rgb).resize((640, 360), Image.BILINEAR).save(buf, format="JPEG", quality=82)
        img64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        if len(CACHE) < 4 * max(len(SEQ), 1):
            CACHE[chave] = img64
    # posicao do efetuador (FK) para referencia e gemeo; a garra (joint_6) nao entra no erro
    q_pred_fk = dict(pred)
    q_pred_fk.setdefault("joint_6", gt.get("joint_6", 0.0))
    p_gt = MODELO.fk(gt)["base_garra"][:3, 3]
    p_pr = MODELO.fk(q_pred_fk)["base_garra"][:3, 3]
    extra = getattr(PREDICTOR, "ultima_saida_extra", None) or {}
    t3 = time.perf_counter()
    CONTADORES["quadros"] += 1
    return {
        "tipo": "quadro", "idx": idx, "total": len(SEQ), "id": i, "camera": camera,
        "imagem": img64, "gt": gt, "pred": pred, "erro_graus": erro,
        "mae_graus": float(np.mean(braco)) if braco else None,
        "max_graus": float(np.max(braco)) if braco else None,
        "erro_efetuador_m": float(np.linalg.norm(p_gt - p_pr)),
        "efetuador_gt_m": [round(float(x), 6) for x in p_gt],
        "efetuador_pred_m": [round(float(x), 6) for x in p_pr],
        "kp2d_pred": extra.get("keypoints_2d"),
        "latencia_predictor_ms": pred_ms,
        "latencia_predictor_interna_ms": getattr(PREDICTOR, "ultima_latencia_ms", None),
        "leitura_ms": 1000 * (t1 - t0), "pos_ms": 1000 * (t3 - t2),
        "t_srv_inicio": t_ini,
        "predictor": PREDICTOR.nome,
    }


@app.get("/")
def raiz():
    return FileResponse(os.path.join(AQUI, "static", "index.html"))


@app.get("/saude")
def saude():
    return {"ok": True, "quadros": len(SEQ), "predictor": PREDICTOR.nome, "split": SPLIT_DESC}


@app.get("/urdf/servo6dof.urdf")
def urdf():
    return FileResponse(URDF, media_type="application/xml")


@app.get("/api/info")
def info():
    return {
        "predictor": PREDICTOR.nome, "aviso_predictor": AVISO_PREDICTOR,
        "predictor_usa_so_imagem": not getattr(PREDICTOR, "usa_meta", False),
        "n_quadros": len(SEQ), "split": SPLIT, "split_fonte": SPLIT_DESC, "ids": SEQ, "juntas": JUNTAS,
        "limites_rad": LIMITES, "cameras": CAMERAS, "urdf": "/urdf/servo6dof.urdf",
        "pacotes": {"servo6dof_description": "/pkg/servo6dof_description"},
    }


def _ler(caminho):
    try:
        return open(caminho).read().strip()
    except Exception:
        return None


@app.get("/api/recursos")
def recursos():
    r = {"predictor": PREDICTOR.nome, "uptime_s": round(time.time() - T_INICIO_SERVIDOR, 1),
         "contadores": CONTADORES, "t_carga_predictor_s": getattr(PREDICTOR, "t_carga", None)}
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        r["gpu_torch"] = {
            "alocada_GB": round(torch.cuda.memory_allocated() / 1e9, 3),
            "reservada_GB": round(torch.cuda.memory_reserved() / 1e9, 3),
            "pico_alocada_GB": round(torch.cuda.max_memory_allocated() / 1e9, 3),
            "pico_reservada_GB": round(torch.cuda.max_memory_reserved() / 1e9, 3),
            "dispositivo": torch.cuda.get_device_name(0),
        }
    for linha in (_ler("/proc/self/status") or "").splitlines():
        if linha.startswith(("VmRSS", "VmHWM")):
            k, v = linha.split(":", 1)
            r[k] = v.strip()
    for k in ("memory.current", "memory.peak", "memory.max"):
        v = _ler("/sys/fs/cgroup/" + k)
        if v is not None:
            r["cgroup_" + k.replace(".", "_")] = v if not v.isdigit() else round(int(v) / 1e9, 3)
    return r


@app.post("/api/prever")
async def api_prever(req: Request):
    corpo = await req.json()
    camera = corpo.get("camera", "camera_frontal")
    if not camera.startswith("camera_"):
        camera = "camera_" + camera
    rgb = np.asarray(Image.open(io.BytesIO(base64.b64decode(corpo["png_b64"]))).convert("RGB"))
    if getattr(PREDICTOR, "usa_meta", False):
        return JSONResponse({"erro": "predictor atual (%s) precisa da anotacao; suba em modo pose" % PREDICTOR.nome},
                            status_code=409)
    loop = asyncio.get_running_loop()
    pred, dt = await loop.run_in_executor(None, prever, rgb, camera, None)
    CONTADORES["prever"] += 1
    extra = getattr(PREDICTOR, "ultima_saida_extra", None) or {}
    return {"joints": pred, "latency_ms": dt, "latencia_interna_ms": getattr(PREDICTOR, "ultima_latencia_ms", None),
            "keypoints_2d": extra.get("keypoints_2d"), "camera": camera, "predictor": PREDICTOR.nome}


@app.get("/api/quadro/{idx}")
async def api_quadro(idx: int, camera: str = "camera_frontal"):
    loop = asyncio.get_running_loop()
    return JSONResponse(await loop.run_in_executor(None, quadro, idx, camera))


class RegistroSessao:
    """Guarda as medicoes de cada quadro enviado e casa com a confirmacao (ack) do front-end."""

    CAMPOS = ("idx", "id", "camera", "gt", "pred", "erro_graus", "mae_graus", "max_graus", "erro_efetuador_m",
              "kp2d_pred", "latencia_predictor_ms", "latencia_predictor_interna_ms", "leitura_ms", "pos_ms",
              "t_srv_inicio", "t_srv_envio", "bytes", "fps_alvo")

    def __init__(self, cliente):
        CONTADORES["sessoes"] += 1
        self.nome = time.strftime("%Y%m%d_%H%M%S") + "_s%d" % CONTADORES["sessoes"]
        self.pendentes = {}
        self.arq = None
        self.ultimo_e2e_ms = None
        if LOG_DIR:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.arq = open(os.path.join(LOG_DIR, "sessao_%s.jsonl" % self.nome), "w")
            self._gravar({"tipo": "sessao", "sessao": self.nome, "cliente": cliente, "predictor": PREDICTOR.nome,
                          "split": SPLIT_DESC, "n_quadros": len(SEQ), "t": time.time()})

    def _gravar(self, d):
        if self.arq:
            self.arq.write(json.dumps(d) + "\n")
            self.arq.flush()

    def enviado(self, seq, q):
        r = {k: q.get(k) for k in self.CAMPOS}
        r.update({"tipo": "quadro", "sessao": self.nome, "seq": seq})
        self.pendentes[seq] = r
        if len(self.pendentes) > 64:  # cliente que nao confirma: grava sem ack
            s0 = min(self.pendentes)
            self._gravar(self.pendentes.pop(s0))

    def ack(self, msg, t_ack):
        r = self.pendentes.pop(int(msg.get("seq", -1)), None)
        if r is None:
            return
        CONTADORES["acks"] += 1
        tr, trd = msg.get("t_cli_recebido"), msg.get("t_cli_render")
        r.update({"t_ack": t_ack, "t_cli_recebido": tr, "t_cli_render": trd,
                  "rtt_ms": 1000 * (t_ack - r["t_srv_inicio"]),
                  # relogio comum: navegador e servidor no mesmo host (Playwright no Spark)
                  "e2e_ms": 1000 * (trd - r["t_srv_inicio"]) if trd else None,
                  "render_cli_ms": 1000 * (trd - tr) if (tr and trd) else None})
        self.ultimo_e2e_ms = r["rtt_ms"]
        self._gravar(r)

    def fechar(self):
        for s in sorted(self.pendentes):
            self._gravar(self.pendentes[s])
        self.pendentes.clear()
        if self.arq:
            self.arq.close()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    qp = websocket.query_params
    cam0 = qp.get("camera", "camera_frontal")
    est = {"idx": int(qp.get("idx", 0) or 0) % max(len(SEQ), 1), "rodando": qp.get("pausado") != "1",
           "fps": float(qp.get("fps", 2) or 0), "camera": cam0 if cam0 in CAMERAS else "camera_frontal",
           "passo": qp.get("pausado") == "1"}
    loop = asyncio.get_running_loop()
    reg = RegistroSessao(str(websocket.client))
    evento_ack = asyncio.Event()
    seq = 0

    async def receber():
        while True:
            msg = json.loads(await websocket.receive_text())
            c = msg.get("cmd")
            if c == "ack":
                reg.ack(msg, time.time())
                evento_ack.set()
            elif c == "pausar":
                est["rodando"] = False
            elif c == "continuar":
                est["rodando"] = True
            elif c == "fps":
                v = float(msg.get("valor", 2))
                est["fps"] = 0.0 if v <= 0 else max(0.2, min(30.0, v))
            elif c == "camera" and msg.get("valor") in CAMERAS:
                if msg["valor"] != est["camera"]:
                    est["camera"] = msg["valor"]
                    est["passo"] = True
            elif c == "ir":
                est["idx"] = int(msg.get("idx", 0)) % max(len(SEQ), 1)
                est["passo"] = True

    tarefa = asyncio.create_task(receber())
    try:
        while True:
            t_ciclo = time.perf_counter()
            if est["rodando"] or est["passo"]:
                q = await loop.run_in_executor(None, quadro, est["idx"], est["camera"])
                seq += 1
                q["seq"] = seq
                q["fps_alvo"] = est["fps"]
                q["e2e_ultimo_ms"] = reg.ultimo_e2e_ms
                q["t_srv_envio"] = time.time()
                texto = json.dumps(q)
                q["bytes"] = len(texto)
                evento_ack.clear()
                await websocket.send_text(texto)
                reg.enviado(seq, q)
                if est["rodando"] and not est["passo"]:
                    est["idx"] = (est["idx"] + 1) % max(len(SEQ), 1)
                est["passo"] = False
                if est["fps"] <= 0:  # malha fechada: espera o front-end confirmar que desenhou
                    try:
                        await asyncio.wait_for(evento_ack.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
            if est["fps"] > 0 or not (est["rodando"] or est["passo"]):
                periodo = 1.0 / est["fps"] if est["fps"] > 0 else 0.05
                await asyncio.sleep(max(0.0, periodo - (time.perf_counter() - t_ciclo)))
            if tarefa.done():
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        tarefa.cancel()
        reg.fechar()
