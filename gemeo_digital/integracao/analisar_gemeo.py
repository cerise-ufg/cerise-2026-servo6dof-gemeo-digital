#!/usr/bin/env python3
"""
Analise das sessoes do gemeo digital integrado ao modelo de pose (Atividade 12).

Entradas: JSONL gravados pelo servidor (GEMEO_LOG_DIR) em <integ>/logs/gpu e <integ>/logs/swiftshader,
os resumos do cliente (cliente_avaliacao_*.json), o index.npz da frente de pose (keypoints 2D verdade
do teste) e o dataset (imagens, segmentacao, profundidade) para diagnosticar os piores quadros.

Saidas (<integ>/resultados e <integ>/evidencias):
  quadros_gemeo_teste.csv         uma linha por (camera, pose) do teste: juntas, erros, tempos por etapa
  metricas_gemeo_integracao.json  erro por junta (media, mediana, p95, max), erro do efetuador, latencias
                                  por etapa, FPS sustentado, comparacao com as metricas da frente de pose
  piores_quadros.json/.csv        piores quadros com diagnostico e explicacao
  escolhas_capturas.json          quadros escolhidos para as capturas (baixo erro / falha)
  a12i_*.png                      graficos (matplotlib, 150 dpi)

Uso (container cerise26_gemeo, com /integ, /repo, /dataset e /pose montados):
  python3 analisar_gemeo.py --integ /integ --dataset /dataset --pose /pose
"""
import argparse
import csv
import glob
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

JUNTAS5 = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
CAMS = ["camera_frontal", "camera_diagonal"]
ROT_CAM = {"camera_frontal": "frontal", "camera_diagonal": "diagonal"}
COR_CAM = {"camera_frontal": "#2a6fdb", "camera_diagonal": "#e07b28"}
ARESTAS = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})


def ler_sessoes(pasta):
    sessoes = []
    for arq in sorted(glob.glob(os.path.join(pasta, "sessao_*.jsonl"))):
        cab, quadros = None, []
        for linha in open(arq):
            d = json.loads(linha)
            if d.get("tipo") == "sessao":
                cab = d
            elif d.get("tipo") == "quadro":
                quadros.append(d)
        quadros.sort(key=lambda q: q["seq"])
        if quadros:
            sessoes.append({"arquivo": os.path.basename(arq), "cab": cab, "quadros": quadros,
                            "fps_alvo": quadros[0].get("fps_alvo"), "camera": quadros[0]["camera"]})
    return sessoes


def est(v):
    v = np.asarray([x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))], float)
    if v.size == 0:
        return None
    return {"n": int(v.size), "media": float(v.mean()), "mediana": float(np.median(v)),
            "p95": float(np.percentile(v, 95)), "max": float(v.max()), "min": float(v.min()),
            "desvio": float(v.std())}


def fps_sessao(qs):
    t = np.array([q["t_cli_render"] for q in qs if q.get("t_cli_render")])
    if t.size < 3:
        return None
    dt = np.diff(t)
    return {"quadros": int(t.size), "duracao_s": float(t[-1] - t[0]), "fps": float((t.size - 1) / (t[-1] - t[0])),
            "intervalo_ms": est(1000 * dt)}


