#!/bin/bash
# Baixa three.js e urdf-loader do registro oficial do npm e copia os modulos usados
set -e
V=~/cerise2026/gemeo/repo/gemeo_digital/servidor/static/vendor
T=~/cerise2026/gemeo/tmp/npm
rm -rf $T; mkdir -p $T $V
cd $T
UV=$(curl -s https://registry.npmjs.org/urdf-loader/latest | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["version"])')
echo "urdf-loader latest: $UV"
curl -s https://registry.npmjs.org/urdf-loader/$UV | python3 -c 'import sys,json; d=json.load(sys.stdin); print("peer:", d.get("peerDependencies"), "lic:", d.get("license"))'
curl -sL -o three.tgz https://registry.npmjs.org/three/-/three-0.160.0.tgz
curl -sL -o urdf.tgz https://registry.npmjs.org/urdf-loader/-/urdf-loader-$UV.tgz
sha256sum three.tgz urdf.tgz
mkdir three urdf; tar xzf three.tgz -C three; tar xzf urdf.tgz -C urdf
mkdir -p $V/three/build $V/three/examples/jsm/loaders $V/three/examples/jsm/controls $V/three/examples/jsm/renderers $V/urdf-loader/src
cp three/package/build/three.module.js $V/three/build/
cp three/package/LICENSE $V/three/
for f in loaders/STLLoader.js loaders/ColladaLoader.js loaders/TGALoader.js controls/OrbitControls.js renderers/CSS2DRenderer.js; do cp three/package/examples/jsm/$f $V/three/examples/jsm/$f; done
cp urdf/package/src/*.js $V/urdf-loader/src/
cp urdf/package/LICENSE $V/urdf-loader/ 2>/dev/null || true
echo "three 0.160.0 / urdf-loader $UV" > $V/VERSOES.txt
grep -h "^import" $V/urdf-loader/src/*.js $V/three/examples/jsm/*/*.js | sort -u
du -sh $V; find $V -type f
