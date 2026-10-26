# CERISE 2026 · servo6dof: dataset, modelo digital e gêmeo digital

Repositório da frente **Gêmeo Digital (base)** do Plano de Trabalho CERISE/EMC/UFG 2026, cobrindo:

- **Objetivo 3, Atividade 7**: dataset estruturado e documentado do braço robótico servo6dof (imagens
  sintéticas RGB, profundidade e segmentação, com os ângulos de junta como rótulo), gerado no Gazebo;
- **Objetivo 4, Atividade 11**: modelo digital do braço em ambiente virtual (características físicas e
  cinemáticas, cinemática direta validada, espaço de trabalho, MoveIt 2);
- **Objetivo 4, Atividade 12 (infraestrutura)**: servidor do gêmeo digital (FastAPI + WebSocket +
  three.js) com `Predictor` plugável, à espera do modelo de estimação de pose da frente de visão.

O braço e o pacote ROS 2 original (`servo6dof_*`) são do Prof. Dr. Alisson Assis Cardoso. A execução
roda em ROS 2 Humble + Ignition Gazebo Fortress, em containers no DGX Spark (arm64, GPU GB10).

## Estrutura

```
ros2_ws/src/servo6dof/        pacotes ROS 2 (description, controller, moveit, camera) - cópia de ~/braco
docker/                       Dockerfile.spark (gerador do dataset), Dockerfile.gemeo (ferramentas,
                              MoveIt, FastAPI), Dockerfile.playwright (capturas headless)
dataset_tools/                geração (gerar_plano.py, gerar_hd_spark.sh, finalizar.sh, cams_hd.yaml,
                              plano_poses.json), legado_wsl/ e analise/ (índice, integridade,
                              estatísticas, grades, linha do tempo, reais x comandadas)
modelo_digital/               URDF gerado, cinematica.py (FK numpy + câmera pinhole), tabelas, árvore,
                              validação FK x TF, espaço de trabalho, renders, IoU modelo x imagens,
                              moveit_headless/
gemeo_digital/                servidor/ (FastAPI, predictors.py, static/ three.js + urdf-loader),
                              ros2/ (nó imagem -> /twin/joint_states, launch, RViz), capturas/ (Playwright)
amostra_dataset/              8 poses do split de teste (48 PNGs + JSONs, ~4 MB)
docs/                         README e guia MoveIt originais, slides, DATASET.md (datasheet)
evidencias/                   figuras e prints usados no relatório
resultados/                   métricas medidas (.json/.csv/.log)
scripts/rodar_container.sh    executa um comando no container de ferramentas cerise26_gemeo
```

## Como rodar (no DGX Spark)

```bash
cd ~/cerise2026/gemeo/repo
sudo docker build -f docker/Dockerfile.gemeo -t cerise26_gemeo:latest docker     # 1 vez (~1 min)

# A11 - modelo digital
sudo docker run --rm -v $PWD:/repo cerise26_gemeo:latest bash /repo/modelo_digital/gerar_urdf.sh
bash scripts/rodar_container.sh tab  "python3 modelo_digital/tabela_modelo.py"
bash scripts/rodar_container.sh fk   "python3 modelo_digital/validar_fk_tf.py --n 300"
bash scripts/rodar_container.sh ws   "python3 modelo_digital/espaco_trabalho.py --n 100000"
bash scripts/rodar_container.sh rend "python3 modelo_digital/render_modelo.py --ids 1 2 7"
bash scripts/rodar_container.sh iou  "python3 modelo_digital/validar_projecao.py --n 1000"
bash scripts/rodar_container.sh moveit "bash modelo_digital/moveit_headless/rodar_moveit_headless.sh"

# A7 - análise do dataset (lê ~/braco/dataset somente leitura; escreve em ~/cerise2026/gemeo/dataset_meta)
bash dataset_tools/analise/rodar_analise.sh 0          # 0 = decodifica todas as imagens

# A12 - servidor do gêmeo (só no loopback do Spark, porta 8091)
bash gemeo_digital/subir_servidor.sh auto               # auto | gt | ruido | pose | http
bash gemeo_digital/derrubar_servidor.sh
# do Windows: ssh -N -L 127.0.0.1:18091:localhost:8091 spark-bridge  ->  http://127.0.0.1:18091
bash gemeo_digital/capturas/sessao_capturas.sh          # capturas Playwright + verificação das malhas
```

