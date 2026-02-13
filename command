docker run -d \
  --name st4player \
  --restart unless-stopped \
  --net=host \
  --device /dev/snd:/dev/snd \
  --device /dev/ttyAML0:/dev/ttyAML0 \
  -v /mnt/mmcblk2p4/music:/music \ 
  -e TZ=Asia/Jakarta \
  st4player