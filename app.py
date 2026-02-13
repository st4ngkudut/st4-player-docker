from flask import Flask, render_template, request, jsonify, render_template_string
import subprocess
import json
import os
import threading
import time
import socket
import re
import hashlib
import random
import requests
import serial
import shutil
from threading import Lock
from ytmusicapi import YTMusic
import yt_dlp

# --- DUMMY LIBRARY MANAGER ---
class MockLibMgr:
    def scan_directory(self, path):
        print(f"[Mock] Scanning {path}...")
    def get_scan_status(self):
        return {"status": "idle", "progress": 0, "count": 0}
    def get_all_tracks(self, sort_mode):
        return []

try:
    from library import lib_mgr
except ImportError:
    print("Warning: Library module not found. Using Mock Manager.")
    lib_mgr = MockLibMgr()

app = Flask(__name__)

# --- CONFIG DOCKER OPENWRT ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MPV_SOCKET = "/tmp/mpv_socket"
PLAYLIST_FILE = os.path.join(BASE_DIR, "playlist.json")
COVER_DIR = os.path.join(BASE_DIR, "static", "covers")
PLAY_SCRIPT = os.path.join(BASE_DIR, "play.sh")
DEFAULT_PATH_FILE = os.path.join(BASE_DIR, "default_path.txt")
BP_MODE_FILE = os.path.join(BASE_DIR, "state_bp_mode")
INTERNAL_MUSIC_PATH = "/music"
AUDIO_EXTS = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.wma', '.aac', '.dsf', '.dff')

state_lock = Lock()
yt_music = YTMusic()
needs_restore = False
stop_serial_flag = False

# --- GLOBAL STATE ---
st4_state = {
    "title": "Ready", "artist": "Waiting...", "album": "",
    "status": "stopped", "volume": 50, "active_preset": "Normal",
    "thumb": "", "queue": [], "current_index": -1,
    "sleep_target": 0, "current_eq_cmd": "",
    "last_play_time": 0, "error_count": 0, "manual_stop": False,
    "timer_display": "OFF", "tech_info": ""
}

af_state = {"eq": "", "balance": "", "crossfeed": ""}
download_status = {}

# Net Stats Vars
last_net_check = 0
last_rx = 0
last_tx = 0
curr_rx_speed = 0
curr_tx_speed = 0

# --- SERIAL SETUP ---
ser = None
serial_port = '/dev/ttyAML0' 

def init_serial():
    global ser
    if ser is not None:
        try: ser.close()
        except: pass
    try:
        ser = serial.Serial(serial_port, 115200, timeout=1)
        print(f"✅ Serial Connected: {serial_port}")
    except Exception as e:
        print(f"⚠️ Gagal Konek Serial: {e}")
        ser = None

init_serial()

# --- HELPERS ---
def mpv_send(cmd):
    if not os.path.exists(MPV_SOCKET): return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(MPV_SOCKET)
        s.send((json.dumps({"command": cmd}) + "\n").encode())
        res = s.recv(8192).decode()
        s.close()
        return json.loads(res).get("data")
    except: return None

def update_mpv_filters():
    # Cek Mode Bitperfect
    is_bp = False
    if os.path.exists(BP_MODE_FILE):
        try:
            with open(BP_MODE_FILE, 'r') as f: is_bp = (f.read().strip() == "1")
        except: pass
        
    if is_bp:
        mpv_send(["set_property", "af", ""])
        mpv_send(["set_property", "volume", 100])
        with state_lock: st4_state["volume"] = 100
        return

    filters = []
    if af_state["balance"]: filters.append(af_state["balance"])
    if af_state["eq"]: filters.append(af_state["eq"])
    if af_state["crossfeed"]: filters.append(af_state["crossfeed"])
    cmd_str = ",".join(filters) if filters else ""
    mpv_send(["set_property", "af", cmd_str])

