cd ~/cerise2026/gemeo/repo
python3 -c "import json; d=json.load(open('resultados/capturas_verificacao.json')); print('\n'.join(d['lado']['console']))" | head -20
F=gemeo_digital/servidor/static/vendor/urdf-loader/src/URDFLoader.js
grep -n -A25 'defaultMeshLoader(path' $F | head -40
grep -n -B3 -A25 'loadMeshCb(filePath' $F | head -50
