# ST4 Player (Audiophile STB Music Server)

**ST4 Player** adalah aplikasi pemutar musik *headless* berbasis Python
& Flask yang dirancang khusus untuk berjalan di **STB OpenWrt (Amlogic
HG680P/B860H)** via Docker.

Aplikasi ini mengubah STB bekas menjadi **Music Server Audiophile**
dengan kemampuan DSP (EQ, Crossfeed), integrasi YouTube Music, dan
kontrol hardware dua arah melalui Serial Port (UART) ke Remote/Display
eksternal (ESP8266).

![ST4 Player UI](static/img/default.png)

------------------------------------------------------------------------

## Fitur Utama

-   **Playback Engine:** Menggunakan `mpv` untuk kualitas audio tinggi
    (FLAC, MP3, WAV, AAC, DSD via DoP).
-   **Web Interface:** Antarmuka responsif untuk kontrol, manajemen
    playlist, dan file browser.
-   **DSP & Audio Processing:**
    -   10-Band Equalizer dengan Preset.
    -   **Bitperfect Mode:** Bypass semua filter untuk audio murni.
    -   **Crossfeed (CMoy):** Simulasi speaker untuk headphone.
-   **YouTube Music Integration:** Cari, putar, dan **download** lagu
    dari YT Music.
-   **Hardware Integration (Serial/UART):**
    -   Mengirim metadata lagu ke display eksternal.
    -   Menerima perintah fisik (Knob/Tombol) dari hardware eksternal.
    -   **OTA Flasher:** Flash firmware ESP8266 langsung dari Web UI
        STB.

------------------------------------------------------------------------

## Prasyarat Hardware

1.  **STB Amlogic** (HG680P, B860H, dll) dengan firmware **OpenWrt**.
2.  **USB DAC** (Opsional, sangat disarankan).
3.  **Koneksi Serial:** Pin UART internal STB (GND, TX, RX) terhubung ke
    ESP8266/ESP32.

------------------------------------------------------------------------

## Instalasi (Docker)

Metode ini paling bersih dan aman untuk sistem OpenWrt.

### 1. Persiapan Sistem (Host OpenWrt)

Matikan akses console sistem ke serial port `/dev/ttyAML0` agar bisa
dipakai Python.

1.  SSH ke STB

2.  Edit file inittab:

    ``` bash
    nano /etc/inittab
    ```

3.  Beri tanda `#` pada baris ttyAML0:

    ``` text
    # ::askconsole:/usr/libexec/login.sh ttyAML0
    ```

4.  **Reboot STB**

------------------------------------------------------------------------

### 2. Build Docker Image

Lakukan build langsung di STB (pastikan koneksi internet lancar).

``` bash
cd /root/st4-player

# Gunakan --network=host agar proses build bisa akses internet
docker build --network=host -t st4player .
```

------------------------------------------------------------------------

### 3. Jalankan Container

Jalankan perintah berikut.\
**PENTING:** Sesuaikan path volume (`-v`) dengan lokasi lagu Anda.

``` bash
docker run -d \
  --name st4player \
  --restart unless-stopped \
  --net=host \
  --privileged \
  --device /dev/snd:/dev/snd \
  --device /dev/ttyAML0:/dev/ttyAML0 \
  -v /root/st4-player/music.db:/app/music.db \
  -v /root/st4-player/playlist.json:/app/playlist.json \
  -v /mnt/mmcblk2p4/music:/music \
  -e TZ=Asia/Jakarta \
  st4player
```

**Catatan:**\
Ganti `/mnt/mmcblk2p4/music` dengan path folder musik di harddisk
eksternal / SD Card Anda.

------------------------------------------------------------------------

## Struktur Direktori

    /st4-player
    â”œâ”€â”€ app.py              # Logic Utama (Flask)
    â”œâ”€â”€ library.py          # Modul Scanner Lagu
    â”œâ”€â”€ play.sh             # Script Wrapper MPV
    â”œâ”€â”€ Dockerfile          # Config Docker
    â”œâ”€â”€ requirements.txt    # Python Libs
    â”œâ”€â”€ static/             # Assets Web (CSS/JS)
    â”œâ”€â”€ templates/          # HTML Files
    â””â”€â”€ music.db            # Database (Auto-generated)

------------------------------------------------------------------------

## API Endpoints & Serial

### HTTP API

  Method   Endpoint                  Deskripsi
  -------- ------------------------- -------------------------------
  GET      /status                   Cek status player (JSON)
  GET      /play?url={link}          Putar lagu (lokal / URL)
  GET      /control/{action}         play, pause, next, prev, stop
  GET      /control/volume?val=XX    Set volume (0-100)
  GET      /download_song?id={vid}   Download dari YT Music

------------------------------------------------------------------------

### Serial Protocol (UART)

Baudrate: **115200**

#### STB ESP (JSON Line)

``` json
{"title": "Song", "artist": "Band", "status": "playing", "volume": 50}
```

#### ESP STB (String Command + newline)

    cmd:play
    cmd:pause
    cmd:next
    cmd:prev
    cmd:volume=80

------------------------------------------------------------------------

## Troubleshooting

### Build Error (Network)

Selalu gunakan flag:

    --network=host

### Tidak Ada Suara

-   Pastikan device audio terpasang:

        --device /dev/snd:/dev/snd

-   Cek volume host:

        alsamixer

-   Cek file audio valid.

### Serial Error / Flashing Gagal

-   Pastikan `/etc/inittab` sudah diedit & STB sudah reboot.
-   Cek kabel:
    -   TX STB â†’ RX ESP
    -   RX STB â†’ TX ESP
    -   GND harus menyatu.

### Lagu Tidak Terbaca

-   Cek mounting volume `-v`.
-   Gunakan menu **Rescan Library** di Web UI.

------------------------------------------------------------------------

## License

Project ini dibuat untuk edukasi dan hobi.

Based on: - Flask\
- MPV\
- YT-DLP