EQ_PRESETS = {
    "Normal": {"f1":0,"f2":0,"f3":0,"f4":0,"f5":0,"f6":0,"f7":0,"f8":0,"f9":0,"f10":0},
    "Bass":   {"f1":7,"f2":6,"f3":5,"f4":3,"f5":0,"f6":0,"f7":0,"f8":-1,"f9":-2,"f10":-3},
    "Rock":   {"f1":5,"f2":3,"f3":1,"f4":-1,"f5":-2,"f6":0,"f7":2,"f8":4,"f9":5,"f10":5},
    "Pop":    {"f1":-1,"f2":1,"f3":3,"f4":4,"f5":4,"f6":2,"f7":0,"f8":1,"f9":2,"f10":2},
    "Jazz":   {"f1":2,"f2":2,"f3":3,"f4":2,"f5":2,"f6":4,"f7":2,"f8":2,"f9":3,"f10":3},
    "Vocal":  {"f1":-3,"f2":-3,"f3":-2,"f4":0,"f5":4,"f6":6,"f7":5,"f8":3,"f9":1,"f10":-1},
    "Dance":  {"f1":8,"f2":7,"f3":4,"f4":0,"f5":0,"f6":2,"f7":4,"f8":5,"f9":6,"f10":5},
    "Acoust": {"f1":1,"f2":2,"f3":2,"f4":3,"f5":4,"f6":4,"f7":3,"f8":2,"f9":3,"f10":2},
    "Party":  {"f1":7,"f2":6,"f3":4,"f4":1,"f5":2,"f6":4,"f7":5,"f8":5,"f9":6,"f10":5},
    "Soft":   {"f1":0,"f2":-1,"f3":-1,"f4":1,"f5":2,"f6":1,"f7":0,"f8":-1,"f9":-2,"f10":-4},
    "Metal":  {"f1":6,"f2":5,"f3":0,"f4":-2,"f5":-3,"f6":0,"f7":3,"f8":6,"f9":7,"f10":7},
    "Classic":{"f1":4,"f2":3,"f3":2,"f4":2,"f5":-1,"f6":-1,"f7":0,"f8":2,"f9":3,"f10":4},
    "RnB":    {"f1":6,"f2":5,"f3":3,"f4":0,"f5":-1,"f6":2,"f7":3,"f8":2,"f9":3,"f10":4},
    "Live":   {"f1":-2,"f2":0,"f3":2,"f4":3,"f5":4,"f6":4,"f7":4,"f8":3,"f9":2,"f10":1},
    "Techno": {"f1":8,"f2":7,"f3":0,"f4":-2,"f5":-2,"f6":0,"f7":2,"f8":4,"f9":6,"f10":6},
    "KZEDCPro": {"f1":6,"f2":5,"f3":3,"f4":1,"f5":0,"f6":0,"f7":-1,"f8":-1,"f9":0,"f10":0}
}

def get_yt_thumb(url):
    match = re.search(r"([a-zA-Z0-9_-]{11})", url or "")
    if match: return f"https://img.youtube.com/vi/{match.group(1)}/0.jpg"
    return ""

def trigger_play(url):
    global needs_restore
    if os.path.exists(PLAY_SCRIPT):
        os.chmod(PLAY_SCRIPT, 0o755)
        with state_lock:
            st4_state["last_play_time"] = time.time()
            if "http" in url: st4_state["thumb"] = get_yt_thumb(url)
            else: st4_state["thumb"] = ""
            st4_state["status"] = "loading"
            st4_state["manual_stop"] = False
        needs_restore = True
        subprocess.Popen(["/bin/bash", PLAY_SCRIPT, url])

def play_next_in_queue():
    with state_lock:
        if not st4_state["queue"]: return
        time_diff = time.time() - st4_state.get("last_play_time", 0)
        if time_diff < 2.0: st4_state["error_count"] += 1
        else: st4_state["error_count"] = 0
        
        if st4_state["error_count"] > 5:
            st4_state["status"] = "stopped"
            return
            
        next_idx = st4_state["current_index"] + 1
        if next_idx < len(st4_state["queue"]):
            st4_state["current_index"] = next_idx
            next_song = st4_state["queue"][next_idx]
            threading.Thread(target=trigger_play, args=(next_song['link'],)).start()
        else:
            st4_state["status"] = "stopped"

