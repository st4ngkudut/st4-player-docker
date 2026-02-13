#!/bin/bash

SOCKET="/tmp/mpv_socket"
URL="$1"

# --- KONFIGURASI DAC ---
# Ganti angka 1,0 sesuai hasil aplay -l Anda
# Format: alsa/plughw:CARD,DEVICE
# Jika DAC di card 1: alsa/plughw:1,0
# Jika DAC di card 0: alsa/plughw:0,0
AUDIO_DEV="alsa/plughw:0,0"

start_mpv() {
    echo "Starting MPV Daemon..."
    rm -f "$SOCKET"
    
    # Jalankan MPV dengan parameter audio device
    nohup mpv --idle=yes \
        --input-ipc-server="$SOCKET" \
        --audio-device="$AUDIO_DEV" \
        --no-video \
        --volume=100 \
        > /dev/null 2>&1 &

    TIMEOUT=50
    while [ ! -S "$SOCKET" ]; do
        sleep 0.1
        TIMEOUT=$((TIMEOUT-1))
        if [ $TIMEOUT -le 0 ]; then exit 1; fi
    done
    sleep 0.2
}

if ! pgrep -x "mpv" > /dev/null || [ ! -S "$SOCKET" ]; then
    pkill -x mpv
    start_mpv
fi

echo "{ \"command\": [\"loadfile\", \"$URL\", \"replace\"] }" | socat - "$SOCKET"
