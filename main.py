import time
import threading
import os
import sys

# --- MINIMAL STARTUP CONSTANTS ---
KATANA_HEADER = [0x41, 0x10, 0x01, 0x05, 0x07]
CMD_DT1 = 0x12
CMD_RQ1 = 0x11
CONFIG_FILE = "config.json"

# --- GLOBAL STATE (Minimal) ---
current_mode = "DIRECT"
edit_mode = False 
last_interaction_time = 0 
start_time = time.time()
handlers = []
lcd_lock = threading.Lock() # Lock to prevent SPI bus contention

# --- DELAYED IMPORTS & LOGIC WRAPPER ---
def delayed_init():
    """Import heavy modules and load config after startup sequence begins."""
    global mido, json, Button, Flask, SocketIO, emit, spi, ili9341, canvas, Image, ImageDraw, ImageFont
    global GPIO_CONFIG, MODE_MAPPINGS, PRESETS, web_server
    
    import mido
    import json
    from flask import Flask, render_template, request
    from flask_socketio import SocketIO, emit
    from luma.core.interface.serial import spi
    from luma.lcd.device import ili9341
    from luma.core.render import canvas
    from PIL import Image, ImageDraw, ImageFont
    from gpiozero import Button

    load_config()
    
    # Initialize hardware button handlers now that Button is imported
    global handlers, mode_btn, edit_btn
    handlers = [ButtonHandler(btn_id, pin) for btn_id, pin in GPIO_CONFIG.items()]
    
    mode_btn = Button(MODE_SWITCH_PIN, pull_up=True, bounce_time=0.05)
    mode_btn.when_pressed = lambda: (
        print(f"[DEBUG] SYSTEM: MODE SWITCH (Pin: {MODE_SWITCH_PIN})") if PRINT_DEBUG else None,
        toggle_global_mode()
    )
    
    edit_btn = Button(PRESET_EDIT_PIN, pull_up=True, bounce_time=0.05)
    edit_btn.when_pressed = lambda: (
        print(f"[DEBUG] SYSTEM: PRESET EDIT (Pin: {PRESET_EDIT_PIN})") if PRINT_DEBUG else None,
        toggle_preset_edit()
    )

    # Initialize Web server
    web_server = WebHandler(
        state_getter=get_full_state_dict, toggle_mode_fn=lambda: toggle_global_mode(),
        toggle_edit_fn=lambda: toggle_preset_edit(), save_preset_fn=lambda bid: save_preset_to_button(bid),
        control_btn_fn=handle_web_control
    )

# --- CONFIGURATION PERSISTENCE ---
DEFAULT_GPIO_CONFIG = {
    "BTN_1": 13, "BTN_2": 5, "BTN_3": 12,
    "BTN_4": 19, "BTN_5": 6, "BTN_6": 26,
    "BTN_7": 16, "BTN_8": 21, "BTN_9": 20
}

DEFAULT_MODE_MAPPINGS = {
    "DIRECT": {
        "BTN_1": "Amp Type", "BTN_2": "Variation", "BTN_3": "Boost",
        "BTN_4": "MOD",      "BTN_5": "FX",        "BTN_6": "Solo"
    },
    "PRESET": {
        "BTN_1": "CLEAN_PRESET", "BTN_2": "LEAD_PRESET",
    }
}

DEFAULT_PRESETS = {
    "CLEAN_PRESET": {
        "Amp Type": "CLEAN", "Boost": "OFF", "MOD": "OFF",
        "FX": "OFF", "Delay": "OFF", "Reverb": "GREEN", "Solo": "OFF"
    },
    "LEAD_PRESET": {
        "Amp Type": "BROWN", "Boost": "RED", "MOD": "GREEN", "Solo": "ON"
    }
}

GPIO_CONFIG = {}
MODE_MAPPINGS = {}
PRESETS = {}

