#!/usr/bin/env bash
cd ~/cerise2026/gemeo/repo
I=$HOME/cerise2026/gemeo/integracao
mkdir -p $I/logs_capturas
GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh capturas --escolhas /integ/resultados/escolhas_capturas.json --pasta /integ/evidencias 2>&1 | grep -v "^$"
rm -rf $I/varredura && GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh varredura --inicio 0 --n 72 --modo lado --vista livre --pasta /integ/varredura 2>&1 | tail -2
rm -rf $I/varredura_cam && GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh varredura --inicio 0 --n 72 --modo sobreposto --vista camera --camera camera_diagonal --pasta /integ/varredura_cam 2>&1 | tail -2
mv $I/logs/sessao_*.jsonl $I/logs_capturas/ 2>/dev/null
# animacoes (ffmpeg do host): MP4 H.264 e GIF com paleta
cd $I
ffmpeg -y -loglevel error -framerate 4 -i varredura/q_%03d.png -vf "scale=1440:-2,format=yuv420p" -c:v libx264 -crf 23 evidencias/a12i_varredura_gemeo_lado.mp4
ffmpeg -y -loglevel error -framerate 4 -i varredura/q_%03d.png -vf "scale=900:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" evidencias/a12i_varredura_gemeo_lado.gif
ffmpeg -y -loglevel error -framerate 4 -i varredura_cam/q_%03d.png -vf "scale=1440:-2,format=yuv420p" -c:v libx264 -crf 23 evidencias/a12i_varredura_gemeo_sobreposto_diagonal.mp4
ffmpeg -y -loglevel error -framerate 4 -i varredura_cam/q_%03d.png -vf "scale=900:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" evidencias/a12i_varredura_gemeo_sobreposto_diagonal.gif
# tira de quadros (para o relatorio impresso): 8 quadros da varredura lado a lado
ffmpeg -y -loglevel error -i varredura/q_%03d.png -vf "select='not(mod(n\,9))',scale=720:-1,tile=4x2:padding=6:color=white" -frames:v 1 evidencias/a12i_varredura_tira.png
ls -la evidencias/
