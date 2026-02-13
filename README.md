# ST4 Player (Audiophile STB Music Server - Hybrid Edition)

**ST4 Player** adalah aplikasi pemutar musik *headless* berbasis Python
& Flask yang dirancang khusus untuk berjalan di **STB OpenWrt (Amlogic
HG680P/B860H)** via Docker.

Versi ini menggunakan sistem **Komunikasi Hybrid**:

-   **WiFi (HTTP)** ’ Jalur utama untuk kontrol cepat, browsing file,
    dan pengambilan metadata (Judul, Cover, Stats) ke Remote ESP8266.
-   **Serial (UART)** ’ Jalur khusus untuk fitur OTA Flasher (flash
    firmware ESP tanpa kabel USB) dan backup stream.

------------------------------------------------------------------------

## Fitur Utama

### Playback Engine

Menggunakan **mpv** untuk kualitas audio tinggi (FLAC, MP3, WAV, AAC,
DSD via DoP).

### Web Interface

Antarmuka responsif untuk manajemen playlist, kontrol playback, dan
konfigurasi sistem.

### DSP & Audio Processing

-   10-Band Equalizer (Preset & Manual)
-   Bitperfect Mode (bypass software mixer)
-   Crossfeed (CMoy)
-   Balance L/R Channel

### Remote Control Canggih (ESP8266)

-   OLED display metadata realtime
-   Progress bar playback
-   File browser langsung dari remote
-   System monitor:
    -   CPU temperature
    -   RAM usage
    -   Disk usage
    -   Internet speed (DL / UL)
-   Tools:
    -   Ping test
    -   Clean RAM
    -   Reboot STB

### YouTube Music Integration

Cari, putar, dan download lagu langsung ke storage lokal.

### OTA Flasher

Flash firmware ESP8266 langsung dari Web UI STB via kabel serial.

------------------------------------------------------------------------

## 1. Prasyarat Hardware

### STB

-   Amlogic HG680P / B860H / sejenis
-   Firmware OpenWrt

### Audio

-   USB DAC (sangat disarankan)

### Remote Hardware

-   ESP8266 (NodeMCU / Wemos D1 Mini)
-   OLED 128x64 (SPI / I2C)
-   Rotary Encoder

### Koneksi

-   STB dan ESP harus dalam jaringan WiFi / LAN yang sama
-   Kabel serial jumper:
    -   GND > GND
    -   TX STB > RX ESP
    -   RX STB > TX ESP

(Wajib untuk fitur flasher)

------------------------------------------------------------------------

## Instalasi (Docker)

Metode paling bersih dan aman untuk OpenWrt.

------------------------------------------------------------------------

### 1. Persiapan Sistem OpenWrt ( OPSIONAL / Bisa di skip )

Matikan console serial agar bisa dipakai Python.

``` bash
nano /etc/inittab
```

Comment:

    # ::askconsole:/usr/libexec/login.sh ttyAML0

Reboot STB.

------------------------------------------------------------------------

### 2. Siapkan File Database (WAJIB)

``` bash
cd /root && git clone https://github.com/st4ngkudut/st4-player-docker.git
cd /root/st4-player-docker
touch music.db
echo "[]" > playlist.json
```

------------------------------------------------------------------------

### 3. Build Docker Image

``` bash
docker build --network=host -t st4player .
```

------------------------------------------------------------------------

### 4. Jalankan Container

``` bash
docker run -d \
  --name st4player \
  --restart unless-stopped \
  --net=host \
  --privileged \
  --device /dev/snd:/dev/snd \
  --device /dev/ttyAML0:/dev/ttyAML0 \
  -v "$PWD/music.db":/app/music.db \
  -v "$PWD/playlist.json":/app/playlist.json \
  -v /mnt/mmcblk2p4/music:/music \
  -e TZ=Asia/Jakarta \
  st4player
```

------------------------------------------------------------------------

## API Endpoints (Hybrid Remote)

Digunakan oleh ESP8266 via WiFi.

  Method   Endpoint               Fungsi
  -------- ---------------------- -------------------
  GET      /status                Status player
  GET      /browser/list          List file browser
  GET      /browser/play_file     Play file
  GET      /browser/play_folder   Play folder
  GET      /system/stats          CPU, RAM, Disk
  GET      /system/net_stats      Speed internet
  GET      /system/exec_cmd       Tools system
  GET      /control/eq            Set equalizer
  GET      /control/balance       Set balance
  GET      /play?url=             Play URL / path

------------------------------------------------------------------------

## ðŸ”Œ Protokol Komunikasi

### 1. WiFi HTTP (Primary)

-   ESP kirim perintah ke STB
-   ESP polling JSON untuk update OLED

### 2. Serial UART (Secondary)

-   Baudrate 115200
-   Untuk OTA flash firmware ESP
-   Tidak perlu lepas hardware

------------------------------------------------------------------------

## Troubleshooting

### Remote tidak konek

-   Pastikan IP STB tidak berubah
-   Reconfig WiFi remote jika perlu

------------------------------------------------------------------------

### socat connection refused

Normal saat MPV belum siap.

------------------------------------------------------------------------

### Docker mount error

Pastikan file database sudah dibuat sebelum run.

------------------------------------------------------------------------

### Tidak ada suara

Cek:

``` bash
aplay -l
alsamixer
```

------------------------------------------------------------------------

## License

Project komunitas OpenWrt Indonesia.

Stack: - Flask - Arduino C++ - MPV - Docker

------------------------------------------------------------------------

Happy Listening!
