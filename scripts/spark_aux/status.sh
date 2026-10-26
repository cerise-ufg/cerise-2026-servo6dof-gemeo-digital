date
tail -3 ~/braco/gen_main.log
for f in ~/braco/gen_logs/w*.log; do
  n=$(grep -c 'FIM:' $f); last=$(grep -E '\[[0-9]+/[0-9]+\] id' $f | tail -1 | grep -oE '\[[0-9]+/[0-9]+\] id [0-9]+')
  echo "$(basename $f) fim=$n ultimo=$last"
done
ls ~/braco/dataset/*.json | wc -l
uptime
sudo docker ps -a --filter name=braco_gen --format '{{.Names}} {{.Status}}'