def find_key_insensitive(data, search_keys):
    if not data or not isinstance(data, dict): return ""
    for k in search_keys:
        for data_k, data_v in data.items():
            if data_k.lower() == k.lower(): return data_v
    return ""

# --- WORKERS ---
def serial_read_worker():
    global ser, stop_serial_flag
    while True:
        if stop_serial_flag:
            time.sleep(1)
            continue
        if ser is None:
            init_serial()
            time.sleep(2)
            continue
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("cmd:"):
                    # Handle basic commands from older remote code if any
                    pass 
        except:
            ser = None
        time.sleep(0.05)

def metadata_worker():
    global st4_state, needs_restore, ser, stop_serial_flag
    last_path = ""
    idle_counter = 0
    
    while True:
        try:
            # Sleep Timer
            with state_lock:
                target = st4_state["sleep_target"]
                if target > 0:
                    remaining = int(target - time.time())
                    if remaining > 0: st4_state["timer_display"] = f"{int(remaining/60)+1}m"
                    else:
                        st4_state["sleep_target"] = 0
                        st4_state["timer_display"] = "OFF"
                        st4_state["queue"] = []
                        st4_state["current_index"] = -1
                        threading.Thread(target=mpv_send, args=(["stop"],)).start()
                else:
                    st4_state["timer_display"] = "OFF"

            # MPV Logic
            mpv_ready = False
            try:
                if mpv_send(["get_property", "idle-active"]) is not None: mpv_ready = True
            except: pass
            
            if mpv_ready:
                idle_counter = 0
                path = mpv_send(["get_property", "path"])
                
                if path and (path != last_path or needs_restore):
                    last_path = path
                    needs_restore = False
                    time.sleep(0.5)
                    with state_lock: saved_vol = st4_state["volume"]
                    mpv_send(["set_property", "volume", saved_vol])
                    update_mpv_filters()
                
                is_eof = mpv_send(["get_property", "eof-reached"])
                is_idle = mpv_send(["get_property", "idle-active"])
                
                if st4_state.get("manual_stop", False):
                    if is_idle:
                        with state_lock: st4_state["manual_stop"] = False
                elif is_eof is True or (is_idle is True and st4_state["status"] == "playing"):
                    play_next_in_queue()
                    time.sleep(1)
                    continue
                
                # Fetch Meta
                meta_all = mpv_send(["get_property", "metadata"]) or {}
                mpv_title = mpv_send(["get_property", "media-title"])
                
                queue_title = "Unknown Title"
                with state_lock:
                    if st4_state["queue"] and st4_state["current_index"] < len(st4_state["queue"]):
                        queue_title = st4_state["queue"][st4_state["current_index"]]['title']
                
                final_title = queue_title
                if mpv_title and not any(x in mpv_title.lower() for x in ["http", "www.", ".com", "googlevideo"]):
                    final_title = mpv_title
                
                temp_artist = find_key_insensitive(meta_all, ["artist", "performer", "composer"]) or "Unknown Artist"
                temp_album = find_key_insensitive(meta_all, ["album"]) or ""
                
                # Tech Info Construction
                tech_parts = []
                codec = mpv_send(["get_property", "audio-codec-name"])
                fmt = mpv_send(["get_property", "audio-params/format"])
                rate = mpv_send(["get_property", "audio-params/samplerate"])
                br = mpv_send(["get_property", "audio-bitrate"])
                
                if codec: tech_parts.append(codec.upper())
                if br and int(br) > 0: tech_parts.append(f"{int(int(br)/1000)}kbps")
                if rate: tech_parts.append(f"{float(rate)/1000:g}kHz")
                
                bit_depth = ""
                if fmt:
                    if 's16' in fmt: bit_depth = "16bit"
                    elif 's24' in fmt: bit_depth = "24bit"
                    elif 's32' in fmt or 'float' in fmt: bit_depth = "32bit"
                    elif 'dsd' in fmt: bit_depth = "1bit(DSD)"
                if bit_depth and codec and not any(x in codec.upper() for x in ['MP3', 'AAC', 'VORBIS', 'OPUS']):
                    tech_parts.append(bit_depth)
                
                badge = "Lossless"
                if codec and any(x in codec.upper() for x in ['MP3', 'AAC', 'VORBIS', 'OPUS']): badge = "Lossy"
                elif (bit_depth in ["24bit", "32bit"]) or (rate and float(rate) > 48000): badge = "Hi-Res"
                tech_parts.append(badge)
                
                temp_info = " • ".join(tech_parts)
                is_paused = mpv_send(["get_property", "pause"])
                
                with state_lock:
                    st4_state.update({
                        "title": final_title,
                        "artist": temp_artist, "album": temp_album,
                        "status": "paused" if is_paused else "playing",
                        "tech_info": temp_info,
                        "current_time": mpv_send(["get_property", "time-pos"]) or 0,
                        "total_time": mpv_send(["get_property", "duration"]) or 0
                    })
                    val_vol = mpv_send(["get_property", "volume"])
                    if val_vol is not None: st4_state["volume"] = val_vol
            else:
                idle_counter += 1
                if idle_counter == 5:
                    with state_lock: st4_state["status"] = "stopped"
            
            # Send to ESP
            if ser and not stop_serial_flag:
                try:
                    with state_lock:
                        mini_state = {
                            "title": st4_state["title"],
                            "artist": st4_state["artist"],
                            "album": st4_state["album"],
                            "status": st4_state["status"],
                            "volume": int(st4_state["volume"]),
                            "tech_info": st4_state["tech_info"],
                            "current_index": st4_state["current_index"],
                            "current_time": st4_state["current_time"],
                            "total_time": st4_state["total_time"],
                            "timer_display": st4_state["timer_display"],
                            "active_preset": st4_state["active_preset"]
                        }
                    ser.write((json.dumps(mini_state) + '\n').encode('utf-8'))
                except: pass

        except Exception as e: pass
        time.sleep(1)