### Plugar o modelo de pose

O servidor carrega `~/cerise2026/pose/inferencia/predict.py` (classe `PosePredictor`) quando
`~/cerise2026/pose/READY.json` existe (modo `auto` ou `pose`). Contrato:
`PosePredictor(**READY.json["kwargs"]).predict(rgb: np.ndarray HxWx3 uint8 RGB, camera: str)` devolvendo
`{"joint_1": rad, ..., "joint_5": rad[, "joint_6": rad]}` (também aceita lista/array em ordem, ou graus
se `READY.json` tiver `"unidade": "graus"`). Se o modelo precisar de torch/GPU, suba o servidor com a
imagem da frente de pose: `IMAGEM=cerise26_pose:latest GPU=1 bash gemeo_digital/subir_servidor.sh pose`
(o script instala fastapi/uvicorn se faltarem). Alternativa desacoplada: `GEMEO_PREDICTOR_URL=<url>` e
modo `http` (POST JSON `{"camera", "png_b64"}`).

## Resultados principais (medidos em 26/10/2026)

| Item | Resultado |
|---|---|
| Dataset | 5.000 poses, 30.000 imagens 1280×720 (RGB, profundidade, segmentação × 2 câmeras), 2,51 GB; splits 4.000/500/500 |
| Integridade (todas as 30.000 imagens) | 0 problemas, 0 órfãos, 0 faltantes, 0 quadros duplicados; rótulos {0,1,2} em todas as máscaras |
| Cobertura do espaço de juntas | 100 % das células 20×20 em todos os pares; correlação máx. entre juntas 0,024 |
| Juntas reais × comandadas | 34,1 % das poses divergem (> 0,01 rad), 100 % das que atravessariam o chão; usar `juntas_reais` |
| Geração | 3,64 h no DGX Spark, 8 workers Gazebo, 12,8 s/pose por worker (mediana) |
| Modelo × imagens (IoU silhueta, 1.000 poses) | 0,950 (frontal) e 0,938 (diagonal); 2,05 % das imagens abaixo de 0,8 |
| URDF | 13 links, 12 juntas (11 de revolução, 1 fixa), 5 GDL no braço + 1 na garra, 5 juntas mimic |
| FK própria × TF do `robot_state_publisher` | 300 configurações × 11 links: erro máx. 1,9e-15 m e 4,2e-8 rad |
| FK do front-end (three.js/urdf-loader) × FK Python | ≤ 7,6e-7 m (precisão float32) |
| Espaço de trabalho (100 mil configurações) | alcance horizontal máx. 2,05 m; z da ponta da garra em [-0,82; 2,58] m; 20 % das configurações levariam a garra abaixo do chão |
| MoveIt 2 headless (OMPL RRTConnect, hardware falso) | 5/5 objetivos executados; 50/50 planejamentos com sucesso, 12,9 a 17,0 ms em média por objetivo |
| Nó ROS 2 do gêmeo | imagem → `/twin/joint_states` → TF `twin/`: erro 4,6e-16 m com oráculo |
| Front-end | 2 × 12 malhas STL carregadas, sem erros, verificado por Playwright (pixels e estado JS) |

Detalhes do dataset em `docs/DATASET.md` (datasheet) e `resultados/dataset_*.json`; seção de relatório em `RELATORIO_SECAO.md`.

## Segurança

O servidor é publicado só em `127.0.0.1:8091` do Spark. Nada é exposto à internet; o acesso é feito
por encaminhamento SSH local. A eventual exposição pública fica como decisão do Eduardo (ver
`RELATORIO_SECAO.md`).
