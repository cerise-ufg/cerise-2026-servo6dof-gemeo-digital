# Roteiro executado em 26/10/2026 (Spark, ~/cerise2026/gemeo/integracao)

Ordem: `lancar_aval.sh` (avaliacao GPU + SwiftShader; as sessoes com taxa fixa desta rodada foram
descartadas por um erro do driver, `?fps=2.0` nao casava com o seletor) -> `lancar_fps.sh` (refaz as
taxas fixas 2/5/10) -> `alternado.sh` (controle de latencia alternando as cameras) -> `analisar.sh`
(metricas e figuras) -> `capturas.sh` (capturas, varreduras, MP4/GIF via ffmpeg do host) ->
`../../ros2/rodar_rviz_pose.sh` (ROS 2 + RViz headless).
`diag_gpu.py`: teste de WebGL no Chromium headless (ANGLE/EGL na GPU ~16 ms por quadro de animacao,
Vulkan ~160 ms, SwiftShader ~600-690 ms a 1600x1000), que motivou o uso de GL=gpu nas medicoes.