# Start Background Workers
threading.Thread(target=serial_read_worker, daemon=True).start()
threading.Thread(target=metadata_worker, daemon=True).start()

# --- WEB & API ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/status')
def status():
    with state_lock: return jsonify(st4_state)

# --- [NEW] BROWSER API FOR ARDUINO ---
@app.route('/browser/list')
def browser_list():
    # Arduino sends: path, start, limit
    req_path = request.args.get('path', '')
    start = int(request.args.get('start', 0))
    limit = int(request.args.get('limit', 4))
    
    # Secure Path
    base = os.path.abspath(INTERNAL_MUSIC_PATH)
    if not req_path:
        target_dir = base
        current_display = "/"
        parent_path = "EXIT"
    else:
        target_dir = os.path.abspath(os.path.join(base, req_path))
        if not target_dir.startswith(base): target_dir = base
        current_display = req_path
        parent_path = os.path.dirname(req_path)
        if parent_path == "" or parent_path == "/": parent_path = ""

    items = []
    try:
        # Create ".." entry if not root
        entries = sorted(os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
        for e in entries:
            if e.name.startswith('.'): continue
            if e.is_dir():
                items.append({"n": e.name, "p": os.path.join(req_path, e.name), "t": "D"})
            elif e.is_file() and e.name.lower().endswith(AUDIO_EXTS):
                items.append({"n": e.name, "p": os.path.join(req_path, e.name), "t": "F"})
    except: pass

    # Pagination
    total = len(items)
    sliced_items = items[start : start + limit]
    
    return jsonify({
        "total": total,
        "current": current_display,
        "parent": parent_path,
        "items": sliced_items
    })

@app.route('/browser/play_file')
def browser_play_file():
    rel_path = request.args.get('path', '')
    full_path = os.path.join(INTERNAL_MUSIC_PATH, rel_path)
    
    # Setup single song queue
    with state_lock:
        st4_state["queue"] = [{'link': full_path, 'title': os.path.basename(full_path)}]
        st4_state["current_index"] = 0
        st4_state["error_count"] = 0
    
    threading.Thread(target=trigger_play, args=(full_path,)).start()
    return jsonify({"status": "ok"})

@app.route('/browser/play_folder')
def browser_play_folder():
    rel_path = request.args.get('path', '')
    full_path = os.path.join(INTERNAL_MUSIC_PATH, rel_path)
    
    try:
        files = [f for f in os.listdir(full_path) if f.lower().endswith(AUDIO_EXTS)]
        files.sort(key=lambda x: x.lower())
        
        new_queue = []
        for f in files:
            new_queue.append({'link': os.path.join(full_path, f), 'title': f})
            
        if new_queue:
            with state_lock:
                st4_state["queue"] = new_queue
                st4_state["current_index"] = 0
                st4_state["error_count"] = 0
            threading.Thread(target=trigger_play, args=(new_queue[0]['link'],)).start()
            return jsonify({"status": "playing_folder", "count": len(new_queue)})
    except: pass
    return jsonify({"error": "empty or invalid"})

# --- [NEW] SYSTEM TOOLS COMMANDS ---
@app.route('/system/exec_cmd')
def system_exec():
    key = request.args.get('key', '')
    msg = "Unknown Cmd"
    
    # Warning: Running as root inside Docker
    try:
        if key == "ping_test":
            res = subprocess.run(["ping", "-c", "1", "8.8.8.8"], stdout=subprocess.DEVNULL)
            msg = "Internet OK" if res.returncode == 0 else "No Internet"
        elif key == "check_ip":
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80)); ip = s.getsockname()[0]
                msg = ip
            except: msg = "No IP"
            finally: s.close()
        elif key == "clean_ram":
            subprocess.run("sync; echo 3 > /proc/sys/vm/drop_caches", shell=True)
            msg = "RAM Cleaned"
        elif key == "restart_net":
            # Restart networking container side (might not affect host much)
            msg = "Net Restarted" 
        elif key == "reboot_system":
            # Dangerous! Only works if container is privileged
            threading.Thread(target=lambda: (time.sleep(1), subprocess.run(["reboot"]))).start()
            msg = "Rebooting..."
        elif key == "restart_docker":
            # Cant restart self easily, assume calling host watchdog?
            msg = "Not Supported"
    except Exception as e:
        msg = "Error"
        
    return jsonify({"msg": msg})

