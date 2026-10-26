# legado/ — pasta original do projeto do braço (ago.–set./2026)

Cópia integral da pasta de trabalho do projeto do braço servo6dof anterior às atividades de 26/10/2026
(originalmente `E:\cerise\braco`, em WSL2/Ubuntu 22.04 com ROS 2 Humble e Ignition Gazebo Fortress),
preservada como estava. Ficaram de fora apenas os artefatos regeneráveis do colcon (`build/`,
`install/`, `log/`) e as pastas dos datasets completos (`dataset/`, `dataset_cinza/`), distribuídas
como Releases (ver `../RELEASES.md`).

| Caminho | Conteúdo |
|---|---|
| `README.md`, `GUIA_MOVEIT.md` | documentação original (também em `../docs/`) |
| `src/servo6dof/` | pacotes ROS 2 (`description`, `controller`, `moveit`, `camera`) no estado final da pasta |
| `ambiente.sh`, `rodar.sh`, `continuar.sh`, `gerar_dataset_paralelo.sh`, `params_*.yaml`, `_*.py` | scripts da geração em WSL2 (também em `../dataset_tools/legado_wsl/`) |
| `gerar_plano.py`, `plano_poses.json`, `status_dataset.py` | plano de 5.000 poses (semente 20260909) e acompanhamento (também em `../dataset_tools/`) |
| `slides/` | apresentação do dataset e scripts de atualização dos números (também em `../docs/slides/`) |
| `fotos/` | 16 fotos das 8 poses nomeadas nas duas câmeras e `poses_registradas.csv` (primeiro teste do estúdio, 28/08/2026) |
| `t0*.txt`, `ts.txt` | carimbos de tempo (época Unix) registrados nos testes de vazão de 31/08/2026 |
| `braco_spark_2026-10-26.tar.gz` | pacote da pasta enviado ao DGX Spark em 26/10/2026 (00:10), antes da troca das câmeras do `estudio_hd.sdf` de 640×480 para 1280×720 |

Diferenças em relação a `../ros2_ws/src/servo6dof/` (versão usada no relatório): o
`servo6dof.urdf.xacro` daqui é a variante com o braço em laranja (`rgba 0.95 0.45 0.05`), usada na
segunda renderização do dataset (ver `../dataset_tools/variante_laranja/`); em `../ros2_ws/` o material
é cinza-alumínio (`rgba 0.78 0.79 0.82`). Os demais arquivos são idênticos. Os arquivos
`*.original_professor` guardam as versões recebidas do Prof. Dr. Alisson Assis Cardoso.
