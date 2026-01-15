# 🎸 Boss Katana Gen 3 Virtual Footswitch

> **⚠️ DISCLAIMER: VIBE CODED HACK**
> This project was built through a process of "vibe coding". It is a glorious hack held together by high-level logic, real-time MIDI SysEx streams, and pure vibes. It works surprisingly well, but expect the soul of a machine in the code.

This is a custom-built footswitch and remote controller for the **Boss Katana Gen 3**. It transforms a Raspberry Pi into a dual-interface powerhouse: a physical stomp-box with an integrated LCD and a real-time WebSocket-powered web interface that mimics high-end guitar processors.

## ✨ Features

* **Bi-directional Sync:** Change a knob on the physical amp, and the LCD + Web UI update instantly.

* **Dual Modes:**

  * **Direct Control:** Stomp to toggle individual effects (Boost, Mod, FX, Delay, Reverb) or cycle types (Green/Red/Yellow).

  * **Preset Mode:** Apply entire "rig" configurations with a single tap.

* **On-the-Fly Editing:** Enter "Edit Mode" to save your current amp settings into a hardware button slot directly from the pedal.

* **Hybrid Interface:**

  * **Physical:** Support for SPI-driven ILI9341 LCDs and GPIO-mapped footswitches.

  * **Web:** A responsive, "stomp-box style" web dashboard using WebSockets for near-zero latency.

* **Smart Latency Control:** Background polling pauses during user interaction to give priority to your performance.

* **Config Persistence:** All button mappings and custom presets are saved to `config.json`.

## 🛠 Hardware Requirements

* **Raspberry Pi** (3, 4, or Zero 2W recommended)

* **Display:** ILI9341 320x240 SPI LCD

* **Controls:** Momentary footswitches connected to GPIO pins.

* **Connection:** USB cable to the Boss Katana "USB MIDI" port.

## 🚀 Quick Start

### 1. Installation

```
# Clone the repo
git clone [https://github.com/yourusername/katana-vibe-switch.git](https://github.com/yourusername/katana-vibe-switch.git)
cd katana-vibe-switch

# Install dependencies
pip install flask flask-socketio mido python-rtmidi luma.lcd gpiozero pillow

```

### 2. Configuration

Edit the top of `katana_footswitch.py` or modify the generated `config.json` to match your GPIO wiring:

```
GPIO_CONFIG = {
    "BTN_1": 5, "BTN_2": 6, "BTN_3": 13, # ... and so on
}

```

### 3. Run

```
# Basic run
python katana_footswitch.py

# Run with latency tracking enabled in CLI
python katana_footswitch.py -t

```

## 🌐 Web Interface

Once running, navigate to `http://<your-pi-ip>:5000` on any device on your network. The interface features:

* **Central LCD:** Mirroring the physical display.

* **Virtual Stomps:** With glowing LEDs indicating effect status (Green/Red/Yellow).

* **Interactive LEDs:** Visual feedback for active modes and effect colors.

## 🤓 Technical Details for Geeks

The core logic utilizes the **Roland SysEx protocol**. Unlike standard MIDI CC messages, this allows deep access to the Katana's internal state.

* **Checksum Calculation:** Implements the Roland 7-bit sum algorithm.

* **Message Caching:** All possible SysEx commands are pre-calculated on boot to minimize processing delay during your set.

* **Threading:** Separate threads handle MIDI Input, Refresh Polling, and the Flask/SocketIO server to ensure the UI never stutters.

## 📜 License

Use it, hack it, vibe with it, contrib back.