# --- [NEW] REAL SYSTEM STATS ---
@app.route('/system/stats')
def system_stats():
    # CPU Temp
    temp = "0C"
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            t = int(f.read().strip())
            temp = f"{t/1000:.0f}C"
    except: pass
    
    # RAM
    ram = "-/-"
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            total = int(lines[0].split()[1]) // 1024
            free = int(lines[1].split()[1]) // 1024
            used = total - free
            ram = f"{used}/{total}"
    except: pass
    
    # Disk (Music Path)
    disk = "-"
    try:
        total, used, free = shutil.disk_usage(INTERNAL_MUSIC_PATH)
        percent = (used / total) * 100
        disk = f"{percent:.0f}%"
    except: pass
    
    # Uptime
    uptime = "-"
    try:
        with open("/proc/uptime", "r") as f:
            u = float(f.read().split()[0])
            uptime = f"{int(u/3600)}h"
    except: pass
    
    return jsonify({
        "temp": temp, "ram": ram, "disk": disk, "uptime": uptime
    })

# --- [NEW] NETWORK SPEED MONITOR ---
@app.route('/system/net_stats')
def net_stats():
    global last_net_check, last_rx, last_tx, curr_rx_speed, curr_tx_speed
    
    now = time.time()
    if now - last_net_check >= 1.0:
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
                for line in lines:
                    if "eth0" in line: # Or wlan0 depending on STB
                        parts = line.split()
                        # eth0: parts[0] is name, parts[1] is RX bytes, parts[9] is TX bytes
                        rx = int(parts[1])
                        tx = int(parts[9])
                        
                        if last_net_check > 0:
                            curr_rx_speed = (rx - last_rx) / 1024 # KB/s
                            curr_tx_speed = (tx - last_tx) / 1024 # KB/s
                        
                        last_rx = rx
                        last_tx = tx
                        last_net_check = now
                        break
        except: pass

    # Format for Arduino
    # dl_val: 0-100 (visual bar), dl_str: string display
    dl_kb = int(curr_rx_speed)
    ul_kb = int(curr_tx_speed)
    
    dl_str = f"{dl_kb}K" if dl_kb < 1000 else f"{dl_kb/1024:.1f}M"
    ul_str = f"{ul_kb}K" if ul_kb < 1000 else f"{ul_kb/1024:.1f}M"
    
    # Simple mapping for progress bar (scale 0-10MB/s)
    dl_val = min(100, int(dl_kb / 100)) 
    ul_val = min(100, int(ul_kb / 100))

    return jsonify({
        "dl_str": dl_str, "dl_val": dl_val,
        "ul_str": ul_str, "ul_val": ul_val
    })

