import glob
import os
import struct
import sys
import time
import zlib
import psutil

import tkinter as tk
import ctypes
from ctypes import wintypes


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def _make_rgba_png_bytes(width, height, rows):
    """Pack raw RGBA rows into an in-memory PNG byte stream."""
    raw = bytearray()
    for row in rows:
        raw.append(0)  # PNG filter byte: None
        raw.extend(row)

    def chunk(tag, data):
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=1)
    return (
        b"\x89PNG\r\n\x1a\n"    
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


class CatTooltip:
    """Lightweight tooltip that appears on mouse hover."""

    def __init__(self, widget, get_text_func):
        self.widget = widget
        self.get_text_func = get_text_func
        self.tip_window = None

        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = max(0, self.widget.winfo_rooty() - 30)

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        tw.geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.get_text_func(),
            background="#1e1e1e",
            foreground="#f0f0f0",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=3,
        )
        label.pack()

    def update_text(self):
        if self.tip_window:
            for child in self.tip_window.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(text=self.get_text_func())

    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class CpuCat:
    # Key color for Windows transparency
    TRANS_COLOR = "#010101"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CPU Cat")

        # 1. Tkinter transparent overlay setup
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", self.TRANS_COLOR)
        self.root.config(bg=self.TRANS_COLOR)

        # Apply Windows toolwindow style (hides from taskbar / Alt+Tab)
        self._apply_toolwindow_style()

        # Scaling: factor 5 gives ~56x40 px (small & compact)
        self.scale_factor = 5
        self.cat_width = 58
        self.cat_height = 40

        # CPU & Animation state
        self.cpu_usage = 0.0
        self.last_cpu = 0.0
        self.animation_speed = 100
        self.state = "run"  # 'idle' or 'run'
        self.direction = 1  # 1 = right, -1 = left
        self.paused = False

        self.x_position = 0.0
        self.y_position = 0.0
        self.current_frame_idx = 0

        # Drag tracking
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0

        # 2. Load 6 running & 2 idle PNG frames with black-to-transparent handling
        self._load_animation_frames()

        # 3. Detect screen and taskbar
        self._detect_screen_and_taskbar()
        self.position_on_top_of_taskbar()

        # Canvas for transparent sprite
        self.canvas = tk.Canvas(
            self.root,
            width=self.cat_width,
            height=self.cat_height,
            bg=self.TRANS_COLOR,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()

        # Draw initial frame anchored at bottom-center (south)
        initial_img = self._get_current_image()
        self.sprite_item = self.canvas.create_image(
            self.cat_width // 2,
            self.cat_height,
            image=initial_img,
            anchor="s",
        )

        # 4. Tooltip & Interactions
        self.tooltip = CatTooltip(
            self.canvas,
            lambda: f"CPU: {self.last_cpu:.1f}% | {self.state.title()} ({self.animation_speed}%)",
        )

        self.canvas.bind("<Button-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_stop)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self.root.destroy())

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Control-q>", lambda e: self.root.destroy())

        # Initialize psutil
        psutil.cpu_percent(interval=None)

        # 5. Start async update loops
        self._cpu_loop()
        self._move_loop()
        self._anim_loop()

    def _apply_toolwindow_style(self):
        """Set WS_EX_TOOLWINDOW so the overlay does not clutter taskbar or Alt+Tab."""
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

    def _detect_screen_and_taskbar(self):
        """Query Windows user32 for exact monitor and taskbar dimensions."""
        user32 = ctypes.windll.user32
        self.screen_width = user32.GetSystemMetrics(0)
        self.screen_height = user32.GetSystemMetrics(1)

        rect = RECT()
        SPI_GETWORKAREA = 0x0030
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)

        self.work_bottom = rect.bottom
        self.taskbar_height = self.screen_height - (rect.bottom - rect.top)

    def position_on_top_of_taskbar(self):
        """Position the cat so its paws walk along the top edge of the taskbar."""
        if self.taskbar_height > 0:
            self.y_position = self.work_bottom - self.cat_height
        else:
            self.y_position = self.screen_height - self.cat_height
        self._update_window_position()

    def position_inside_taskbar(self):
        """Position the cat inside the taskbar (bottom of screen)."""
        self.y_position = self.screen_height - self.cat_height
        self._update_window_position()

    def _update_window_position(self):
        self.root.geometry(
            f"{self.cat_width}x{self.cat_height}+{int(self.x_position)}+{int(self.y_position)}"
        )

    def set_size(self, factor: int):
        """Dynamically change the cat size and update canvas and window."""
        self.scale_factor = factor
        self._load_animation_frames()
        self.canvas.config(width=self.cat_width, height=self.cat_height)
        self.canvas.coords(self.sprite_item, self.cat_width // 2, self.cat_height)
        img = self._get_current_image()
        self.canvas.itemconfig(self.sprite_item, image=img)
        self.position_on_top_of_taskbar()

    def _load_animation_frames(self):
        """
        Load 6 running PNGs and 2 idle PNGs.
        Subsamples by self.scale_factor and converts dark pixels (black background) to transparent RGBA.
        Generates both right-facing and left-facing (mirrored) frames in memory.
        """
        self.frames = {
            "cat_idle": {"right": [], "left": []},
            "cat_run": {"right": [], "left": []},
        }

        base_dir = os.path.dirname(os.path.abspath(__file__))
        max_w = 0
        max_h = 0

        for anim in ["cat_idle", "cat_run"]:
            pattern = os.path.join(base_dir, "assets", anim, "*.png")
            paths = sorted(glob.glob(pattern))

            for path in paths:
                orig_img = tk.PhotoImage(file=path)
                sub = orig_img.subsample(self.scale_factor, self.scale_factor)
                w, h = sub.width(), sub.height()
                if w > max_w:
                    max_w = w
                if h > max_h:
                    max_h = h

                rows_r = []
                rows_l = []
                for y in range(h):
                    pixels = [sub.get(x, y) for x in range(w)]

                    # Right-facing row
                    row_r = bytearray()
                    for r, g, b in pixels:
                        # Black background threshold
                        if max(r, g, b) < 35:
                            row_r.extend((0, 0, 0, 0))  # Full transparent
                        else:
                            row_r.extend((r, g, b, 255))
                    rows_r.append(row_r)

                    # Left-facing row (horizontally flipped)
                    row_l = bytearray()
                    for r, g, b in reversed(pixels):
                        if max(r, g, b) < 35:
                            row_l.extend((0, 0, 0, 0))  # Full transparent
                        else:
                            row_l.extend((r, g, b, 255))
                    rows_l.append(row_l)

                data_r = _make_rgba_png_bytes(w, h, rows_r)
                data_l = _make_rgba_png_bytes(w, h, rows_l)

                self.frames[anim]["right"].append(tk.PhotoImage(data=data_r))
                self.frames[anim]["left"].append(tk.PhotoImage(data=data_l))

        self.cat_width = max_w + 2
        self.cat_height = max_h + 1

    def _get_current_image(self):
        anim_key = f"cat_{self.state}"
        dir_key = "right" if self.direction == 1 else "left"
        anim_list = self.frames.get(anim_key, {}).get(dir_key, [])
        if not anim_list:
            anim_list = self.frames["cat_run"]["right"]
        return anim_list[self.current_frame_idx % len(anim_list)]

    def _cpu_loop(self):
        """Read CPU load with psutil every 500ms and adjust speed and mode."""
        cpu = psutil.cpu_percent(interval=None)
        self.last_cpu = cpu

        # Smooth out sudden spikes
        self.cpu_usage = 0.65 * self.cpu_usage + 0.35 * cpu

        # Switch between 2 idle frames (<10%) and 6 running frames (>=10%)
        if self.cpu_usage < 10.0:
            if self.state != "idle":
                self.state = "idle"
                self.current_frame_idx = 0
        else:
            if self.state != "run":
                self.state = "run"
                self.current_frame_idx = 0

        # Animation speed: 60% to 400%
        self.animation_speed = int(60 + (self.cpu_usage * 3.4))
        self.animation_speed = max(60, min(self.animation_speed, 400))

        self.tooltip.update_text()
        self.root.after(500, self._cpu_loop)

    def _move_loop(self):
        """Move cat across the taskbar every 30ms (~33 FPS)."""
        if not self._dragging and not self.paused:
            if self.state == "run":
                # Movement speed: 35 to 335 pixels/second
                speed = 35 + (self.cpu_usage * 3.0)
                distance = speed * 0.03
                self.x_position += distance * self.direction

                # Bounce at screen edges
                max_x = self.screen_width - self.cat_width
                if self.x_position >= max_x:
                    self.x_position = max_x
                    self.direction = -1
                elif self.x_position <= 0:
                    self.x_position = 0
                    self.direction = 1

            self._update_window_position()

        self.root.after(30, self._move_loop)

    def _anim_loop(self):
        """Cycle frames based on current mode and CPU speed."""
        if not self.paused:
            anim_key = f"cat_{self.state}"
            dir_key = "right" if self.direction == 1 else "left"
            anim_list = self.frames[anim_key][dir_key]

            self.current_frame_idx = (self.current_frame_idx + 1) % len(anim_list)
            img = anim_list[self.current_frame_idx]
            self.canvas.itemconfig(self.sprite_item, image=img)

            # Delay per frame
            if self.state == "idle":
                delay_ms = 450  # Slow, calm breathing in idle mode
            else:
                delay_ms = max(25, int(100 / (self.animation_speed / 100.0)))
        else:
            delay_ms = 100

        self.root.after(delay_ms, self._anim_loop)

    # Mouse & Context Menu Handlers
    def _on_drag_start(self, event):
        self._dragging = True
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self.x_position += dx
        self.y_position += dy
        self._update_window_position()

    def _on_drag_stop(self, event):
        self._dragging = False

    def _toggle_pause(self):
        self.paused = not self.paused

    def _show_context_menu(self, event):
        """Right-click menu providing status, positioning, and exit functionality."""
        menu = tk.Menu(self.root, tearoff=0)

        # Real-time status display
        menu.add_command(
            label=f"CPU: {self.last_cpu:.1f}% (Smoothed: {self.cpu_usage:.1f}%)",
            state="disabled",
        )
        menu.add_command(
            label=f"Speed: {self.animation_speed}% | Status: {self.state.title()}",
            state="disabled",
        )
        menu.add_separator()

        # Taskbar positioning options
        menu.add_command(
            label="Walk On Top of Taskbar",
            command=self.position_on_top_of_taskbar,
        )
        menu.add_command(
            label="Walk Inside Taskbar",
            command=self.position_inside_taskbar,
        )
        menu.add_separator()

        # Size options submenu
        size_menu = tk.Menu(menu, tearoff=0)
        sizes = [
            ("Tiny (~46px)", 6),
            ("Small (~56px)", 5),
            ("Medium (~70px)", 4),
            ("Large (~94px)", 3),
        ]
        for label, factor in sizes:
            prefix = "• " if self.scale_factor == factor else "   "
            size_menu.add_command(
                label=f"{prefix}{label}",
                command=lambda f=factor: self.set_size(f),
            )
        menu.add_cascade(label="Cat Size", menu=size_menu)
        menu.add_separator()

        # Pause / Resume toggle
        pause_label = "Resume Cat" if self.paused else "Pause Cat"
        menu.add_command(label=pause_label, command=self._toggle_pause)

        menu.add_separator()
        menu.add_command(label="Exit CPU Cat", command=self.root.destroy)

        menu.post(event.x_root, event.y_root)


def main():
    root = tk.Tk()
    app = CpuCat(root)
    root.mainloop()


if __name__ == "__main__":
    main()
