# 🐱 CPU Cat

An animated, lightweight desktop companion for Windows that visualizes your system's CPU usage in real-time. As your CPU load increases, the cat runs faster across your taskbar; when your computer is idling, the cat calms down and rests.

---

## ✨ Features

- **⚡ Real-Time CPU Monitoring:**
  - Dynamic CPU load tracking using [`psutil`](https://github.com/giampaolo/psutil).
  - Exponential smoothing to prevent erratic animation speed jumps during short load spikes.
  - Automatically switches between **Idle** (sleep/rest) and **Running** animations depending on CPU load.
  - Dynamic movement speed (35–335 px/sec) and frame rate (60%–400% speed) scaled according to CPU intensity.

- **🪟 Seamless Windows Integration:**
  - **Transparent & Frameless:** Floats neatly on top of other windows with no title bar or borders.
  - **Taskbar Snapping:** Automatically queries Windows work area metrics to walk along the top edge or inside the Windows taskbar.
  - **Clean Multitasking:** Configured with Windows `WS_EX_TOOLWINDOW` so it stays off your taskbar and doesn't clutter your `Alt + Tab` switcher.
  - **Always-on-Top:** Remains visible while you work or game.

- **🎮 Interactive & Customizable:**
  - **Draggable:** Click and drag the cat anywhere on your monitors.
  - **Hover Tooltip:** Shows real-time CPU percentage, state, and animation speed on mouse hover.
  - **Context Menu (Right-Click):**
    - View live CPU & animation statistics.
    - Switch positions: *Walk On Top of Taskbar* or *Walk Inside Taskbar*.
    - Resize on the fly: Tiny (~46px), Small (~56px), Medium (~70px), Large (~94px).
    - Pause / Resume animation and movement.
    - Quick exit.
  - **Keyboard Shortcuts & Quick Actions:**
    - Double left-click to close.
    - Press <kbd>Esc</kbd> or <kbd>Ctrl</kbd> + <kbd>Q</kbd> to quit instantly.

---

## 📋 Requirements

- **Operating System:** Windows 10 / 11 *(uses Windows Win32 APIs for transparency and work area detection)*
- **Python:** 3.8 or higher
- **Dependencies:** Listed in [`requirements.txt`](requirements.txt) (`psutil`)

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Cat.git
   cd Cat
   ```

2. **Create and activate a virtual environment (optional but recommended):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run CPU Cat:**
   ```powershell
   python main.py
   ```
   *(To run in the background without a command prompt window, you can run `pythonw main.py`)*

---

## 🖱️ Controls & Shortcuts

| Action | Control | Description |
| :--- | :--- | :--- |
| **Move** | Left Click + Drag | Drag and drop the cat anywhere on screen |
| **Inspect** | Mouse Hover | Displays tooltip with current CPU load and state |
| **Options** | Right Click | Opens context menu (status, sizes, taskbar snap, pause) |
| **Exit** | Double Left-Click | Instantly closes CPU Cat |
| **Exit** | <kbd>Esc</kbd> or <kbd>Ctrl</kbd> + <kbd>Q</kbd> | Shortcut to close application |

---

## 📁 Project Structure

```text
Cat/
│
├── assets/
│   ├── cat_idle/         # Idle animation frames (PNG)
│   │   ├── frame_01.png
│   │   └── frame_02.png
│   └── cat_run/          # Running animation frames (PNG)
│       ├── frame_01.png
│       ├── frame_02.png
│       ├── ...
│       └── frame_06.png
│
├── main.py               # Main application logic and Tkinter UI
├── requirements.txt      # Project dependencies (psutil)
├── .gitignore            # Git ignore file
└── README.md             # Project documentation
```

---

## 🛠️ How It Works

- **Native Windows Calls via `ctypes`:** Communicates directly with `user32.dll` to read monitor bounds (`GetSystemMetrics`) and taskbar dimensions (`SystemParametersInfoW` with `SPI_GETWORKAREA`).
- **In-Memory RGBA Processing:** Converts frame assets on the fly, creating transparent PNG byte streams and mirroring frames horizontally so the cat naturally faces its movement direction without needing separate flipped image assets on disk.
- **Tkinter Canvas:** Runs an asynchronous event-driven loop via `root.after()` for smooth multi-frame rendering and screen movement.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) (or choose your preferred license).