def tempos(q):
    srv = 1000 * (q["t_srv_envio"] - q["t_srv_inicio"]) if q.get("t_srv_envio") else None
    transp = 1000 * (q["t_cli_recebido"] - q["t_srv_envio"]) if q.get("t_cli_recebido") else None
    return {"leitura_ms": q.get("leitura_ms"), "predictor_ms": q.get("latencia_predictor_ms"),
            "predictor_interno_ms": q.get("latencia_predictor_interna_ms"), "pos_ms": q.get("pos_ms"),
            "servidor_ms": srv, "transporte_ms": transp, "render_cliente_ms": q.get("render_cli_ms"),
            "e2e_ms": q.get("e2e_ms"), "rtt_ms": q.get("rtt_ms")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--integ", default="/integ")
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--pose", default="/pose")
    ap.add_argument("--repo", default="/repo")
    ap.add_argument("--recursos", default=None, help="JSON do /api/recursos apos a avaliacao")
    a = ap.parse_args()
    R = os.path.join(a.integ, "resultados")
    E = os.path.join(a.integ, "evidencias")
    os.makedirs(R, exist_ok=True)
    os.makedirs(E, exist_ok=True)
    sys.path.insert(0, os.path.join(a.repo, "modelo_digital"))
    from cinematica import ModeloURDF
    modelo = ModeloURDF(os.path.join(a.repo, "modelo_digital", "urdf", "servo6dof.urdf"))

    ses_gpu = ler_sessoes(os.path.join(a.integ, "logs", "gpu"))
    ses_sw = ler_sessoes(os.path.join(a.integ, "logs", "swiftshader"))
    fechadas = [s for s in ses_gpu if not s["fps_alvo"]]
    fixas = [s for s in ses_gpu if s["fps_alvo"]]

    # ---------------------------------------------------------------- quadros do teste (malha fechada, GPU)
    linhas = {}
    for s in fechadas:
        for q in s["quadros"]:
            chave = (q["camera"], q["id"])
            if chave in linhas or not q.get("pred"):
                continue  # a sessao da a volta na sequencia: fica a primeira passagem
            err = [q["erro_graus"][j] for j in JUNTAS5]
            linhas[chave] = {"camera": q["camera"], "id": q["id"], "idx": q["idx"], "sessao": s["arquivo"],
                             **{"gt_" + j: q["gt"][j] for j in JUNTAS5}, **{"pred_" + j: q["pred"][j] for j in JUNTAS5},
                             **{"err_" + j: e for j, e in zip(JUNTAS5, err)},
                             "mae5_graus": float(np.mean(np.abs(err))), "mae4_graus": float(np.mean(np.abs(err[:4]))),
                             "max_graus": float(np.max(np.abs(err))), "erro_efetuador_mm": 1000 * q["erro_efetuador_m"],
                             "kp2d_pred": q.get("kp2d_pred"), **tempos(q)}
    L = sorted(linhas.values(), key=lambda r: (CAMS.index(r["camera"]), r["idx"]))
    campos = [k for k in L[0] if k != "kp2d_pred"]
    with open(os.path.join(R, "quadros_gemeo_teste.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for r in L:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items() if k in campos})

    def bloco(rs):
        out = {"n_quadros": len(rs)}
        for j in JUNTAS5:
            out["abs_err_" + j] = est([abs(r["err_" + j]) for r in rs])
            out["vies_" + j + "_graus"] = float(np.mean([r["err_" + j] for r in rs]))
        out["mae5_graus"] = est([r["mae5_graus"] for r in rs])
        out["mae4_graus"] = est([r["mae4_graus"] for r in rs])
        out["max_por_quadro_graus"] = est([r["max_graus"] for r in rs])
        ee = [r["erro_efetuador_mm"] for r in rs]
        out["erro_efetuador_mm"] = est(ee)
        out["frac_efetuador_abaixo"] = {"20mm": float(np.mean(np.array(ee) < 20)), "50mm": float(np.mean(np.array(ee) < 50)),
                                        "100mm": float(np.mean(np.array(ee) < 100))}
        for k in ("leitura_ms", "predictor_ms", "predictor_interno_ms", "pos_ms", "servidor_ms", "transporte_ms",
                  "render_cliente_ms", "e2e_ms", "rtt_ms"):
            out[k] = est([r[k] for r in rs])
        return out

    met = {"descricao": "Gemeo digital (servidor FastAPI/WebSocket + front-end three.js) com o PosePredictor da frente "
                        "de pose: o braco 'gemeo' segue as juntas previstas SO a partir da imagem; a referencia segue a "
                        "verdade-base (juntas_reais do Gazebo). Conjunto de TESTE da frente de pose (500 poses x 2 cameras), "
                        "malha fechada (proximo quadro so apos o front-end confirmar o desenho), Chromium headless com "
                        "WebGL na GPU (ANGLE/EGL), no mesmo host do servidor.",
           "sessoes_malha_fechada": [s["arquivo"] for s in fechadas], "por_camera": {}, "geral": bloco(L)}
    for c in CAMS:
        met["por_camera"][ROT_CAM[c]] = bloco([r for r in L if r["camera"] == c])

    # consistencia com a avaliacao offline da frente de pose (mesmas 1000 imagens)
    try:
        ready = json.load(open(os.path.join(a.pose, "READY.json")))
        mt = ready["metricas_teste"]
        met["comparacao_frente_pose"] = {
            "frente_pose_MAE_medio_graus": mt["MAE_medio_graus"], "gemeo_MAE_medio_graus": met["geral"]["mae5_graus"]["media"],
            "frente_pose_MAE_por_junta": mt["MAE_por_junta_graus"],
            "gemeo_MAE_por_junta": [met["geral"]["abs_err_" + j]["media"] for j in JUNTAS5],
            "obs": "a frente de pose avaliou com recortes e profundidade DA-V2 pre-computados (memmap); o gemeo le o PNG "
                   "1280x720 e roda recorte + DA-V2 + HPE a cada quadro. Diferencas pequenas vem da ordem de "
                   "arredondamento/redimensionamento."}
    except Exception as e:  # pragma: no cover
        met["comparacao_frente_pose"] = {"erro": str(e)}

    # ---------------------------------------------------------------- FPS / sessoes
    met["fps"] = {}
    for s in ses_gpu:
        chave = "%s_%s" % (ROT_CAM[s["camera"]], "malha_fechada" if not s["fps_alvo"] else "alvo_%gfps" % s["fps_alvo"])
        f = fps_sessao(s["quadros"])
        if f:
            f["fps_alvo"] = s["fps_alvo"] or None
            f["e2e_ms"] = est([q.get("e2e_ms") for q in s["quadros"]])
            met["fps"][chave] = f
    met["swiftshader"] = {}
    for s in ses_sw:
        f = fps_sessao(s["quadros"]) or {}
        f.update({k: est([tempos(q)[k] for q in s["quadros"]]) for k in ("render_cliente_ms", "e2e_ms", "servidor_ms")})
        met["swiftshader"]["%s_%s" % (ROT_CAM[s["camera"]], "malha_fechada" if not s["fps_alvo"] else "alvo_%gfps" % s["fps_alvo"])] = f
    for nome in ("cliente_avaliacao_gpu.json", "cliente_avaliacao_swiftshader.json"):
        p = os.path.join(R, nome)
        if os.path.exists(p):
            met["cliente_" + nome.split("_")[-1].replace(".json", "")] = [
                {k: v for k, v in s.items() if k not in ("console",)} for s in json.load(open(p))["sessoes"]]
    if a.recursos and os.path.exists(a.recursos):
        met["recursos_servidor"] = json.load(open(a.recursos))
    p = os.path.join(R, "controle_latencia_cameras_alternadas.json")
    if os.path.exists(p):  # a diferenca de latencia entre as sessoes frontal/diagonal e da camera ou da carga da GPU?
        met["controle_latencia_cameras_alternadas"] = json.load(open(p))

    # ---------------------------------------------------------------- diagnostico dos piores quadros
    idx_npz = np.load(os.path.join(a.pose, "dados", "final", "index.npz"))
    crop = json.load(open(os.path.join(a.pose, "dados", "final", "crop.json")))
    kp_gt = {}
    for i, c, k in zip(idx_npz["teste_ids"], idx_npz["teste_cam"], idx_npz["teste_kp2d"]):
        kp_gt[("camera_" + ["frontal", "diagonal"][int(c)], int(i))] = k

    metas_ds = {}

    def diagnostico(r):
        c, i = r["camera"], r["id"]
        seg = np.asarray(Image.open(os.path.join(a.dataset, "%06d_%s_segmentation_labels_map.png" % (i, c))))
        if seg.ndim == 3:
            seg = seg[..., 0]
        dep = np.asarray(Image.open(os.path.join(a.dataset, "%06d_%s_depth.png" % (i, c))))
        braco = (seg == 0) & (dep > 0)
        x0, y0, S = crop[ROT_CAM[c]]
        ys, xs = np.nonzero(braco)
        dentro = ((xs >= x0) & (xs < x0 + S) & (ys >= y0) & (ys < y0 + S)).mean() if xs.size else 0.0
        gt = {j: r["gt_" + j] for j in JUNTAS5}
        gt["joint_6"] = 0.0
        T = modelo.fk(gt)
        # altura dos elos distais (cotovelo em diante): o base_link e o 1o elo ficam sempre no piso
        z_min = min(float(T[l][2, 3]) for l in ("terceiro_elo", "quarto_elo", "base_garra", "garra_elo3a", "garra_elo3b")
                    if l in T)
        meta = metas_ds.get(i)
        if meta is None:
            meta = metas_ds[i] = json.load(open(os.path.join(a.dataset, "%06d.json" % i)))
        div = max(abs(meta["juntas_reais"][j] - meta["juntas_comandadas"][j]) for j in JUNTAS5)
        prof_min = float(dep[braco].min()) / 1000.0 if xs.size else None
        kg = kp_gt.get((c, i))
        kp = np.array(r["kp2d_pred"]) if r.get("kp2d_pred") else None
        err_kp = np.linalg.norm(kp - kg, axis=1).tolist() if (kp is not None and kg is not None) else None
        borda = bool(kg is not None and ((kg[:, 0] < 15).any() or (kg[:, 0] > 1265).any() or (kg[:, 1] < 15).any()
                                         or (kg[:, 1] > 705).any()))
        outra = linhas.get((CAMS[1 - CAMS.index(c)], i))
        errs = {j: abs(r["err_" + j]) for j in JUNTAS5}
        dom = max(JUNTAS5[:4], key=errs.get)   # a joint_5 nao move a origem da base_garra
        motivos = []
        if r["err_joint_2"] * r["err_joint_3"] < 0 and errs["joint_2"] > 30 and errs["joint_3"] > 30:
            motivos.append("ambiguidade de configuracao: erros grandes e de sinais opostos em j2 (%+.0f) e j3 (%+.0f) -> "
                           "'cotovelo invertido' com silhueta 2D parecida" % (r["err_joint_2"], r["err_joint_3"]))
        elif errs[dom] > 15:
            motivos.append("erro concentrado na %s (%+.0f graus)" % (dom, r["err_" + dom]))
        if xs.size and dentro < 0.97:
            motivos.append("%.0f%% dos pixels do braco ficam FORA do recorte fixo da camera" % (100 * (1 - dentro)))
        if borda:
            motivos.append("keypoints verdade na borda/fora da imagem (braco cortado pelo enquadramento)")
        if xs.size < 6000:
            motivos.append("braco pequeno/pouco visivel na imagem (%d px)" % xs.size)
        if prof_min is not None and prof_min < 1.2:
            motivos.append("braco muito perto da camera (%.2f m): escala/perspectiva fora do usual" % prof_min)
        if div > math.radians(1):
            motivos.append("pose em contato com o piso no Gazebo (juntas reais diferem das comandadas em ate %.0f graus)"
                           % math.degrees(div))
        if z_min < 0.15:
            motivos.append("garra/punho rente ao chao (z %.2f m): oclusao com o piso e sombra" % z_min)
        if err_kp is not None and max(err_kp) > 40:
            k_pior = int(np.argmax(err_kp))
            motivos.append("keypoint 2D mais errado: %s (%.0f px)" % (["base", "junta_1", "junta_2", "junta_3", "junta_4",
                                                                     "junta_5", "ponta_garra"][k_pior], err_kp[k_pior]))
        if outra is not None:
            motivos.append("mesma pose na outra camera: erro do efetuador %.0f mm, MAE %.1f graus"
                           % (outra["erro_efetuador_mm"], outra["mae5_graus"]))
        return {"camera": c, "id": i, "idx": r["idx"], "mae5_graus": r["mae5_graus"], "mae4_graus": r["mae4_graus"],
                "erro_efetuador_mm": r["erro_efetuador_mm"], "erros_graus": {j: round(r["err_" + j], 2) for j in JUNTAS5},
                "junta_dominante": dom, "pixels_braco": int(xs.size), "frac_braco_no_recorte": float(dentro),
                "z_min_distal_m": z_min, "divergencia_real_comandada_graus": math.degrees(div),
                "profundidade_min_braco_m": prof_min, "keypoints_na_borda": borda,
                "erro_kp2d_px": [round(v, 1) for v in err_kp] if err_kp else None,
                "gt_graus": {j: round(math.degrees(r["gt_" + j]), 1) for j in JUNTAS5},
                "pred_graus": {j: round(math.degrees(r["pred_" + j]), 1) for j in JUNTAS5},
                "explicacao": "; ".join(motivos) if motivos else "sem causa evidente pelos indicadores automaticos"}

    por_ee = sorted(L, key=lambda r: -r["erro_efetuador_mm"])[:10]
    por_mae4 = sorted(L, key=lambda r: -r["mae4_graus"])[:10]
    por_mae5 = sorted(L, key=lambda r: -r["mae5_graus"])[:5]
    piores = {"por_erro_efetuador": [diagnostico(r) for r in por_ee],
              "por_mae_juntas_1a4": [diagnostico(r) for r in por_mae4],
              "por_mae_5_juntas": [diagnostico(r) for r in por_mae5]}
    # indicadores agregados: erro do efetuador x visibilidade / recorte (todos os quadros, amostra)
    amostra = L[::5]
    diag_am = [diagnostico(r) for r in amostra]
    piores["correlacoes_amostra"] = {
        "n": len(diag_am),
        "corr_spearman_ee_vs_pixels_braco": None, "corr_spearman_ee_vs_frac_recorte": None}
    try:
        def rank(v):
            return np.argsort(np.argsort(v))
        ee = np.array([d["erro_efetuador_mm"] for d in diag_am])
        px = np.array([d["pixels_braco"] for d in diag_am])
        fr = np.array([d["frac_braco_no_recorte"] for d in diag_am])
        piores["correlacoes_amostra"]["corr_spearman_ee_vs_pixels_braco"] = float(np.corrcoef(rank(ee), rank(px))[0, 1])
        piores["correlacoes_amostra"]["corr_spearman_ee_vs_frac_recorte"] = float(np.corrcoef(rank(ee), rank(fr))[0, 1])
        piores["correlacoes_amostra"]["frac_quadros_braco_fora_recorte_3pct"] = float(np.mean(fr < 0.97))
        piores["correlacoes_amostra"]["ee_mediano_mm_braco_fora_recorte"] = float(np.median(ee[fr < 0.97])) if (fr < 0.97).any() else None
        piores["correlacoes_amostra"]["ee_mediano_mm_braco_dentro_recorte"] = float(np.median(ee[fr >= 0.97]))
        for j in JUNTAS5:
            g = np.array([r["gt_" + j] for r in amostra])
            piores["correlacoes_amostra"]["corr_spearman_ee_vs_|gt_%s|" % j] = float(np.corrcoef(rank(ee), rank(np.abs(g)))[0, 1])
        ct = np.array([d["divergencia_real_comandada_graus"] > 1 for d in diag_am])
        bd = np.array([d["keypoints_na_borda"] for d in diag_am])
        zb = np.array([d["z_min_distal_m"] < 0.15 for d in diag_am])
        cA = piores["correlacoes_amostra"]
        cA["frac_contato_piso"] = float(ct.mean())
        cA["ee_mediano_mm_contato"] = float(np.median(ee[ct])) if ct.any() else None
        cA["ee_mediano_mm_sem_contato"] = float(np.median(ee[~ct])) if (~ct).any() else None
        cA["frac_keypoints_na_borda"] = float(bd.mean())
        cA["ee_mediano_mm_keypoints_na_borda"] = float(np.median(ee[bd])) if bd.any() else None
        cA["ee_mediano_mm_keypoints_dentro"] = float(np.median(ee[~bd])) if (~bd).any() else None
        cA["frac_garra_rente_chao"] = float(zb.mean())
        cA["ee_mediano_mm_garra_rente_chao"] = float(np.median(ee[zb])) if zb.any() else None
        cA["ee_mediano_mm_garra_alta"] = float(np.median(ee[~zb])) if (~zb).any() else None
        # nos 20 piores quadros (efetuador) de todo o teste
        top = [diagnostico(r) for r in sorted(L, key=lambda r: -r["erro_efetuador_mm"])[:20]]
        cA["top20_frac_contato_piso"] = float(np.mean([d["divergencia_real_comandada_graus"] > 1 for d in top]))
        cA["top20_frac_keypoints_na_borda"] = float(np.mean([d["keypoints_na_borda"] for d in top]))
        cA["top20_frac_garra_rente_chao"] = float(np.mean([d["z_min_distal_m"] < 0.15 for d in top]))
        cA["top20_frac_ambiguidade_cotovelo"] = float(np.mean(["ambiguidade" in d["explicacao"] for d in top]))
    except Exception as e:  # pragma: no cover
        piores["correlacoes_amostra"]["erro"] = str(e)
    json.dump(piores, open(os.path.join(R, "piores_quadros.json"), "w"), indent=2, ensure_ascii=False)
    with open(os.path.join(R, "piores_quadros.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["criterio", "camera", "id", "idx", "erro_efetuador_mm", "mae5_graus", "mae4_graus", "junta_dominante",
                    "pixels_braco", "frac_braco_no_recorte", "explicacao"])
        for crit in ("por_erro_efetuador", "por_mae_juntas_1a4", "por_mae_5_juntas"):
            for d in piores[crit]:
                w.writerow([crit, d["camera"], d["id"], d["idx"], round(d["erro_efetuador_mm"], 1), round(d["mae5_graus"], 2),
                            round(d["mae4_graus"], 2), d["junta_dominante"], d["pixels_braco"],
                            round(d["frac_braco_no_recorte"], 3), d["explicacao"]])
    met["piores_resumo"] = {"pior_efetuador": piores["por_erro_efetuador"][0], "correlacoes": piores["correlacoes_amostra"]}
    json.dump(met, open(os.path.join(R, "metricas_gemeo_integracao.json"), "w"), indent=2, ensure_ascii=False)

    # ---------------------------------------------------------------- escolhas para as capturas
    n_seq = 500
    fr = [r for r in L if r["camera"] == "camera_frontal"]
    p10 = np.percentile([r["erro_efetuador_mm"] for r in fr], 10)
    bons = [r for r in fr if r["erro_efetuador_mm"] <= p10]
    bom = min(bons, key=lambda r: r["mae4_graus"] + 0.2 * r["mae5_graus"])
    ruim = por_ee[0]
    esc = {"baixo_erro": {k: bom[k] for k in ("camera", "id", "idx", "mae5_graus", "mae4_graus", "erro_efetuador_mm")},
           "falha": {k: ruim[k] for k in ("camera", "id", "idx", "mae5_graus", "mae4_graus", "erro_efetuador_mm")},
           "capturas": [
               {"arquivo": "a12i_gemeo_baixo_erro_lado.png", "idx": bom["idx"], "camera": bom["camera"], "modo": "lado",
                "vista": "livre", "n_quadros": n_seq},
               {"arquivo": "a12i_gemeo_baixo_erro_sobreposto.png", "idx": bom["idx"], "camera": bom["camera"],
                "modo": "sobreposto", "vista": "camera", "n_quadros": n_seq},
               {"arquivo": "a12i_gemeo_falha_lado.png", "idx": ruim["idx"], "camera": ruim["camera"], "modo": "lado",
                "vista": "livre", "n_quadros": n_seq},
               {"arquivo": "a12i_gemeo_falha_sobreposto.png", "idx": ruim["idx"], "camera": ruim["camera"],
                "modo": "sobreposto", "vista": "camera", "n_quadros": n_seq}]}
    json.dump(esc, open(os.path.join(R, "escolhas_capturas.json"), "w"), indent=2, ensure_ascii=False)

    # ================================================================= figuras
    # 1) erro ao longo da sequencia
    fig, axs = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True)
    for c in CAMS:
        rs = [r for r in L if r["camera"] == c]
        x = [r["idx"] for r in rs]
        axs[0].plot(x, [r["mae4_graus"] for r in rs], lw=0.9, color=COR_CAM[c], label="câmera " + ROT_CAM[c])
        axs[1].plot(x, [abs(r["err_joint_5"]) for r in rs], lw=0.8, color=COR_CAM[c], alpha=0.85)
        axs[2].plot(x, [r["erro_efetuador_mm"] for r in rs], lw=0.9, color=COR_CAM[c])
    axs[0].set_ylabel("erro médio juntas 1–4 (°)")
    axs[1].set_ylabel("|erro| junta 5 (°)\n(rotação da garra)")
    axs[2].set_ylabel("erro do efetuador (mm)")
    axs[2].set_xlabel("quadro da sequência de teste (ordem por vizinho mais próximo no espaço de juntas)")
    for d in piores["por_erro_efetuador"][:3]:
        axs[2].annotate("id %d" % d["id"], (d["idx"], d["erro_efetuador_mm"]), fontsize=7, xytext=(4, 2),
                        textcoords="offset points")
    axs[0].legend(loc="upper right", ncol=2)
    fig.suptitle("Gêmeo digital com o modelo de pose: erro quadro a quadro no conjunto de teste (500 poses × 2 câmeras)")
    fig.tight_layout()
    fig.savefig(os.path.join(E, "a12i_erro_sequencia.png"))
    plt.close(fig)

    # 2) erro por junta (boxplot) + comparacao com a frente de pose
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.6, 1]})
    pos = np.arange(len(JUNTAS5))
    for k, c in enumerate(CAMS):
        dados = [[abs(r["err_" + j]) for r in L if r["camera"] == c] for j in JUNTAS5]
        bp = axs[0].boxplot(dados, positions=pos + (k - 0.5) * 0.36, widths=0.32, patch_artist=True, showfliers=True,
                            flierprops={"markersize": 2, "alpha": 0.4}, medianprops={"color": "k"})
        for b in bp["boxes"]:
            b.set_facecolor(COR_CAM[c])
            b.set_alpha(0.55)
        axs[0].plot([], [], "s", color=COR_CAM[c], alpha=0.6, label="câmera " + ROT_CAM[c])
    axs[0].set_xticks(pos, ["junta %d" % (i + 1) for i in range(5)])
    axs[0].set_yscale("symlog", linthresh=10)
    axs[0].set_ylabel("|erro| por quadro (°, escala symlog)")
    axs[0].set_title("Distribuição do erro por junta no gêmeo")
    axs[0].legend()
    g = met["geral"]
    medias = [g["abs_err_" + j]["media"] for j in JUNTAS5]
    p95 = [g["abs_err_" + j]["p95"] for j in JUNTAS5]
    ref = met.get("comparacao_frente_pose", {}).get("frente_pose_MAE_por_junta")
    w = 0.27
    axs[1].bar(pos - w, medias, w, label="gêmeo: média", color="#3b8f6b")
    axs[1].bar(pos, p95, w, label="gêmeo: p95", color="#9fd3b9")
    if ref:
        axs[1].bar(pos + w, ref, w, label="frente de pose (offline): média", color="#888")
    for x, v in zip(pos - w, medias):
        axs[1].text(x, v + 1, "%.1f" % v, ha="center", fontsize=7)
    axs[1].set_xticks(pos, ["j%d" % (i + 1) for i in range(5)])
    axs[1].set_ylabel("graus")
    axs[1].set_title("Média e p95 (2 câmeras) × avaliação offline")
    axs[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(E, "a12i_erro_por_junta_gemeo.png"))
    plt.close(fig)

    # 3) latencia por etapa + distribuicao ponta a ponta + FPS
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.0), gridspec_kw={"width_ratios": [1.5, 1.2, 1]})
    etapas = [("leitura_ms", "leitura PNG"), ("predictor_ms", "modelo de pose\n(recorte+DA-V2+HPE)"),
              ("pos_ms", "FK + JPEG"), ("transporte_ms", "serialização +\nWebSocket"), ("render_cliente_ms", "atualização\nno three.js")]
    srv_rest = []
    for r in L:
        if r["servidor_ms"] is not None:
            srv_rest.append(r["servidor_ms"] - (r["leitura_ms"] + r["predictor_ms"] + r["pos_ms"]))
    meds = [g[k]["mediana"] for k, _ in etapas]
    cores = ["#6c8ebf", "#d6604d", "#b8b8b8", "#f4a582", "#4daf4a"]
    esq = 0
    for (k, rot), v, cor in zip(etapas, meds, cores):
        axs[0].barh([0], [v], left=esq, color=cor, edgecolor="white", label="%s: %.1f ms" % (rot.replace("\n", " "), v))
        esq += v
    axs[0].barh([1], [g["e2e_ms"]["mediana"]], color="#555", label="ponta a ponta medido: %.1f ms" % g["e2e_ms"]["mediana"])
    axs[0].set_yticks([0, 1], ["soma das\netapas", "ponta a\nponta"])
    axs[0].set_xlabel("mediana (ms)")
    axs[0].legend(fontsize=7, loc="lower right")
    axs[0].set_title("Imagem → predição → gêmeo desenhado")
    e2e = [r["e2e_ms"] for r in L if r["e2e_ms"]]
    axs[1].hist(e2e, bins=60, color="#555", alpha=0.85)
    for q, ls in ((50, "-"), (95, "--")):
        v = np.percentile(e2e, q)
        axs[1].axvline(v, color="r", ls=ls, lw=1)
        axs[1].text(v, axs[1].get_ylim()[1] * 0.9, " p%d %.0f ms" % (q, v), color="r", fontsize=7)
    axs[1].set_xlabel("latência ponta a ponta (ms)")
    axs[1].set_ylabel("quadros")
    axs[1].set_title("Distribuição (1000 quadros, WebGL na GPU)")
    nomes, vals, alvos = [], [], []
    for k, f in met["fps"].items():
        nomes.append(k.replace("_malha_fechada", "\nmáx.").replace("frontal_alvo_", "alvo\n").replace("fps", ""))
        vals.append(f["fps"])
        alvos.append(f["fps_alvo"])
    for k, f in met["swiftshader"].items():
        if f.get("fps"):
            nomes.append("Swift-\nShader")
            vals.append(f["fps"])
            alvos.append(None)
    xb = np.arange(len(nomes))
    axs[2].bar(xb, vals, color=["#3b8f6b" if "Swift" not in n else "#bbb" for n in nomes])
    for x, v, al in zip(xb, vals, alvos):
        axs[2].text(x, v + 0.1, "%.2f" % v, ha="center", fontsize=7)
        if al:
            axs[2].plot([x - 0.4, x + 0.4], [al, al], "k--", lw=1)
    axs[2].set_xticks(xb, nomes, fontsize=6.5)
    axs[2].set_ylabel("quadros/s sustentados")
    axs[2].set_title("FPS medido (tracejado = alvo)")
    fig.tight_layout()
    fig.savefig(os.path.join(E, "a12i_latencia_fps.png"))
    plt.close(fig)

    # 4) mosaico dos piores quadros (+ 1 bom para referencia)
    casos = piores["por_erro_efetuador"][:4] + [diagnostico(bom)]
    fig, axs = plt.subplots(1, len(casos), figsize=(3.3 * len(casos), 4.4))
    for ax, d in zip(axs, casos):
        c, i = d["camera"], d["id"]
        img = np.asarray(Image.open(os.path.join(a.dataset, "%06d_%s_image.png" % (i, c))).convert("RGB"))
        x0, y0, S = crop[ROT_CAM[c]]
        ax.imshow(img)
        kg = kp_gt.get((c, i))
        kp = np.array(linhas[(c, i)]["kp2d_pred"])
        if kg is not None:
            ax.plot(kg[:, 0], kg[:, 1], "-o", color="white", lw=2.2, ms=3, label="verdade")
        ax.plot(kp[:, 0], kp[:, 1], "-o", color="#1baf7a", lw=2, ms=3, label="previsto")
        ax.add_patch(plt.Rectangle((x0, y0), S, S, fill=False, ec="yellow", ls="--", lw=1))
        pts = np.vstack([kp, kg]) if kg is not None else kp
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        half = max(200, 0.6 * max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
        ax.set_xlim(max(0, cx - half), min(1280, cx + half))
        ax.set_ylim(min(720, cy + half), max(0, cy - half))
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        tit = ("BOM — " if d is casos[-1] else "falha — ") + "id %d (%s)" % (i, ROT_CAM[c])
        ax.set_title(tit, fontsize=8.5)
        txt = "efetuador %.0f mm · juntas 1–4 %.1f°\n" % (d["erro_efetuador_mm"], d["mae4_graus"])
        txt += " ".join("j%d %+.0f" % (k + 1, d["erros_graus"][j]) for k, j in enumerate(JUNTAS5))
        ax.set_xlabel(txt, fontsize=7)
    axs[0].legend(fontsize=7, loc="lower left")
    fig.suptitle("Piores quadros do gêmeo (erro do efetuador) e um quadro bom — esqueleto verdade (branco) × previsto "
                 "(verde); tracejado amarelo = recorte fixo da câmera", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(E, "a12i_piores_quadros.png"))
    plt.close(fig)

    # 5) diagnostico: erro do efetuador por fator (amostra 1/5 do teste) e x |joint_1| verdade
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.0), gridspec_kw={"width_ratios": [1.5, 1]})
    fatores = [("contato com o piso\n(reais ≠ comandadas)", lambda d: d["divergencia_real_comandada_graus"] > 1),
               ("keypoints na borda\nda imagem", lambda d: d["keypoints_na_borda"]),
               ("garra/punho a\n< 15 cm do chão", lambda d: d["z_min_distal_m"] < 0.15),
               ("braço > 3% fora\ndo recorte", lambda d: d["frac_braco_no_recorte"] < 0.97)]
    dados, rot, pos_b = [], [], []
    for k, (nome, f) in enumerate(fatores):
        sim = [d["erro_efetuador_mm"] for d in diag_am if f(d)]
        nao = [d["erro_efetuador_mm"] for d in diag_am if not f(d)]
        dados += [nao, sim]
        pos_b += [3 * k, 3 * k + 1]
        rot += ["não\n(n=%d)" % len(nao), "sim\n(n=%d)" % len(sim)]
        axs[0].text(3 * k + 0.5, 1.02, nome, transform=axs[0].get_xaxis_transform(), ha="center", va="bottom", fontsize=7.5)
    bp = axs[0].boxplot([d if d else [np.nan] for d in dados], positions=pos_b, widths=0.7, patch_artist=True,
                        flierprops={"markersize": 2, "alpha": 0.5}, medianprops={"color": "k"})
    for k, b in enumerate(bp["boxes"]):
        b.set_facecolor("#9fd3b9" if k % 2 == 0 else "#d6604d")
        b.set_alpha(0.7)
    axs[0].set_xticks(pos_b, rot, fontsize=7)
    axs[0].set_yscale("log")
    axs[0].set_ylabel("erro do efetuador (mm, log)")
    for c in CAMS:
        ds = [d for d, r in zip(diag_am, amostra) if d["camera"] == c]
        axs[1].scatter([abs(d["gt_graus"]["joint_1"]) for d in ds], [d["erro_efetuador_mm"] for d in ds], s=9,
                       color=COR_CAM[c], alpha=0.7, label="câmera " + ROT_CAM[c])
    axs[1].set_yscale("log")
    axs[1].set_xlabel("|joint_1| verdade (°) — giro da base")
    axs[1].set_ylabel("erro do efetuador (mm, log)")
    axs[1].set_title("Erro × giro da base (Spearman %.2f)" % piores["correlacoes_amostra"].get("corr_spearman_ee_vs_|gt_joint_1|", float("nan")),
                     fontsize=9)
    axs[1].legend(fontsize=7)
    fig.suptitle("Diagnóstico das falhas do gêmeo (amostra de 200 quadros do teste)", fontsize=9.5, y=1.0)
    fig.tight_layout()
    fig.savefig(os.path.join(E, "a12i_diagnostico_falhas.png"))
    plt.close(fig)

    g = met["geral"]
    print("quadros: %d | MAE5 %.2f° | MAE j1-4 %.2f° | efetuador media %.1f mm mediana %.1f p95 %.1f max %.1f"
          % (g["n_quadros"], g["mae5_graus"]["media"], g["mae4_graus"]["media"], g["erro_efetuador_mm"]["media"],
             g["erro_efetuador_mm"]["mediana"], g["erro_efetuador_mm"]["p95"], g["erro_efetuador_mm"]["max"]))
    for j in JUNTAS5:
        s = g["abs_err_" + j]
        print("  %s |err| media %6.2f  p95 %6.2f  max %6.2f" % (j, s["media"], s["p95"], s["max"]))
    print("latencia mediana: leitura %.1f | predictor %.1f | pos %.1f | transporte %.1f | render %.1f | e2e %.1f (p95 %.1f) ms"
          % (g["leitura_ms"]["mediana"], g["predictor_ms"]["mediana"], g["pos_ms"]["mediana"], g["transporte_ms"]["mediana"],
             g["render_cliente_ms"]["mediana"], g["e2e_ms"]["mediana"], g["e2e_ms"]["p95"]))
    for k, f in met["fps"].items():
        print("  FPS %-28s %.2f (alvo %s, %d quadros)" % (k, f["fps"], f["fps_alvo"], f["quadros"]))
    for k, f in met["swiftshader"].items():
        print("  SwiftShader %-20s FPS %s | render mediana %s ms" % (k, round(f.get("fps") or 0, 2),
                                                                    round((f.get("render_cliente_ms") or {}).get("mediana", 0), 1)))
    print("pior quadro (efetuador):", json.dumps(piores["por_erro_efetuador"][0]["explicacao"], ensure_ascii=False))
    cA = piores["correlacoes_amostra"]
    print("fatores (amostra %d): contato %.0f%% (ee med %.0f vs %.0f mm) | kp na borda %.0f%% (%.0f vs %.0f) | garra rente %.0f%% "
          "(%.0f vs %.0f) | top20: contato %.0f%% borda %.0f%% rente %.0f%% cotovelo %.0f%%"
          % (cA["n"], 100 * cA["frac_contato_piso"], cA["ee_mediano_mm_contato"] or 0, cA["ee_mediano_mm_sem_contato"] or 0,
             100 * cA["frac_keypoints_na_borda"], cA["ee_mediano_mm_keypoints_na_borda"] or 0, cA["ee_mediano_mm_keypoints_dentro"] or 0,
             100 * cA["frac_garra_rente_chao"], cA["ee_mediano_mm_garra_rente_chao"] or 0, cA["ee_mediano_mm_garra_alta"] or 0,
             100 * cA["top20_frac_contato_piso"], 100 * cA["top20_frac_keypoints_na_borda"],
             100 * cA["top20_frac_garra_rente_chao"], 100 * cA["top20_frac_ambiguidade_cotovelo"]))
    print("escolhas:", json.dumps({k: esc[k] for k in ("baixo_erro", "falha")}))


if __name__ == "__main__":
    main()