# --- STANDARD CONTROLS (OLD BUT GOLD) ---
@app.route('/control/<action>')
def control(action):
    if action == "pause": mpv_send(["cycle", "pause"])
    elif action == "stop":
        mpv_send(["stop"])
        with state_lock:
            st4_state["status"] = "stopped"
            st4_state["queue"] = []
            st4_state["current_index"] = -1
    elif action == "next": play_next_in_queue()
    elif action == "prev":
        with state_lock:
            if st4_state["current_index"] > 0:
                st4_state["current_index"] -= 1
                trigger_play(st4_state["queue"][st4_state["current_index"]]['link'])
    elif "volume" in action:
        try:
            v = int(request.args.get('val', 50))
            mpv_send(["set_property", "volume", v])
            with state_lock: st4_state["volume"] = v
        except: pass
    elif "jump" in action:
        try:
            idx = int(request.args.get('index', 0))
            with state_lock:
                if 0 <= idx < len(st4_state["queue"]):
                    st4_state["current_index"] = idx
                    trigger_play(st4_state["queue"][idx]['link'])
        except: pass
    return jsonify({"status": "ok"})

@app.route('/control/preset')
def set_preset():
    n = request.args.get('name')
    if n in EQ_PRESETS:
        preset = EQ_PRESETS[n]
        freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
        entries = []
        for i in range(1, 11):
            val = float(preset.get(f'f{i}', 0))
            entries.append(f"entry({freqs[i-1]},{val})")
        cmd_str = f"firequalizer=gain_entry='{';'.join(entries)}'"
        af_state["eq"] = f"lavfi=[{cmd_str}]"
        update_mpv_filters()
        with state_lock:
            st4_state["active_preset"] = n
            st4_state["current_eq_cmd"] = af_state["eq"]
        return jsonify(preset)
    return jsonify({"error": "not found"})

@app.route('/control/eq')
def set_eq():
    p = request.args
    gains = {}
    for i in range(1, 11): gains[f'f{i}'] = p.get(f'f{i}', 0)
    freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    entries = []
    for i in range(1, 11):
        val = float(gains.get(f'f{i}', 0))
        entries.append(f"entry({freqs[i-1]},{val})")
    cmd_str = f"firequalizer=gain_entry='{';'.join(entries)}'"
    af_state["eq"] = f"lavfi=[{cmd_str}]"
    update_mpv_filters()
    with state_lock: st4_state["current_eq_cmd"] = af_state["eq"]
    return jsonify({"status": "ok"})

@app.route('/control/bitperfect')
def toggle_bitperfect():
    current = "0"
    if os.path.exists(BP_MODE_FILE):
        try:
            with open(BP_MODE_FILE, 'r') as f: current = f.read().strip()
        except: pass
    new_state = "1" if current == "0" else "0"
    with open(BP_MODE_FILE, 'w') as f: f.write(new_state)
    update_mpv_filters()
    return jsonify({"status": "ok", "bitperfect": new_state == "1"})