def load_config():
    global GPIO_CONFIG, MODE_MAPPINGS, PRESETS
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                GPIO_CONFIG = data.get("GPIO_CONFIG", DEFAULT_GPIO_CONFIG)
                MODE_MAPPINGS = data.get("MODE_MAPPINGS", DEFAULT_MODE_MAPPINGS)
                PRESETS = data.get("PRESETS", DEFAULT_PRESETS)
                if PRINT_DEBUG: print(f"[DEBUG] Config loaded from {CONFIG_FILE}")
                return
        except: pass
    GPIO_CONFIG, MODE_MAPPINGS, PRESETS = DEFAULT_GPIO_CONFIG, DEFAULT_MODE_MAPPINGS, DEFAULT_PRESETS
    if PRINT_DEBUG: print("[DEBUG] Defaults loaded")

def save_config():
    try:
        data = {"GPIO_CONFIG": GPIO_CONFIG, "MODE_MAPPINGS": MODE_MAPPINGS, "PRESETS": PRESETS}
        with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)
        if PRINT_DEBUG: print(f"[DEBUG] Config saved to {CONFIG_FILE}")
    except: pass

# --- COMMAND LINE ARGUMENTS ---
PRINT_LATENCY = "-t" in sys.argv
PRINT_DEBUG = "-d" in sys.argv # Generic debug switch for state and operations
ENABLE_WEB = "-w" in sys.argv 
MODE_SWITCH_PIN = 4 
PRESET_EDIT_PIN = 17 

# --- AMP SETTINGS ---
SETTINGS = {
    "Amp Type":  {"addr": [0x20, 0x00, 0x06, 0x07], "vals": ["ACOUS", "CLEAN", "PUSH", "CRNCH", "LEAD", "BROWN"], "cat": "AMP"},
    "Variation": {"addr": [0x20, 0x00, 0x06, 0x09], "vals": ["OFF", "ON"], "cat": "AMP"},
    "Bloom":     {"addr": [0x20, 0x00, 0x06, 0x06], "vals": ["OFF", "ON"], "cat": "AMP"},
    "Boost":     {"addr": [0x20, 0x00, 0x04, 0x00], "sw_addr": [0x20, 0x00, 0x03, 0x00], "vals": ["GREEN", "RED", "YELLOW"], "cat": "DRIVE"},
    "MOD":        {"addr": [0x20, 0x00, 0x04, 0x01], "sw_addr": [0x20, 0x00, 0x03, 0x01], "vals": ["GREEN", "RED", "YELLOW"], "cat": "MOD"},
    "FX":         {"addr": [0x20, 0x00, 0x04, 0x02], "sw_addr": [0x20, 0x00, 0x03, 0x02], "vals": ["GREEN", "RED", "YELLOW"], "cat": "FX"},
    "Delay":      {"addr": [0x20, 0x00, 0x04, 0x03], "sw_addr": [0x20, 0x00, 0x03, 0x03], "vals": ["GREEN", "RED", "YELLOW"], "cat": "DLY"},
    "Reverb":     {"addr": [0x20, 0x00, 0x04, 0x04], "sw_addr": [0x20, 0x00, 0x03, 0x04], "vals": ["GREEN", "RED", "YELLOW"], "cat": "RVB"},
    "Solo":       {"addr": [0x20, 0x00, 0x3A, 0x00], "vals": ["OFF", "ON"], "cat": "DRIVE"},
    "Contour":    {"addr": [0x20, 0x00, 0x40, 0x00], "vals": ["OFF", "GRN", "RED", "YEL"], "cat": "UTIL"},
    "Cab Res":    {"addr": [0x20, 0x00, 0x02, 0x01], "vals": ["VINT", "MODRN", "DEEP"], "cat": "UTIL"},
}
HIDDEN_FROM_LCD = ["Solo", "Contour", "Cab Res"]
CAT_COLORS = {"AMP": "#FF4500", "DRIVE": "#FF0000", "MOD": "#0000FF", "FX": "#FFA500", "DLY": "#008000", "RVB": "#228B22", "UTIL": "#444444"}
STATE_COLORS = {"GREEN": "#00FF00", "GRN": "#00FF00", "RED": "#FF0000", "YELLOW": "#FFFF00", "YEL": "#FFFF00", "ON": "#00FF00", "OFF": "#222222"}
LABEL_BG_COLOR = "#0a024d"

