"""
Predictors plugaveis do gemeo digital: recebem a imagem RGB de uma camera e
devolvem os angulos estimados das juntas do servo6dof.

Interface (contrato com a frente do modelo de pose):

    class Predictor:
        nome: str
        def predict(self, rgb: np.ndarray, camera: str) -> dict[str, float]

    - rgb:    np.ndarray uint8 (H, W, 3), ordem RGB, 1280x720 no dataset;
    - camera: "camera_frontal" | "camera_diagonal";
    - retorno: {"joint_1": rad, ..., "joint_5": rad, ["joint_6": rad]}.
      Tambem sao aceitos (e normalizados por `normalizar_saida`): lista/array
      [j1..j5(,j6)], ou dict {"juntas": {...}}; graus se READY.json disser
      "unidade": "graus".

Implementacoes:
    GroundTruthPredictor  - oraculo: devolve a verdade-base do JSON (erro 0);
    RuidoPredictor        - GT + ruido gaussiano (DEMONSTRACAO do painel de
                            erro; nao e' resultado de modelo);
    PosePredictorAdapter  - carrega a classe PosePredictor publicada pela
                            frente de pose em <pasta>/inferencia/predict.py,
                            quando <pasta>/READY.json existir;
    HttpPredictor         - envia o PNG para um servico HTTP externo.
"""
import importlib.util
import io
import json
import math
import os
import sys
import time

import numpy as np

JUNTAS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]


class Predictor:
    nome = "base"
    usa_meta = False  # True = recebe a anotacao do quadro (so oraculos)

    def predict(self, rgb, camera):  # pragma: no cover - interface
        raise NotImplementedError


def normalizar_saida(saida, graus=False):
    """Converte a saida de um predictor em {junta: rad}."""
    for chave in ("juntas", "joints"):
        if isinstance(saida, dict) and chave in saida and isinstance(saida[chave], (dict, list, tuple)):
            saida = saida[chave]
            break
    if isinstance(saida, dict):
        d = {k: float(v) for k, v in saida.items() if k in JUNTAS}
    else:
        v = np.asarray(saida, dtype=float).reshape(-1)
        d = {JUNTAS[k]: float(v[k]) for k in range(min(len(v), len(JUNTAS)))}
    if graus:
        d = {k: math.radians(v) for k, v in d.items()}
    return d


class GroundTruthPredictor(Predictor):
    nome = "ground_truth (oraculo)"
    usa_meta = True

    def predict(self, rgb, camera, meta=None):
        if meta is None:
            raise ValueError("GroundTruthPredictor precisa da anotacao do quadro (meta)")
        d = dict(meta.get("juntas_reais") or meta["juntas_comandadas"])
        d["joint_6"] = meta.get("garra_comandada", {}).get("joint_6", 0.0)
        return d


class RuidoPredictor(GroundTruthPredictor):
    """GT + ruido gaussiano. SO para demonstrar o painel de erro."""

    def __init__(self, sigma_graus=3.0, semente=0):
        self.sigma = math.radians(sigma_graus)
        self.rng = np.random.default_rng(semente)
        self.nome = "demo: GT + ruido gaussiano (sigma %.1f graus)" % sigma_graus

    def predict(self, rgb, camera, meta=None):
        d = super().predict(rgb, camera, meta)
        return {k: v + float(self.rng.normal(0, self.sigma)) for k, v in d.items()}


