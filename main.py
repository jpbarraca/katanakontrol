from __future__ import annotations
import time
import threading
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING

# These are used for type hinting when the actual modules aren't loaded yet
if TYPE_CHECKING:
    import mido
    from flask import Flask
    from flask_socketio import SocketIO
    from luma.lcd.device import ili9341
    from PIL.ImageFont import FreeTypeFont

# --- HELP / USAGE INFORMATION ---
def print_usage() -> None:
    """Prints the command-line help menu and exits the program."""
    print("""
Boss Katana MIDI Controller
Usage: python3 katana_controller.py [options]

Options:
  -h, --help     Show this help message and exit
  -d             Enable debug mode (logs state, operations, and inputs)
  -w             Enable the web interface on port 5000
  -t             Print MIDI latency timing information
    """)
    sys.exit(0)

# Check for help flag before anything else starts
if "-h" in sys.argv or "--help" in sys.argv:
    print_usage()

# --- MINIMAL STARTUP CONSTANTS ---
KATANA_HEADER: List[int] = [0x41, 0x10, 0x01, 0x05, 0x07]
CMD_DT1: int = 0x12  # Data set command
CMD_RQ1: int = 0x11  # Request data command
CONFIG_FILE: str = "config.json"

# --- GLOBAL STATE ---
current_mode: str = "DIRECT"
edit_mode: bool = False
last_interaction_time: float = 0.0
start_time: float = time.time()
handlers: List[ButtonHandler] = []
lcd_lock: threading.Lock = threading.Lock() 

# --- DELAYED IMPORTS & LOGIC WRAPPER ---
def delayed_init() -> None:
    global mido, json, Button, Flask, SocketIO, emit, spi, ili9341, canvas, Image, ImageDraw, ImageFont
    global GPIO_CONFIG, MODE_MAPPINGS, PRESETS, LCD_ORDER, web_server

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

    global handlers, mode_btn, edit_btn
    handlers = [ButtonHandler(btn_id, pin) for btn_id, pin in GPIO_CONFIG.items()]

    mode_btn = Button(MODE_SWITCH_PIN, pull_up=True, bounce_time=0.05)
    mode_btn.when_pressed = lambda: toggle_global_mode()

    edit_btn = Button(PRESET_EDIT_PIN, pull_up=True, bounce_time=0.05)
    edit_btn.when_pressed = lambda: toggle_preset_edit()

    web_server = WebHandler(
        state_getter=get_full_state_dict,
        toggle_mode_fn=toggle_global_mode,
        toggle_edit_fn=toggle_preset_edit,
        save_preset_fn=save_preset_to_button,
        control_btn_fn=handle_web_control,
        update_map_fn=update_switch_mapping,
        update_preset_fn=update_preset_content # New functionality
    )

# --- CONFIGURATION PERSISTENCE ---
DEFAULT_GPIO_CONFIG: Dict[str, int] = {
    "BTN_1": 13, "BTN_2": 5, "BTN_3": 12,
    "BTN_4": 19, "BTN_5": 6, "BTN_6": 26,
    "BTN_7": 16, "BTN_8": 21, "BTN_9": 20
}

DEFAULT_MODE_MAPPINGS: Dict[str, Dict[str, str]] = {
    "DIRECT": {
        "BTN_1": "Amp", "BTN_2": "Var", "BTN_3": "Boost",
        "BTN_4": "MOD",      "BTN_5": "FX",        "BTN_6": "Solo"
    },
    "PRESET": {
        "BTN_1": "CLEAN_PRESET", "BTN_2": "LEAD_PRESET",
    }
}

DEFAULT_PRESETS: Dict[str, Dict[str, str]] = {
    "CLEAN_PRESET": {
        "Amp": "CLEAN", "Boost": "OFF", "MOD": "OFF",
        "FX": "OFF", "Delay": "OFF", "Revrb": "GREEN", "Solo": "OFF"
    },
    "LEAD_PRESET": {
        "Amp": "BROWN", "Boost": "RED", "MOD": "GREEN", "Solo": "ON"
    }
}