@app.route('/control/crossfeed')
def toggle_crossfeed():
    state = request.args.get('state', 'on')
    af_state["crossfeed"] = "lavfi=[bs2b=profile=cmoy]" if state == 'on' else ""
    update_mpv_filters()
    return jsonify({"status": "ok", "crossfeed": state == 'on'})

@app.route('/control/balance')
def set_balance():
    try:
        l_vol = float(request.args.get('l', 1.0))
        r_vol = float(request.args.get('r', 1.0))
    except: l_vol = 1.0; r_vol = 1.0
    pan_cmd = f"pan=stereo|c0={l_vol:.2f}*c0|c1={r_vol:.2f}*c1"
    if l_vol >= 0.99 and r_vol >= 0.99: af_state["balance"] = ""
    else: af_state["balance"] = f"lavfi=[{pan_cmd}]"
    update_mpv_filters()
    return jsonify({"status": "ok"})

@app.route('/system/timer')
def set_timer():
    try: minutes = int(request.args.get('min', 0))
    except: minutes = 0
    with state_lock: st4_state["sleep_target"] = (time.time() + minutes*60) if minutes > 0 else 0
    return jsonify({"status": "ok", "timer": minutes})

@app.route('/queue/list')
def get_queue():
    start = int(request.args.get('start', 0))
    limit = int(request.args.get('limit', 4))
    with state_lock:
        total = len(st4_state["queue"])
        sliced = []
        for i in range(start, min(start + limit, total)):
            item = st4_state["queue"][i]
            sliced.append({"i": i, "t": item['title']})
        return jsonify({
            "total": total,
            "current": st4_state["current_index"],
            "items": sliced
        })

@app.route('/search')
def search_yt():
    query = request.args.get('q', '')
    if not query: return jsonify([])
    try:
        results = yt_music.search(query, filter="songs", limit=15)
        data = []
        for r in results:
            thumb = r['thumbnails'][-1]['url'] if 'thumbnails' in r else ""
            artists = ", ".join([a['name'] for a in r.get('artists', [])])
            data.append({'title': r.get('title'), 'artist': artists, 'duration': r.get('duration',''), 'thumb': thumb, 'link': f"https://music.youtube.com/watch?v={r['videoId']}", 'videoId': r['videoId']})
        return jsonify(data)
    except: return jsonify([])

@app.route('/play')
def play():
    # Handle Web UI Play Requests
    url = request.args.get('url')
    title = request.args.get('title', 'Unknown')
    mode = request.args.get('mode', 'play_now')
    
    if not url: return jsonify({"error": "no url"})
    song = {'link': url, 'title': title}
    
    with state_lock:
        if mode == 'play_now':
            st4_state["queue"] = [song]
            st4_state["current_index"] = 0
            trigger_play(url)
        elif mode == 'enqueue':
            st4_state["queue"].append(song)
            if st4_state["status"] == "stopped":
                st4_state["current_index"] = 0
                trigger_play(url)
                
    return jsonify({"status": "ok"})

# --- FLASHER (KEEP THIS) ---
@app.route('/flasher')
def flasher_ui():
    return render_template_string("""
    <html><body><h1>ESP8266 Flasher</h1>
    <form action="/flash_now" method="post" enctype="multipart/form-data">
    <input type="file" name="firmware" required><br><br>
    <button type="submit">⚡ FLASH NOW ⚡</button>
    </form></body></html>""")

@app.route('/flash_now', methods=['POST'])
def flash_now():
    global ser, stop_serial_flag
    if 'firmware' not in request.files: return "No file"
    f = request.files['firmware']
    if f.filename == '': return "No file"
    
    stop_serial_flag = True
    if ser: 
        try: ser.close()
        except: pass
        ser = None
    time.sleep(1)
    
    f.save("/tmp/firmware.bin")
    cmd = f"esptool.py --port {serial_port} --baud 460800 write_flash --flash_size=detect 0x0 /tmp/firmware.bin"
    subprocess.run(cmd, shell=True)
    
    init_serial()
    stop_serial_flag = False
    return "Done. Please restart ESP."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