class PosePredictorAdapter(Predictor):
    """Carrega <pasta>/inferencia/predict.py -> class PosePredictor."""

    def __init__(self, pasta):
        pronto = os.path.join(pasta, "READY.json")
        if not os.path.exists(pronto):
            raise FileNotFoundError("modelo de pose ainda nao publicado: falta " + pronto)
        self.info = json.load(open(pronto))
        caminho = os.path.join(pasta, "inferencia", "predict.py")
        dir_inf = os.path.dirname(caminho)
        if dir_inf not in sys.path:
            sys.path.insert(0, dir_inf)
        spec = importlib.util.spec_from_file_location("pose_predict", caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        info = self.info if isinstance(self.info, dict) else {}
        kwargs = dict(info.get("kwargs", {}))
        # aceita tambem "ckpt"/"device" no nivel de cima do READY.json
        for k in ("ckpt", "device", "da_pesos"):
            if k in info and k not in kwargs:
                kwargs[k] = info[k]
        # o READY.json traz o caminho do host (ckpt) e o do container (ckpt_no_container); aqui a pasta
        # da pose esta montada em <pasta>: usa o que existir, ou remapeia ".../cerise2026/pose/..." -> <pasta>/...
        if "ckpt" in kwargs and not os.path.exists(kwargs["ckpt"]):
            cands = [info.get("ckpt_no_container", "")]
            for marca in ("/cerise2026/pose/", "/workspace/pose/"):
                if marca in kwargs["ckpt"]:
                    cands.append(os.path.join(pasta, kwargs["ckpt"].split(marca, 1)[1]))
            for c in cands:
                if c and os.path.exists(c):
                    kwargs["ckpt"] = c
                    break
        t0 = time.time()
        self.modelo = mod.PosePredictor(**kwargs)
        self.t_carga = time.time() - t0
        self.graus = str(info.get("unidade", "rad")).lower().startswith("grau")
        self.nome = "PosePredictor (%s)" % info.get("modelo", info.get("nome", "HPE + Depth Anything V2, frente POSE"))
        self.ultima_latencia_ms = None
        self.ultima_saida_extra = None

    def predict(self, rgb, camera):
        # a frente de pose nomeia as cameras "frontal"/"diagonal"; o servidor usa "camera_frontal"
        curto = camera.replace("camera_", "")
        try:
            out = self.modelo.predict(rgb, camera=curto)
        except (KeyError, AssertionError):
            out = self.modelo.predict(rgb, camera=camera)
        if isinstance(out, dict):
            self.ultima_latencia_ms = out.get("latency_ms")
            # keypoints 2D previstos (px da imagem de entrada) -> desenhados sobre a imagem no front-end
            self.ultima_saida_extra = {"keypoints_2d": [[round(float(u), 1), round(float(v), 1)]
                                                        for u, v in out.get("keypoints_2d", [])]}
        return normalizar_saida(out, graus=self.graus)


class HttpPredictor(Predictor):
    """POST JSON {"camera": str, "png_b64": str} -> JSON de juntas (mesmos formatos aceitos)."""

    def __init__(self, url):
        self.url = url
        self.nome = "HTTP " + url
        self.ultima_latencia_ms = None

    def predict(self, rgb, camera):
        import base64
        import urllib.request
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="PNG", compress_level=1)
        corpo = json.dumps({"camera": camera, "png_b64": base64.b64encode(buf.getvalue()).decode()}).encode()
        req = urllib.request.Request(self.url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            out = json.loads(r.read())
        if isinstance(out, dict):
            self.ultima_latencia_ms = out.get("latency_ms")
        return normalizar_saida(out)


def carregar_predictor(modo=None, pasta_pose=None, url=None):
    """modo: 'gt' | 'ruido' | 'pose' | 'http' | 'auto' (padrao: env GEMEO_PREDICTOR ou 'auto').
    'auto' usa o PosePredictor se READY.json existir; senao cai no GT."""
    modo = (modo or os.environ.get("GEMEO_PREDICTOR", "auto")).lower()
    pasta_pose = pasta_pose or os.environ.get("GEMEO_POSE_DIR", "/pose")
    url = url or os.environ.get("GEMEO_PREDICTOR_URL")
    if modo == "gt":
        return GroundTruthPredictor(), None
    if modo == "ruido":
        return RuidoPredictor(float(os.environ.get("GEMEO_RUIDO_GRAUS", "3.0"))), None
    if modo == "http":
        return HttpPredictor(url), None
    if modo in ("pose", "auto"):
        try:
            return PosePredictorAdapter(pasta_pose), None
        except Exception as e:  # cai no oraculo, registrando o motivo
            if modo == "pose":
                raise
            return GroundTruthPredictor(), "PosePredictor indisponivel (%s): usando ground truth" % e
    raise ValueError("modo de predictor desconhecido: " + modo)


def chamar(predictor, rgb, camera, meta):
    if getattr(predictor, "usa_meta", False):
        return normalizar_saida(predictor.predict(rgb, camera, meta=meta))
    return normalizar_saida(predictor.predict(rgb, camera))