DEFAULT_LCD_ORDER: List[str] = ["Amp", "Var", "Delay", "Revrb", "MOD", "FX", "Boost", "Bloom"]

GPIO_CONFIG: Dict[str, int] = {}
MODE_MAPPINGS: Dict[str, Dict[str, str]] = {}
PRESETS: Dict[str, Dict[str, str]] = {}
LCD_ORDER: List[str] = []

def load_config() -> None:
    global GPIO_CONFIG, MODE_MAPPINGS, PRESETS, LCD_ORDER
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                GPIO_CONFIG = data.get("GPIO_CONFIG", DEFAULT_GPIO_CONFIG)
                MODE_MAPPINGS = data.get("MODE_MAPPINGS", DEFAULT_MODE_MAPPINGS)
                PRESETS = data.get("PRESETS", DEFAULT_PRESETS)
                LCD_ORDER = data.get("LCD_ORDER", DEFAULT_LCD_ORDER)
                return
        except Exception: pass
    GPIO_CONFIG, MODE_MAPPINGS, PRESETS, LCD_ORDER = DEFAULT_GPIO_CONFIG, DEFAULT_MODE_MAPPINGS, DEFAULT_PRESETS, DEFAULT_LCD_ORDER

def save_config() -> None:
    try:
        data = {
            "GPIO_CONFIG": GPIO_CONFIG, 
            "MODE_MAPPINGS": MODE_MAPPINGS, 
            "PRESETS": PRESETS,
            "LCD_ORDER": LCD_ORDER
        }
        with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)
    except Exception: pass

PRINT_LATENCY: bool = "-t" in sys.argv
PRINT_DEBUG: bool = "-d" in sys.argv 
ENABLE_WEB: bool = "-w" in sys.argv
MODE_SWITCH_PIN: int = 4
PRESET_EDIT_PIN: int = 17

# --- AMP SETTINGS ---
SETTINGS: Dict[str, Dict[str, Any]] = {
    "Amp":  {"addr": [0x20, 0x00, 0x06, 0x07], "vals": ["ACOUS", "CLEAN", "PUSH", "CRNCH", "LEAD", "BROWN"], "cat": "AMP"},
    "Var":  {"addr": [0x20, 0x00, 0x06, 0x09], "vals": ["OFF", "ON"], "cat": "AMP"},
    "Bloom":     {"addr": [0x20, 0x00, 0x06, 0x06], "vals": ["OFF", "ON"], "cat": "AMP"},
    "Boost":     {"addr": [0x20, 0x00, 0x04, 0x00], "sw_addr": [0x20, 0x00, 0x03, 0x00], "vals": ["GREEN", "RED", "YELLOW"], "cat": "DRIVE"},
    "MOD":        {"addr": [0x20, 0x00, 0x04, 0x01], "sw_addr": [0x20, 0x00, 0x03, 0x01], "vals": ["GREEN", "RED", "YELLOW"], "cat": "MOD"},
    "FX":         {"addr": [0x20, 0x00, 0x04, 0x02], "sw_addr": [0x20, 0x00, 0x03, 0x02], "vals": ["GREEN", "RED", "YELLOW"], "cat": "FX"},
    "Delay":      {"addr": [0x20, 0x00, 0x04, 0x03], "sw_addr": [0x20, 0x00, 0x03, 0x03], "vals": ["GREEN", "RED", "YELLOW"], "cat": "DLY"},
    "Revrb":     {"addr": [0x20, 0x00, 0x04, 0x04], "sw_addr": [0x20, 0x00, 0x03, 0x04], "vals": ["GREEN", "RED", "YELLOW"], "cat": "RVB"},
    "Solo":       {"addr": [0x20, 0x00, 0x3A, 0x00], "vals": ["OFF", "ON"], "cat": "DRIVE"},
    "Contr":    {"addr": [0x20, 0x00, 0x40, 0x00], "vals": ["OFF", "GREEN", "RED", "YELLOW"], "cat": "UTIL"},
    "Cab":    {"addr": [0x20, 0x00, 0x02, 0x01], "vals": ["VINT", "MODRN", "DEEP"], "cat": "UTIL"},
}
HIDDEN_FROM_LCD: List[str] = ["Solo", "Contr", "Cab"]
CAT_COLORS: Dict[str, str] = {"AMP": "#FF4500", "DRIVE": "#FF0000", "MOD": "#0000FF", "FX": "#FFA500", "DLY": "#008000", "RVB": "#228B22", "UTIL": "#444444"}
STATE_COLORS: Dict[str, str] = {"GREEN": "#00FF00", "GRN": "#00FF00", "RED": "#FF0000", "YELLOW": "#FFFF00", "YEL": "#FFFF00", "ON": "#00FF00", "OFF": "#222222"}
LABEL_BG_COLOR: str = "#0a024d"