class KatanaHandler:
    def __init__(self, on_change_callback):
        self.on_change = on_change_callback
        self.current_vals = {key: 0 for key in SETTINGS}
        self.active_states = {key: True for key in SETTINGS} 
        self.app_status = "INIT"
        self.inport, self.outport = None, None
        self.msg_cache, self.pending_requests = {}, {}
        self.synced_count = 0

    def _calculate_checksum(self, data):
        return (128 - (sum(data) % 128)) % 128

    def _create_sysex_msg(self, cmd, addr, data_or_size):
        payload = [cmd] + addr + data_or_size
        chk = self._calculate_checksum(addr + data_or_size)
        return mido.Message('sysex', data=KATANA_HEADER + payload + [chk])

    def _prefill_cache(self):
        for key, cfg in SETTINGS.items():
            self.msg_cache[key] = [self._create_sysex_msg(CMD_DT1, cfg["addr"], [i]) for i in range(len(cfg["vals"]))]

    def connect(self, start_time_ref):
        while True:
            try:
                out_names = mido.get_output_names()
                in_names = mido.get_input_names()
                k_out = [n for n in out_names if "KATANA" in n.upper()]
                k_in = [n for n in in_names if "KATANA" in n.upper()]
                if k_out and k_in:
                    self.outport = mido.open_output(k_out[0])
                    self.inport = mido.open_input(k_in[0])
                    if PRINT_DEBUG: print(f"[DEBUG] Connected to {k_out[0]}")
                    self.app_status = "SYNC"
                    self._prefill_cache()
                    self.on_change()
                    break
            except:
                if time.time() - start_time_ref >= 5.0:
                    self.app_status = "NO_USB"
                    self.on_change()
                time.sleep(0.5)
        
        threading.Thread(target=self._midi_worker, daemon=True).start()
        self.on_change()

    def _midi_worker(self):
        while True:
            try:
                for msg in self.inport.iter_pending():
                    if msg.type == 'sysex' and len(msg.data) >= 11:
                        addr_recv = list(msg.data[6:10])
                        val_recv, addr_str = msg.data[10], str(list(msg.data[6:10]))
                        is_initial_sync = (self.app_status == "SYNC")
                        if addr_str in self.pending_requests:
                            self.pending_requests.pop(addr_str)
                            if is_initial_sync: self.synced_count += 1
                        
                        changed = False
                        for key, cfg in SETTINGS.items():
                            if cfg["addr"] == addr_recv:
                                if self.current_vals[key] != val_recv: 
                                    self.current_vals[key] = val_recv
                                    changed = True
                                    if PRINT_DEBUG: print(f"[DEBUG] MIDI RX: {key} = {cfg['vals'][val_recv]}")
                            elif "sw_addr" in cfg and cfg["sw_addr"] == addr_recv:
                                new_state = (val_recv == 0x01)
                                if self.active_states[key] != new_state: 
                                    self.active_states[key] = new_state
                                    changed = True
                                    if PRINT_DEBUG: print(f"[DEBUG] MIDI RX: {key} {'ENABLED' if new_state else 'DISABLED'}")
                        
                        total_expected = sum(2 if "sw_addr" in cfg else 1 for cfg in SETTINGS.values())
                        if is_initial_sync and self.synced_count >= total_expected:
                            if PRINT_DEBUG: print("[DEBUG] Initial Sync Complete")
                            self.app_status = "OK"
                            changed = True
                        if changed: self.on_change()
                time.sleep(0.01)
            except: break

    def send_request(self, addr, size=[0x00, 0x00, 0x00, 0x01]):
        if self.outport:
            self.pending_requests[str(addr)] = time.time()
            self.outport.send(self._create_sysex_msg(CMD_RQ1, addr, size))

    def cycle_effect(self, key):
        if self.app_status != "OK" or not self.outport: return
        self.current_vals[key] = (self.current_vals[key] + 1) % len(SETTINGS[key]["vals"])
        if PRINT_DEBUG: print(f"[DEBUG] OP: Cycle {key} -> {SETTINGS[key]['vals'][self.current_vals[key]]}")
        self.outport.send(self.msg_cache[key][self.current_vals[key]])
        if not self.active_states[key] and "sw_addr" in SETTINGS[key]:
            self.active_states[key] = True
            self.outport.send(self._create_sysex_msg(CMD_DT1, SETTINGS[key]["sw_addr"], [0x01]))
        self.on_change()

    def toggle_effect(self, key):
        if self.app_status != "OK" or not self.outport or "sw_addr" not in SETTINGS[key]: return 
        self.active_states[key] = not self.active_states[key]
        if PRINT_DEBUG: print(f"[DEBUG] OP: Toggle {key} {'ON' if self.active_states[key] else 'OFF'}")
        val = 0x01 if self.active_states[key] else 0x00
        self.outport.send(self._create_sysex_msg(CMD_DT1, SETTINGS[key]["sw_addr"], [val]))
        self.on_change()

    def apply_preset(self, preset_name):
        if self.app_status != "OK" or not self.outport: return
        if PRINT_DEBUG: print(f"[DEBUG] OP: Applying Preset '{preset_name}'")
        data = PRESETS.get(preset_name, {})
        for key, target in data.items():
            if key not in SETTINGS: continue
            cfg = SETTINGS[key]
            if target == "OFF" and "sw_addr" in cfg:
                if self.active_states[key]:
                    self.active_states[key] = False
                    self.outport.send(self._create_sysex_msg(CMD_DT1, cfg["sw_addr"], [0x00]))
                    time.sleep(0.015)
            elif target in cfg["vals"]:
                target_idx = cfg["vals"].index(target)
                if "sw_addr" in cfg and not self.active_states[key]:
                    self.active_states[key] = True
                    self.outport.send(self._create_sysex_msg(CMD_DT1, cfg["sw_addr"], [0x01]))
                    time.sleep(0.015)
                if self.current_vals[key] != target_idx:
                    self.current_vals[key] = target_idx
                    self.outport.send(self.msg_cache[key][target_idx])
                    time.sleep(0.015)
        self.on_change()

