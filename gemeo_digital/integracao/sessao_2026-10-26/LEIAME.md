# Roteiro executado em 26/10/2026 (Spark, ~/cerise2026/gemeo/integracao)

Ordem: `lancar_aval.sh` (avaliacao GPU + SwiftShader; as sessoes com taxa fixa desta rodada foram
descartadas por um erro do driver, `?fps=2.0` nao casava com o seletor) -> `lancar_fps.sh` (refaz as
taxas fixas 2/5/10) -> `alternado.sh` (controle de latencia alternando as cameras) -> `analisar.sh`
(metricas e figuras) -> `capturas.sh` (capturas, varreduras, MP4/GIF via ffmpeg do host) ->
`../../ros2/rodar_rviz_pose.sh` (ROS 2 + RViz headless).
`diag_gpu.py`: teste de WebGL no Chromium headless (ANGLE/EGL na GPU ~16 ms por quadro de animacao,
Vulkan ~160 ms, SwiftShader ~600-690 ms a 1600x1000), que motivou o uso de GL=gpu nas medicoes.

Scripts auxiliares da mesma sessao: `chk.sh` e `chk2.sh` (conferencia do ambiente, das imagens Docker e
do split de teste no `index.npz` do modelo de pose), `teste1.sh` (primeiros quadros do servidor em modo
pose, por camera), `diag_gpu.sh` + `diag_render.py` (diagnostico de WebGL/EGL no contêiner Playwright) e
`prints.sh` (saidas de terminal em `resultados/a12_integracao/terminal/`). Os JSONL das sessoes estao em
`resultados/a12_integracao/` (`logs_sessoes_websocket.tar.gz` com as sessoes medidas e
`logs_jsonl_complementares/` com o teste inicial, as capturas e as duas sessoes descartadas); os quadros
PNG das varreduras estao no Release `gemeo_integracao_quadros_brutos.tar` (ver `RELEASES.md`).