class KatanaHandler:
    def __init__(self, on_change_callback: Callable[[], None]) -> None:
        self.on_change = on_change_callback
        self.current_vals: Dict[str, int] = {key: 0 for key in SETTINGS}
        self.active_states: Dict[str, bool] = {key: True for key in SETTINGS}
        self.app_status: str = "INIT"
        self.inport: Optional[mido.ports.BaseInput] = None
        self.outport: Optional[mido.ports.BaseOutput] = None
        self.msg_cache: Dict[str, List[mido.Message]] = {}
        self.pending_requests: Dict[str, float] = {}
        self.synced_count: int = 0

    def _calculate_checksum(self, data: List[int]) -> int:
        return (128 - (sum(data) % 128)) % 128

    def _create_sysex_msg(self, cmd: int, addr: List[int], data_or_size: List[int]) -> mido.Message:
        payload = [cmd] + addr + data_or_size
        chk = self._calculate_checksum(addr + data_or_size)
        return mido.Message('sysex', data=KATANA_HEADER + payload + [chk])

    def _prefill_cache(self) -> None:
        for key, cfg in SETTINGS.items():
            self.msg_cache[key] = [self._create_sysex_msg(CMD_DT1, cfg["addr"], [i]) for i in range(len(cfg["vals"]))]

    def connect(self, start_time_ref: float) -> None:
        while True:
            try:
                out_names = mido.get_output_names()
                in_names = mido.get_input_names()
                k_out = [n for n in out_names if "KATANA" in n.upper()]
                k_in = [n for n in in_names if "KATANA" in n.upper()]
                if k_out and k_in:
                    self.outport = mido.open_output(k_out[0])
                    self.inport = mido.open_input(k_in[0])
                    self.app_status = "SYNC"
                    self._prefill_cache()
                    self.on_change()
                    break
            except Exception:
                if time.time() - start_time_ref >= 5.0:
                    self.app_status = "NO_USB"
                    self.on_change()
                time.sleep(0.5)
        threading.Thread(target=self._midi_worker, daemon=True).start()
        self.on_change()

    def _midi_worker(self) -> None:
        while True:
            try:
                if self.inport:
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
                                elif "sw_addr" in cfg and cfg["sw_addr"] == addr_recv:
                                    new_state = (val_recv == 0x01)
                                    if self.active_states[key] != new_state:
                                        self.active_states[key] = new_state
                                        changed = True
                            total_expected = sum(2 if "sw_addr" in cfg else 1 for cfg in SETTINGS.values())
                            if is_initial_sync and self.synced_count >= total_expected:
                                self.app_status = "OK"
                                changed = True
                            if changed: self.on_change()
                time.sleep(0.01)
            except Exception: break

    def send_request(self, addr: List[int], size: List[int] = [0x00, 0x00, 0x00, 0x01]) -> None:
        if self.outport:
            self.pending_requests[str(addr)] = time.time()
            self.outport.send(self._create_sysex_msg(CMD_RQ1, addr, size))

    def cycle_effect(self, key: str) -> None:
        if self.app_status != "OK" or not self.outport or key not in SETTINGS: return
        self.current_vals[key] = (self.current_vals[key] + 1) % len(SETTINGS[key]["vals"])
        self.outport.send(self.msg_cache[key][self.current_vals[key]])
        if not self.active_states[key] and "sw_addr" in SETTINGS[key]:
            self.active_states[key] = True
            self.outport.send(self._create_sysex_msg(CMD_DT1, SETTINGS[key]["sw_addr"], [0x01]))
        self.on_change()

    def toggle_effect(self, key: str) -> None:
        if self.app_status != "OK" or not self.outport or key not in SETTINGS or "sw_addr" not in SETTINGS[key]: return
        self.active_states[key] = not self.active_states[key]
        val = 0x01 if self.active_states[key] else 0x00
        self.outport.send(self._create_sysex_msg(CMD_DT1, SETTINGS[key]["sw_addr"], [val]))
        self.on_change()

    def apply_preset(self, preset_name: str) -> None:
        if self.app_status != "OK" or not self.outport: return
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
    def __init__(self) -> None:
        self.device: Optional[ili9341] = None
        try:
            from luma.core.interface.serial import spi
            from luma.lcd.device import ili9341
            self.serial = spi(port=0, device=0, gpio_DC=23, gpio_RST=24, gpio_CS=8)
            self.device = ili9341(self.serial, width=320, height=240, mode='RGB', rotate=0)
        except Exception: pass
        self.label_font = None
        self.value_font = None
        self.status_font = None
        self.mode_font = None
        self._splash_cleared = False

    def _get_font(self, size: int) -> FreeTypeFont:
        paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"]
        from PIL import ImageFont
        for path in paths:
            if os.path.exists(path):
                try: return ImageFont.truetype(path, size)
                except Exception: continue
        return ImageFont.load_default()

    def _load_fonts(self) -> None:
        if self.label_font: return
        self.label_font = self._get_font(14)
        self.value_font = self._get_font(16)
        self.status_font = self._get_font(16)
        self.mode_font = self._get_font(18)

    def update(self, app_status: str, current_mode: str, edit_mode: bool, current_vals: Dict[str, int], active_states: Dict[str, bool], start_time: float) -> None:
        if not self.device: return
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
                except Exception: pass

            if not showing_splash and not self._splash_cleared:
                self.device.clear()
                self._splash_cleared = True

            self._load_fonts()
            from luma.core.render import canvas
            with canvas(self.device) as draw:
                screen_w, screen_h = self.device.width, self.device.height
                if edit_mode:
                    draw.rectangle([0, 0, screen_w, screen_h], fill="red")
                    if self.status_font: draw.text((20, 80), "EDIT MODE", fill="white", font=self.status_font)
                    return
                if app_status in ["INIT", "SYNC", "NO_USB"]:
                    msg = "CONNECTING" if app_status == "INIT" else "SYNCING" if app_status == "SYNC" else "NO USB"
                    if self.status_font: draw.text((screen_w // 2 - 130, screen_h // 2 - 35), msg, fill="yellow", font=self.status_font)
                    return

                row0_h, slot_h, slot_w, label_h = 60, (screen_h - 60) // 2, screen_w // 4, 25
                draw.rectangle([0, 0, screen_w, row0_h], fill="#111111", outline="#333333")
                if self.label_font and self.mode_font:
                    draw.text((10, 5), f"MODE: {current_mode}", fill="cyan" if current_mode == "DIRECT" else "magenta", font=self.label_font)
                    draw.text((12, 35), app_status if current_mode != "PRESET" else "SELECT PRESET", fill="green", font=self.mode_font)

                order_to_use = LCD_ORDER if len(LCD_ORDER) >= 8 else DEFAULT_LCD_ORDER
                for i in range(min(8, len(order_to_use))):
                    col, row = i % 4, i // 4
                    x, y = col * slot_w, row0_h + (row * slot_h)
                    key = order_to_use[i]
                    if key not in SETTINGS: continue
                    is_active = active_states.get(key, True)
                    val_text = SETTINGS[key]["vals"][current_vals[key]] if is_active else "OFF"
                    if key == "Amp": fill, text_color = "#111111", "white"
                    else:
                        text_color = "black" if val_text.upper() in ["GREEN", "YELLOW", "RED", "GRN", "YEL"] else "white"
                        fill = STATE_COLORS.get(val_text, CAT_COLORS.get(SETTINGS[key]["cat"], "#444444")) if is_active else STATE_COLORS["OFF"]

                    draw.rectangle([x, y, x+slot_w-2, y+label_h], outline="#333", fill=LABEL_BG_COLOR)
                    draw.rectangle([x, y+label_h, x+slot_w-2, y+slot_h-2], outline="#333", fill=fill)

                    if self.mode_font:
                        draw.text((x+4, y+2), key.upper()[:7], fill="white", font=self.mode_font)
                        if key == "Amp" and self.value_font:
                            draw.text((x+6, y+label_h+2), val_text[:6], fill=text_color, font=self.value_font)

class WebHandler:
    def __init__(self, state_getter, toggle_mode_fn, toggle_edit_fn, save_preset_fn, control_btn_fn, update_map_fn, update_preset_fn) -> None:
        self.app: Flask = Flask(__name__)
        self.socketio: SocketIO = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self._get_state, self._toggle_mode, self._toggle_edit = state_getter, toggle_mode_fn, toggle_edit_fn
        self._save_preset, self._control_btn, self._update_map, self._update_preset = save_preset_fn, control_btn_fn, update_map_fn, update_preset_fn
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.route('/')
        def index() -> str: return render_template('index.html', cat_colors=CAT_COLORS, state_colors=STATE_COLORS, hidden=HIDDEN_FROM_LCD)
        @self.socketio.on('connect')
        def handle_connect() -> None: emit('state_update', self._get_state())
        @self.socketio.on('toggle_mode')
        def handle_toggle_mode() -> None: self._toggle_mode()
        @self.socketio.on('toggle_edit')
        def handle_toggle_edit() -> None: self._toggle_edit()
        @self.socketio.on('save_to_slot')
        def handle_save_to_slot(data: Dict[str, Any]) -> None: self._save_preset(data.get('btn_id', ""))
        @self.socketio.on('control_by_btn')
        def handle_control_by_btn(data: Dict[str, Any]) -> None: self._control_btn(data.get('btn_id', ""), data.get('action', ""))
        @self.socketio.on('update_mapping')
        def handle_update_mapping(data: Dict[str, Any]) -> None: self._update_map(data.get('mode'), data.get('btn_id'), data.get('target'))
        @self.socketio.on('update_preset')
        def handle_update_preset(data: Dict[str, Any]) -> None: self._update_preset(data.get('preset_name'), data.get('settings'))

    def push_state(self) -> None:
        self.socketio.emit('state_update', self._get_state())
        
    def run(self, host: str = '0.0.0.0', port: int = 5000) -> None:
        self.socketio.run(self.app, host=host, port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

def on_katana_change() -> None: update_ui_all()
katana: KatanaHandler = KatanaHandler(on_change_callback=on_katana_change)
lcd: LCDHandler = LCDHandler()

def get_full_state_dict() -> Dict[str, Any]:
    settings_data = {k: SETTINGS[k]["vals"][katana.current_vals[k]] for k in SETTINGS}
    return {
        "settings": settings_data, 
        "active": katana.active_states, 
        "cats": {k: SETTINGS[k]["cat"] for k in SETTINGS}, 
        "mode": current_mode, 
        "edit_mode": edit_mode, 
        "status": katana.app_status, 
        "mapped": MODE_MAPPINGS[current_mode], 
        "hidden": HIDDEN_FROM_LCD,
        "presets": PRESETS, # Added
        "settings_meta": {k: ["OFF"] + SETTINGS[k]["vals"] if "sw_addr" in SETTINGS[k] else SETTINGS[k]["vals"] for k in SETTINGS} # Added
    }

def handle_web_control(btn_id: str, action: str) -> None:
    if edit_mode: return
    target = MODE_MAPPINGS[current_mode].get(btn_id)
    if not target: return
    if current_mode == "PRESET": katana.apply_preset(target)
    else: katana.toggle_effect(target) if action == 'toggle' else katana.cycle_effect(target)

def update_switch_mapping(mode: str, btn_id: str, target: str) -> None:
    if mode in MODE_MAPPINGS and btn_id in MODE_MAPPINGS[mode]:
        MODE_MAPPINGS[mode][btn_id] = target
        save_config()
        update_ui_all()

def update_preset_content(preset_name: str, settings: Dict[str, str]) -> None:
    """Updates specific settings within a preset and persists to config."""
    if preset_name in PRESETS:
        PRESETS[preset_name].update(settings)
        save_config()
        update_ui_all()

def update_ui_all() -> None:
    lcd.update(katana.app_status, current_mode, edit_mode, katana.current_vals, katana.active_states, start_time)
    if ENABLE_WEB: web_server.push_state()

def refresh_worker() -> None:
    while True:
        if katana.app_status in ["SYNC", "OK"] and katana.outport:
            for key, cfg in SETTINGS.items():
                while time.time() - last_interaction_time < 2.0: time.sleep(0.5)
                try:
                    katana.send_request(cfg["addr"]); time.sleep(0.06)
                    if "sw_addr" in cfg: katana.send_request(cfg["sw_addr"]); time.sleep(0.06)
                except Exception: pass
        time.sleep(10.0)

def toggle_global_mode() -> None:
    global current_mode
    if edit_mode: return
    current_mode = "PRESET" if current_mode == "DIRECT" else "DIRECT"
    update_ui_all()

def toggle_preset_edit() -> None:
    global edit_mode
    edit_mode = not edit_mode
    update_ui_all()

def save_preset_to_button(btn_id: str) -> None:
    global edit_mode
    name = MODE_MAPPINGS["PRESET"].get(btn_id) or f"PRESET_{btn_id}"
    MODE_MAPPINGS["PRESET"][btn_id] = name
    PRESETS[name] = {k: ("OFF" if not katana.active_states.get(k, True) else SETTINGS[k]["vals"][katana.current_vals[k]]) for k in SETTINGS}
    edit_mode = False
    save_config()
    update_ui_all()

class ButtonHandler:
    def __init__(self, btn_id: str, pin: int) -> None:
        self.btn_id, self.pin, self.was_held = btn_id, pin, False
        self.btn = Button(pin, pull_up=True, bounce_time=0.03, hold_time=0.6)
        self.btn.when_released = self.handle_release
        self.btn.when_held = self.handle_hold

    def handle_hold(self) -> None:
        global last_interaction_time
        last_interaction_time, self.was_held = time.time(), True
        if not edit_mode and current_mode == "DIRECT":
            target = MODE_MAPPINGS["DIRECT"].get(self.btn_id)
            if target in SETTINGS: katana.toggle_effect(target)

    def handle_release(self) -> None:
        global last_interaction_time
        if not self.was_held:
            last_interaction_time = time.time()
            if edit_mode:
                save_preset_to_button(self.btn_id)
                return
            target = MODE_MAPPINGS[current_mode].get(self.btn_id)
            if target:
                if current_mode == "PRESET" and target in PRESETS: katana.apply_preset(target)
                elif current_mode == "DIRECT" and target in SETTINGS: katana.cycle_effect(target)
        self.was_held = False

if __name__ == "__main__":
    threading.Thread(target=lambda: (None, [update_ui_all() or time.sleep(0.5) for _ in iter(int, 1)]), daemon=True).start()
    def background_init() -> None:
        delayed_init()
        threading.Thread(target=refresh_worker, daemon=True).start()
        if ENABLE_WEB: web_server.run()
    threading.Thread(target=background_init, daemon=True).start()
    while 'mido' not in globals(): time.sleep(0.1)
    katana.connect(start_time)
    while True: time.sleep(1)