class LCDHandler:
    def __init__(self):
        try:
            from luma.core.interface.serial import spi
            from luma.lcd.device import ili9341
            self.serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24, gpio_CS=8)
            self.device = ili9341(self.serial, width=320, height=240, mode='RGB', rotate=0)
        except: self.device = None
        self.label_font, self.value_font, self.status_font, self.mode_font = None, None, None, None
        self._splash_cleared = False

    def _load_fonts(self):
        if self.label_font: return
        try:
            from PIL import ImageFont
            self.label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            self.value_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.status_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            self.mode_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except: pass

    def update(self, app_status, current_mode, edit_mode, current_vals, active_states, start_time):
        if not self.device: return
        
        # Use a lock to prevent concurrent SPI access which causes corruption
        with lcd_lock:
            showing_splash = time.time() - start_time < 5.0 or app_status in ["INIT", "SYNC"]
            if showing_splash and app_status != "NO_USB":
                try:
                    from PIL import Image
                    if os.path.exists("splash.bmp"):
                        splash = Image.open("splash.bmp").convert("RGB")
                        if splash.size != (self.device.width, self.device.height):
                            splash = splash.resize((self.device.width, self.device.height))
                        self.device.display(splash)
                        return
                except: pass
            
            # Explicitly clear the device once when transitioning from splash
            if not showing_splash and not self._splash_cleared:
                self.device.clear()
                self._splash_cleared = True

            self._load_fonts()
            from luma.core.render import canvas
            with canvas(self.device) as draw:
                screen_w, screen_h = self.device.width, self.device.height
                if edit_mode:
                    draw.rectangle([0, 0, screen_w, screen_h], fill="red")
                    draw.text((30, 60), "EDIT MODE", fill="white", font=self.status_font)
                    return
                if app_status in ["INIT", "SYNC", "NO_USB"]:
                    msg = "CONNECTING" if app_status == "INIT" else "SYNCING" if app_status == "SYNC" else "NO USB"
                    draw.text((screen_w // 2 - 80, screen_h // 2 - 20), msg, fill="yellow", font=self.status_font)
                    return
                row0_h, slot_h, slot_w, label_h = 60, (screen_h - 60) // 2, screen_w // 4, 24
                draw.rectangle([0, 0, screen_w, row0_h], fill="#111111", outline="#333333")
                draw.text((10, 5), f"MODE: {current_mode}", fill="cyan" if current_mode == "DIRECT" else "magenta", font=self.label_font)
                draw.text((10, 30), app_status if current_mode != "PRESET" else "SELECT PRESET", fill="green", font=self.mode_font)
                display_keys = [k for k in SETTINGS.keys() if k not in HIDDEN_FROM_LCD]
                for i in range(min(8, len(display_keys))):
                    col, row = i % 4, i // 4
                    x, y = col * slot_w, row0_h + (row * slot_h)
                    key = display_keys[i]
                    is_active = active_states.get(key, True)
                    val_text = SETTINGS[key]["vals"][current_vals[key]] if is_active else "OFF"
                    fill = STATE_COLORS.get(val_text, CAT_COLORS.get(SETTINGS[key]["cat"], "#444444")) if is_active else STATE_COLORS["OFF"]
                    draw.rectangle([x, y, x+slot_w-2, y+label_h], outline="#333", fill=LABEL_BG_COLOR)
                    draw.rectangle([x, y+label_h, x+slot_w-2, y+slot_h-2], outline="#333", fill=fill)
                    draw.text((x+4, y+3), key.upper()[:7], fill="white", font=self.mode_font)
                    draw.text((x+6, y+label_h+12), val_text[:6], fill="white", font=self.label_font)

class WebHandler:
    def __init__(self, state_getter, toggle_mode_fn, toggle_edit_fn, save_preset_fn, control_btn_fn):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self._get_state, self._toggle_mode, self._toggle_edit = state_getter, toggle_mode_fn, toggle_edit_fn
        self._save_preset, self._control_btn = save_preset_fn, control_btn_fn
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/')
        def index(): return render_template('index.html', cat_colors=CAT_COLORS, state_colors=STATE_COLORS, hidden=HIDDEN_FROM_LCD)
        @self.socketio.on('connect')
        def handle_connect(): emit('state_update', self._get_state())
        @self.socketio.on('toggle_mode')
        def handle_toggle_mode(): self._toggle_mode()
        @self.socketio.on('toggle_edit')
        def handle_toggle_edit(): self._toggle_edit()
        @self.socketio.on('save_to_slot')
        def handle_save_to_slot(data): self._save_preset(data.get('btn_id'))
        @self.socketio.on('control_by_btn')
        def handle_control_by_btn(data): self._control_btn(data.get('btn_id'), data.get('action'))

    def push_state(self): self.socketio.emit('state_update', self._get_state())
    def run(self, host='0.0.0.0', port=5000): self.socketio.run(self.app, host=host, port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

def on_katana_change(): update_ui_all()
katana = KatanaHandler(on_change_callback=on_katana_change)
lcd = LCDHandler()

def get_full_state_dict():
    settings_data = {k: SETTINGS[k]["vals"][katana.current_vals[k]] for k in SETTINGS}
    return {"settings": settings_data, "active": katana.active_states, "cats": {k: SETTINGS[k]["cat"] for k in SETTINGS}, "mode": current_mode, "edit_mode": edit_mode, "status": katana.app_status, "mapped": MODE_MAPPINGS[current_mode], "hidden": HIDDEN_FROM_LCD}

def handle_web_control(btn_id, action):
    if edit_mode: return
    target = MODE_MAPPINGS[current_mode].get(btn_id)
    if not target: return
    if current_mode == "PRESET": katana.apply_preset(target)
    else: katana.toggle_effect(target) if action == 'toggle' else katana.cycle_effect(target)

def update_ui_all():
    lcd.update(katana.app_status, current_mode, edit_mode, katana.current_vals, katana.active_states, start_time)
    if ENABLE_WEB: web_server.push_state()

def refresh_worker():
    while True:
        if katana.app_status in ["SYNC", "OK"] and katana.outport:
            for key, cfg in SETTINGS.items():
                while time.time() - last_interaction_time < 2.0: time.sleep(0.5)
                try:
                    katana.send_request(cfg["addr"]); time.sleep(0.06)
                    if "sw_addr" in cfg: katana.send_request(cfg["sw_addr"]); time.sleep(0.06)
                except: pass
        time.sleep(10.0) 

def toggle_global_mode():
    global current_mode
    if edit_mode: return 
    current_mode = "PRESET" if current_mode == "DIRECT" else "DIRECT"
    if PRINT_DEBUG: print(f"[DEBUG] UI: Switched Mode to {current_mode}")
    update_ui_all()

def toggle_preset_edit():
    global edit_mode
    edit_mode = not edit_mode
    if PRINT_DEBUG: print(f"[DEBUG] UI: Edit Mode {'ENABLED' if edit_mode else 'DISABLED'}")
    update_ui_all()

def save_preset_to_button(btn_id):
    global edit_mode
    name = MODE_MAPPINGS["PRESET"].get(btn_id) or f"PRESET_{btn_id}"
    MODE_MAPPINGS["PRESET"][btn_id] = name
    PRESETS[name] = {k: ("OFF" if not katana.active_states.get(k, True) else SETTINGS[k]["vals"][katana.current_vals[k]]) for k in SETTINGS}
    edit_mode = False
    if PRINT_DEBUG: print(f"[DEBUG] OP: Saved Preset '{name}' to {btn_id}")
    save_config()
    update_ui_all()

class ButtonHandler:
    def __init__(self, btn_id, pin):
        self.btn_id, self.pin, self.was_held = btn_id, pin, False
        self.btn = Button(pin, pull_up=True, bounce_time=0.03, hold_time=0.6)
        self.btn.when_released = self.handle_release
        self.btn.when_held = self.handle_hold

    def handle_hold(self):
        global last_interaction_time
        last_interaction_time, self.was_held = time.time(), True
        if PRINT_DEBUG: print(f"[DEBUG] INPUT: HELD {self.btn_id} (Pin: {self.pin})")
        if not edit_mode and current_mode == "DIRECT":
            target = MODE_MAPPINGS["DIRECT"].get(self.btn_id)
            if target in SETTINGS: katana.toggle_effect(target)

    def handle_release(self):
        global last_interaction_time
        if not self.was_held:
            last_interaction_time = time.time()
            if PRINT_DEBUG: print(f"[DEBUG] INPUT: RELEASED {self.btn_id} (Pin: {self.pin})")
            if edit_mode: save_preset_to_button(self.btn_id); return
            target = MODE_MAPPINGS[current_mode].get(self.btn_id)
            if target:
                if current_mode == "PRESET" and target in PRESETS: katana.apply_preset(target)
                elif current_mode == "DIRECT" and target in SETTINGS: katana.cycle_effect(target)
        self.was_held = False

if __name__ == "__main__":
    if PRINT_DEBUG: print("[DEBUG] Starting Katana Controller")
    
    # 1. Start LCD Tick immediately to show splash
    threading.Thread(target=lambda: (None, [update_ui_all() or time.sleep(0.5) for _ in iter(int, 1)]), daemon=True).start()
    
    # 2. Start Katana connection immediately (heavy modules imported inside class if needed)
    # We trigger the heavy delayed_init in a background thread so it doesn't block the loop
    def background_init():
        delayed_init()
        threading.Thread(target=refresh_worker, daemon=True).start()
        if ENABLE_WEB: web_server.run()

    # We need mido for the connect loop, so delayed_init actually needs to happen 
    # just before or during connect. Let's run it now.
    threading.Thread(target=background_init, daemon=True).start()
    
    # Wait for mido to be available from delayed_init
    while 'mido' not in globals(): time.sleep(0.1)
    
    # 3. Start Katana connection
    katana.connect(start_time)

    # Keep main thread alive
    while True: time.sleep(1)
