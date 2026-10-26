cd ~/braco/dataset
ls *.json | sed 's/.json//' | awk '{w=($1+0)%8; c[w]++} END {for (w=0;w<8;w++) printf "w%d=%d ", w, c[w]; print ""}'
for f in ~/braco/gen_logs/w*.log; do echo "$(basename $f): $(grep -c 'FIM:' $f) fim, $(grep -c 'pulando foto' $f) pulos, ultima: $(grep -oE '\[[0-9]+/[0-9]+\] id [0-9]+' $f | tail -1)"; done
date
