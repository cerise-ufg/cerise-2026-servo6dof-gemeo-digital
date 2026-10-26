#!/usr/bin/env bash
# Sessao completa de capturas: predictor oraculo (GT), depois o predictor de
# demonstracao (GT + ruido) para exercitar o painel de erro, e por fim deixa o
# servidor no modo 'auto' (usa o PosePredictor quando a frente de pose publicar).
cd "$(dirname "$0")/../.."
bash gemeo_digital/subir_servidor.sh gt
bash gemeo_digital/capturas/rodar_capturas.sh lado sobreposto diagonal
RUIDO_GRAUS=4 bash gemeo_digital/subir_servidor.sh ruido
bash gemeo_digital/capturas/rodar_capturas.sh ruido ruido_sobreposto
bash gemeo_digital/subir_servidor.sh auto
