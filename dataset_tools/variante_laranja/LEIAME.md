# Variante "laranja" do dataset (mesmas 5.000 poses)

Depois da geração usada no relatório (braço em cinza-alumínio, `rgba 0.78 0.79 0.82`), o dataset foi
renderizado uma segunda vez com o braço em laranja (`rgba 0.95 0.45 0.05`), mantendo todo o resto:

- mesmo plano de poses (`dataset_tools/plano_poses.json`, semente 20260909, ids 000001–005000);
- mesmo mundo e mesmas câmeras (`estudio_hd.sdf`, `dataset_tools/cams_hd.yaml`), 1280×720;
- mesmo script de geração (`dataset_tools/gerar_hd_spark.sh`, 8 workers Gazebo isolados);
- única diferença no pacote ROS 2: a cor do material dos elos no xacro
  (`servo6dof.urdf.xacro` desta pasta, que substitui
  `ros2_ws/src/servo6dof/servo6dof_description/urdf/servo6dof.urdf.xacro` na geração).

Execução no DGX Spark em 26/10/2026 (registros em `resultados/geracao_laranja/`):

| Item | Valor (dos logs) |
|---|---|
| início da geração (`gen_main.log`) | 13:47:04 UTC (10:47 de Brasília), 8 workers, meta de 5.000 poses |
| término | 15:38:46 UTC (12:38 de Brasília): `COMPLETO`, 0 poses faltando |
| finalização (`finalize.log`) | 5.000 poses no disco às 12:38:47 (horário de Brasília) |
| arquivos na pasta | 35.009 (5.000 JSON + 30.000 PNG + `index.csv` + 8 `poses_registradas_w*.csv`) |

`finalizar_laranja.sh` aguarda o término do contêiner de geração e corrige o dono dos arquivos; ao
contrário de `dataset_tools/finalizar.sh`, não religa serviços. `dataset_tools/build_index.py`
reconstrói o `index.csv` da pasta (id, juntas comandadas, garra e lista de imagens).

As duas versões completas (cinza e laranja) são distribuídas como Releases; ver `RELEASES.md` na raiz.
