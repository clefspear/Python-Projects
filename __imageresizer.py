#Created By Peter Azmy
#!/usr/bin/env python3
"""
Image Resizer
─────────────────────────────────────────────────────────────────────────────
Processes every PNG/JPEG in the current folder and produces two exports:

  filename_2560x1440.jpg  —  crop-to-fill resize, fully automatic.
  filename_1280x1920.jpg  —  vertical format with live-preview GUI.

GUI controls (1280x1920 editor):
  • Blur Strength       — Gaussian blur on background layer
  • Background Zoom     — zoom background image in/out
  • Background Pan      — drag on preview OR use sliders (H + V)
  • Foreground Position — vertical shift of the foreground image
  All values shown as % with typed-entry fields.

Usage:
    python image_resize.py
    (Run from the folder containing your images)

Dependencies:  Pillow   (pip install Pillow)
               tkinter  (built-in on Windows/Mac; Linux: sudo apt install python3-tk)
"""

import sys
import os
import threading
import queue
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageFilter, ImageTk
except ImportError:
    print("Installing Pillow...")
    os.system(f'"{sys.executable}" -m pip install Pillow --break-system-packages -q')
    from PIL import Image, ImageFilter, ImageTk

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    print("ERROR: tkinter is not installed.")
    print("  Windows/Mac: it comes with Python from python.org")
    print("  Linux:       sudo apt install python3-tk")
    sys.exit(1)

try:
    from send2trash import send2trash
except ImportError:
    print("Installing send2trash...")
    os.system(f'"{sys.executable}" -m pip install send2trash --break-system-packages -q')
    from send2trash import send2trash

# ── Dimensions ────────────────────────────────────────────────────────────────
W_HORIZ, H_HORIZ = 2560, 1440
W_VERT,  H_VERT  = 1280, 1920
JPEG_QUALITY     = 95
# Preview canvas sizes — large enough to see real detail
PREV_W, PREV_H       = 480, 720     # vertical editor  (3:4 aspect, ~half of 1280x1920)
HORIZ_PREV_W         = 854          # horizontal editor (16:9)
HORIZ_PREV_H         = 480

# Draft render scale used while dragging (fraction of output resolution)
DRAFT_SCALE = 4     # render native/4 instantly; swap in native-res when idle

# Native output resolutions used for the background full-quality render
FULL_W, FULL_H       = W_VERT, H_VERT        # 1280x1920
FULL_HW, FULL_HH     = W_HORIZ, H_HORIZ      # 2560x1440

# ── Image processing ──────────────────────────────────────────────────────────

def cover_resize(img, target_w, target_h):
    """Scale-to-fill then centre-crop — no black bars."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def make_2560x1440(img):
    return cover_resize(img.convert("RGB"), W_HORIZ, H_HORIZ)


def crop_horiz(img, zoom, x_pct, y_pct, rotate_deg=0.0):
    """
    Produce a 2560x1440 crop from img with zoom + pan + rotation.

    zoom       : float >= 1.0  — 1.0 = tightest fill, >1.0 = zoomed in further
    x_pct      : -100..100     — horizontal pan %
    y_pct      : -100..100     — vertical pan %
    rotate_deg : -180..180     — clockwise rotation in degrees
    """
    base = img.convert("RGB")
    # Apply rotation first (expand=True keeps full image visible after rotation)
    if rotate_deg != 0.0:
        base = base.rotate(-rotate_deg, resample=Image.BICUBIC, expand=True)
    src_w, src_h = base.size
    # Scale so image fills 2560x1440, then apply extra zoom
    fill_scale = max(W_HORIZ / src_w, H_HORIZ / src_h) * max(zoom, 1.0)
    scaled_w = int(src_w * fill_scale)
    scaled_h = int(src_h * fill_scale)
    scaled = base.resize((scaled_w, scaled_h), Image.LANCZOS)

    shift_x = int(x_pct / 100 * W_HORIZ)
    shift_y = int(y_pct / 100 * H_HORIZ)
    cx = max(0, min((scaled_w - W_HORIZ) // 2 - shift_x, scaled_w - W_HORIZ))
    cy = max(0, min((scaled_h - H_HORIZ) // 2 - shift_y, scaled_h - H_HORIZ))
    return scaled.crop((cx, cy, cx + W_HORIZ, cy + H_HORIZ))


def build_vertical_composite(img, blur_radius, bg_zoom,
                              bg_x_pct, bg_y_pct,
                              fg_zoom, fg_x_pct, fg_y_pct,
                              fg_rotate_deg=0.0, bg_rotate_deg=0.0):
    """
    Compose 1280x1920 vertical frame.

    bg_zoom          : float >= 1.0  — background zoom (1.0 = fill exactly)
    bg_x_pct/y_pct   : -100..100    — background pan %
    bg_rotate_deg    : -180..180     — clockwise rotation of background
    fg_zoom          : float >= 1.0  — foreground zoom (1.0 = fit to width)
    fg_x_pct/y_pct   : -100..100    — foreground pan %
    fg_rotate_deg    : -180..180     — clockwise rotation of foreground
    Returns (composite_image, fg_rect_on_canvas) where fg_rect = (x,y,w,h).
    """
    base     = img.convert("RGB")
    src_w, src_h = base.size

    # ── Background ────────────────────────────────────────────────────────────
    fill_scale = max(W_VERT / src_w, H_VERT / src_h) * max(bg_zoom, 1.0)
    bg_w = int(src_w * fill_scale)
    bg_h = int(src_h * fill_scale)
    bg_big = base.resize((bg_w, bg_h), Image.LANCZOS)

    # Apply rotation to the oversized bg before cropping (keeps full fill)
    if bg_rotate_deg != 0.0:
        bg_big = bg_big.rotate(-bg_rotate_deg, resample=Image.BICUBIC, expand=False)

    shift_x = int(bg_x_pct / 100 * W_VERT)
    shift_y = int(bg_y_pct / 100 * H_VERT)
    cx = max(0, min((bg_w - W_VERT) // 2 - shift_x, bg_w - W_VERT))
    cy = max(0, min((bg_h - H_VERT) // 2 - shift_y, bg_h - H_VERT))
    bg = bg_big.crop((cx, cy, cx + W_VERT, cy + H_VERT))

    if blur_radius > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # ── Foreground ────────────────────────────────────────────────────────────
    # Base size: fit to canvas width
    base_fg_w = W_VERT
    base_fg_h = int(src_h * (base_fg_w / src_w))

    # Apply zoom around centre
    fg_w = int(base_fg_w * max(fg_zoom, 1.0))
    fg_h = int(base_fg_h * max(fg_zoom, 1.0))
    fg   = base.resize((fg_w, fg_h), Image.LANCZOS)

    # Apply rotation (expand so full image stays visible; re-measure size)
    if fg_rotate_deg != 0.0:
        fg   = fg.rotate(-fg_rotate_deg, resample=Image.BICUBIC, expand=True)
        fg_w, fg_h = fg.size

    # Centre on canvas then apply pan offset
    # Pan is expressed as % of the canvas dimension so feel is consistent
    fg_x = (W_VERT - fg_w) // 2 + int(fg_x_pct / 100 * W_VERT)
    fg_y = (H_VERT - fg_h) // 2 + int(fg_y_pct / 100 * H_VERT)

    canvas_img = bg.copy()
    # Clamp-paste: only the visible portion is drawn
    src_x1 = max(-fg_x, 0);          dst_x = max(fg_x, 0)
    src_y1 = max(-fg_y, 0);          dst_y = max(fg_y, 0)
    src_x2 = fg_w - max(fg_x + fg_w - W_VERT, 0)
    src_y2 = fg_h - max(fg_y + fg_h - H_VERT, 0)
    if src_x2 > src_x1 and src_y2 > src_y1:
        canvas_img.paste(fg.crop((src_x1, src_y1, src_x2, src_y2)), (dst_x, dst_y))

    # Return composite + the bounding rect of the foreground on the canvas
    # (clipped to canvas; used for the selection indicator in the preview)
    fg_rect = (
        max(fg_x, 0),
        max(fg_y, 0),
        min(fg_x + fg_w, W_VERT),
        min(fg_y + fg_h, H_VERT),
    )
    return canvas_img, fg_rect

# ── Slider + typed-entry widget ───────────────────────────────────────────────

class LabeledSlider(tk.Frame):
    """Label / slider / typed-entry (%) in one row, fully bidirectional."""

    def __init__(self, parent, label, variable, from_, to_,
                 unit="%", fmt=".0f", **kwargs):
        super().__init__(parent, bg="#2b2b2b", **kwargs)
        self.var    = variable
        self.from_  = from_
        self.to_    = to_
        self.fmt    = fmt
        self._busy  = False

        tk.Label(self, text=label, bg="#2b2b2b", fg="white",
                 font=("Arial", 11, "bold"), anchor="w").pack(fill=tk.X)

        row = tk.Frame(self, bg="#2b2b2b")
        row.pack(fill=tk.X)

        self.slider = ttk.Scale(row, variable=variable, from_=from_, to=to_,
                                orient=tk.HORIZONTAL, command=self._on_slider)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.entry_var = tk.StringVar(value=self._f(variable.get()))
        self.entry = tk.Entry(row, textvariable=self.entry_var,
                              width=7, bg="#1a1a2e", fg="#5bc8f5",
                              insertbackground="white",
                              font=("Courier", 10), relief=tk.FLAT,
                              justify=tk.RIGHT)
        self.entry.pack(side=tk.LEFT)
        tk.Label(row, text=unit, bg="#2b2b2b", fg="#aaaaaa",
                 font=("Arial", 10), width=2).pack(side=tk.LEFT)

        self.entry.bind("<Return>",   self._on_entry)
        self.entry.bind("<FocusOut>", self._on_entry)
        variable.trace_add("write", self._on_var)

    def _f(self, v):
        return format(float(v), self.fmt)

    def _on_slider(self, _=None):
        if not self._busy:
            self._busy = True
            self.entry_var.set(self._f(self.var.get()))
            self._busy = False

    def _on_entry(self, _=None):
        if self._busy:
            return
        try:
            v = float(self.entry_var.get())
            v = max(self.from_, min(self.to_, v))
            self._busy = True
            self.var.set(v)
            self.entry_var.set(self._f(v))
            self._busy = False
        except ValueError:
            self.entry_var.set(self._f(self.var.get()))

    def _on_var(self, *_):
        if not self._busy:
            self.entry_var.set(self._f(self.var.get()))

# ── Horizontal editor (2560x1440) ────────────────────────────────────────────

class HorizontalEditor(tk.Toplevel):
    """
    Live-preview editor for the 2560x1440 export.
    Single layer — zoom in and drag to reframe the image.
    """

    def __init__(self, parent, img, filename):
        super().__init__(parent)
        self.title(f"2560\u00d71440 Editor \u2014 {filename}")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")
        self.result     = "skip"
        self.source_img = img
        self.filename   = filename

        self.zoom_var   = tk.DoubleVar(value=100.0)
        self.x_var      = tk.DoubleVar(value=0.0)
        self.y_var      = tk.DoubleVar(value=0.0)
        self.rotate_var = tk.DoubleVar(value=0.0)

        self._drag_origin = None

        self._build_ui()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._skip)
        # Render immediately once the window is fully drawn
        self.after(10, self._update_preview_draft)
        self.after(50, self._update_preview_full)

    def _build_ui(self):
        left = tk.Frame(self, bg="#1e1e1e")
        left.pack(side=tk.LEFT, padx=14, pady=14)

        tk.Label(left, text="Preview  (drag to reframe)",
                 bg="#1e1e1e", fg="#888888", font=("Arial", 9)).pack()

        self.canvas = tk.Canvas(left, width=HORIZ_PREV_W, height=HORIZ_PREV_H,
                                bg="black", highlightthickness=1,
                                highlightbackground="#5bc8f5",
                                cursor="fleur")
        self.canvas.pack()

        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        right = tk.Frame(self, bg="#2b2b2b", padx=18, pady=14)
        right.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 14), pady=14)

        tk.Label(right, text=f"Editing: {self.filename}",
                 bg="#2b2b2b", fg="white",
                 font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 12))

        src_w, src_h = self.source_img.size
        tk.Label(right,
                 text=f"Source: {src_w} \u00d7 {src_h}   \u2192   Output: 2560 \u00d7 1440",
                 bg="#2b2b2b", fg="#aaaaaa",
                 font=("Arial", 10)).pack(anchor="w", pady=(0, 12))

        def add(label, var, lo, hi):
            s = LabeledSlider(right, label, var, lo, hi)
            s.pack(fill=tk.X, pady=5)
            var.trace_add("write", lambda *_: self._schedule_update())

        def add_live(label, var, lo, hi):
            """Like add() but fires a draft render immediately for real-time feel."""
            s = LabeledSlider(right, label, var, lo, hi)
            s.pack(fill=tk.X, pady=5)
            var.trace_add("write", lambda *_: self._schedule_update(draft=True))

        add_live("\U0001f50d  Zoom",   self.zoom_var,   100, 500)
        add_live("\u2194  Pan (H)",    self.x_var,     -100, 100)
        add_live("\u2195  Pan (V)",    self.y_var,     -100, 100)
        add_live("\U0001f504  Rotate", self.rotate_var, -180, 180)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=12)

        btn_row = tk.Frame(right, bg="#2b2b2b")
        btn_row.pack()
        tk.Button(btn_row, text="\u2705  Save & Continue", command=self._save,
                  bg="#27ae60", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="\u23ed  Skip", command=self._skip,
                  bg="#555555", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)

        bottom_row = tk.Frame(right, bg="#2b2b2b")
        bottom_row.pack(pady=(8, 0))
        tk.Button(bottom_row, text="\u21ba  Reset", command=self._reset,
                  bg="#2b2b2b", fg="#888888", font=("Arial", 10),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(0, 16))
        tk.Button(bottom_row, text="\u26d4  Stop & Close", command=self._stop_app,
                  bg="#7f1a1a", fg="#ff6b6b", font=("Arial", 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)

    def _stop_app(self):
        """Ask for confirmation, then stop everything."""
        # Release grab so the messagebox is accessible
        try:
            self.grab_release()
        except Exception:
            pass
        confirmed = messagebox.askyesno(
            "Stop & Close",
            "Are you sure you want to stop processing and close?",
            icon="warning", parent=self
        )
        if not confirmed:
            # User said no — restore grab and stay open
            try:
                self.grab_set()
            except Exception:
                pass
            return
        self.result = "stop"
        self.destroy()
        master = self.master
        if master and hasattr(master, "_stop_and_close"):
            master._stop_and_close()

    def _on_press(self, event):
        self._drag_origin = (event.x, event.y, self.x_var.get(), self.y_var.get())

    def _on_drag(self, event):
        if self._drag_origin is None:
            return
        ox, oy, x0, y0 = self._drag_origin
        dx = (event.x - ox) * (100.0 / HORIZ_PREV_W)
        dy = (event.y - oy) * (100.0 / HORIZ_PREV_H)
        self.x_var.set(max(-100, min(100, x0 + dx)))
        self.y_var.set(max(-100, min(100, y0 + dy)))
        self._schedule_update(draft=True)

    def _on_release(self, event):
        self._drag_origin = None
        self._schedule_update(draft=False)

    def _schedule_update(self, draft=False):
        # Cancel any pending renders (both draft and full)
        if hasattr(self, "_after_id"):
            self.after_cancel(self._after_id)
        if hasattr(self, "_draft_id"):
            self.after_cancel(self._draft_id)
        if draft:
            # after(0) fires on the very next event-loop tick but IS cancellable
            self._draft_id = self.after(0, self._update_preview_draft)
        # Full-quality native render fires after 120ms of inactivity
        self._after_id = self.after(120, self._update_preview_full)

    def _snapshot(self):
        """Capture current slider values as a dict (thread-safe snapshot)."""
        return dict(zoom=self.zoom_var.get(), x=self.x_var.get(),
                    y=self.y_var.get(), rotate=self.rotate_var.get())

    def _render_at(self, w, h, quality, snap=None):
        if snap is None:
            snap = self._snapshot()
        result = crop_horiz(self.source_img,
                            zoom       = snap["zoom"] / 100,
                            x_pct      = snap["x"],
                            y_pct      = snap["y"],
                            rotate_deg = snap["rotate"])
        return result.resize((w, h), quality)

    def _update_preview_draft(self):
        dw = HORIZ_PREV_W // DRAFT_SCALE
        dh = HORIZ_PREV_H // DRAFT_SCALE
        img = self._render_at(dw, dh, Image.BILINEAR)
        img = img.resize((HORIZ_PREV_W, HORIZ_PREV_H), Image.NEAREST)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)

    def _update_preview_full(self):
        """
        Kick off a background thread that renders at native 2560x1440,
        then downscales to canvas size. The UI stays live the whole time.
        """
        snap = self._snapshot()
        self._render_token = getattr(self, "_render_token", 0) + 1
        token = self._render_token

        def worker():
            # Render at full native resolution for pixel-perfect accuracy
            full = self._render_at(FULL_HW, FULL_HH, Image.LANCZOS, snap)
            # Downscale to canvas for display
            preview = full.resize((HORIZ_PREV_W, HORIZ_PREV_H), Image.LANCZOS)
            # Post back to main thread; discard if a newer render has started
            if getattr(self, "_render_token", 0) == token:
                self.after(0, lambda: self._apply_preview_horiz(preview))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_preview_horiz(self, preview):
        self._tk_img = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)

    def get_final_image(self):
        return crop_horiz(self.source_img,
                          zoom       = self.zoom_var.get() / 100,
                          x_pct      = self.x_var.get(),
                          y_pct      = self.y_var.get(),
                          rotate_deg = self.rotate_var.get())

    def _reset(self):
        self.zoom_var.set(100.0)
        self.x_var.set(0.0)
        self.y_var.set(0.0)
        self.rotate_var.set(0.0)

    def _save(self):
        self.result = "save"
        self.destroy()

    def _skip(self):
        self.result = "skip"
        self.destroy()

# ── Editor window ─────────────────────────────────────────────────────────────

class VerticalEditor(tk.Toplevel):
    """
    Live-preview editor for 1280x1920 export.

    Active layer (BG or FG) shown with coloured border on the preview.
    Drag on the preview moves the active layer.
    Clicking inside the foreground region selects it; outside selects background.
    Default active layer = background.
    """

    LAYER_BG = "bg"
    LAYER_FG = "fg"

    def __init__(self, parent, img, filename):
        super().__init__(parent)
        self.title(f"1280x1920 Editor — {filename}")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")
        self.result     = "skip"
        self.source_img = img
        self.filename   = filename

        self.blur_var    = tk.DoubleVar(value=40.0)
        self.bg_zoom_var    = tk.DoubleVar(value=100.0)
        self.bg_x_var       = tk.DoubleVar(value=0.0)
        self.bg_y_var       = tk.DoubleVar(value=0.0)
        self.bg_rotate_var  = tk.DoubleVar(value=0.0)
        self.fg_zoom_var    = tk.DoubleVar(value=220.0)
        self.fg_x_var       = tk.DoubleVar(value=0.0)
        self.fg_y_var       = tk.DoubleVar(value=0.0)
        self.fg_rotate_var  = tk.DoubleVar(value=0.0)

        self._active_layer = self.LAYER_BG
        self._fg_prev_rect = (0, 0, PREV_W, PREV_H)
        self._drag_origin  = None

        self._build_ui()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._skip)
        # Render immediately once the window is fully drawn
        self.after(10, self._update_preview_draft)
        self.after(50, self._update_preview_full)

    def _build_ui(self):
        left = tk.Frame(self, bg="#1e1e1e")
        left.pack(side=tk.LEFT, padx=14, pady=14)

        self.canvas = tk.Canvas(left, width=PREV_W, height=PREV_H,
                                bg="black", highlightthickness=0,
                                cursor="fleur")
        self.canvas.pack()

        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        right = tk.Frame(self, bg="#2b2b2b", padx=18, pady=14)
        right.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 14), pady=14)

        tk.Label(right, text=f"Editing: {self.filename}",
                 bg="#2b2b2b", fg="white",
                 font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 4))

        src_w, src_h = self.source_img.size
        tk.Label(right,
                 text=f"Source: {src_w} × {src_h}   →   Output: 1280 × 1920",
                 bg="#2b2b2b", fg="#aaaaaa",
                 font=("Arial", 10)).pack(anchor="w", pady=(0, 10))

        def add(label, var, lo, hi):
            s = LabeledSlider(right, label, var, lo, hi)
            s.pack(fill=tk.X, pady=4)
            var.trace_add("write", lambda *_: self._schedule_update())

        def add_live(label, var, lo, hi):
            """Like add() but fires a draft render immediately for real-time feel."""
            s = LabeledSlider(right, label, var, lo, hi)
            s.pack(fill=tk.X, pady=4)
            var.trace_add("write", lambda *_: self._schedule_update(draft=True))

        self._bg_hdr = tk.Label(right, text="▶  BACKGROUND (active)",
                                bg="#2b2b2b", fg="#5bc8f5",
                                font=("Arial", 10, "bold"), anchor="w",
                                cursor="hand2")
        self._bg_hdr.pack(fill=tk.X, pady=(4, 2))
        self._bg_hdr.bind("<Button-1>", lambda _: self._set_layer(self.LAYER_BG))

        add_live("🌫  Blur Strength",      self.blur_var,          0,   100)
        add_live("🔍  Background Zoom",    self.bg_zoom_var,      100,  300)
        add_live("↔  Background Pan (H)", self.bg_x_var,        -100,  100)
        add_live("↕  Background Pan (V)", self.bg_y_var,        -100,  100)
        add_live("🔄  Background Rotate", self.bg_rotate_var,   -180,  180)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=8)

        self._fg_hdr = tk.Label(right, text="▶  FOREGROUND",
                                bg="#2b2b2b", fg="#aaaaaa",
                                font=("Arial", 10, "bold"), anchor="w",
                                cursor="hand2")
        self._fg_hdr.pack(fill=tk.X, pady=(0, 2))
        self._fg_hdr.bind("<Button-1>", lambda _: self._set_layer(self.LAYER_FG))

        add_live("🔍  Foreground Zoom",    self.fg_zoom_var,    100, 300)
        add_live("↔  Foreground Pan (H)", self.fg_x_var,      -100, 100)
        add_live("↕  Foreground Pan (V)", self.fg_y_var,      -100, 100)
        add_live("🔄  Foreground Rotate", self.fg_rotate_var, -180, 180)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, pady=10)

        btn_row = tk.Frame(right, bg="#2b2b2b")
        btn_row.pack()
        tk.Button(btn_row, text="✅  Save & Continue", command=self._save,
                  bg="#27ae60", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="⏭  Skip", command=self._skip,
                  bg="#555555", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)

        bottom_row = tk.Frame(right, bg="#2b2b2b")
        bottom_row.pack(pady=(8, 0))
        tk.Button(bottom_row, text="↺  Reset", command=self._reset,
                  bg="#2b2b2b", fg="#888888", font=("Arial", 10),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(0, 16))
        tk.Button(bottom_row, text="⛔  Stop & Close", command=self._stop_app,
                  bg="#7f1a1a", fg="#ff6b6b", font=("Arial", 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)

    def _stop_app(self):
        """Ask for confirmation, then stop everything."""
        try:
            self.grab_release()
        except Exception:
            pass
        confirmed = messagebox.askyesno(
            "Stop & Close",
            "Are you sure you want to stop processing and close?",
            icon="warning", parent=self
        )
        if not confirmed:
            try:
                self.grab_set()
            except Exception:
                pass
            return
        self.result = "stop"
        self.destroy()
        master = self.master
        if master and hasattr(master, "_stop_and_close"):
            master._stop_and_close()

    def _set_layer(self, layer):
        self._active_layer = layer
        if layer == self.LAYER_BG:
            self._bg_hdr.config(fg="#5bc8f5",
                                text="▶  BACKGROUND (active)")
            self._fg_hdr.config(fg="#aaaaaa",
                                text="▶  FOREGROUND")

        else:
            self._bg_hdr.config(fg="#aaaaaa",
                                text="▶  BACKGROUND")
            self._fg_hdr.config(fg="#f5c842",
                                text="▶  FOREGROUND (active)")

        self._draw_selection_border()

    def _point_in_fg(self, px, py):
        x0, y0, x1, y1 = self._fg_prev_rect
        return x0 <= px <= x1 and y0 <= py <= y1

    def _on_press(self, event):
        if self._point_in_fg(event.x, event.y):
            self._set_layer(self.LAYER_FG)
        else:
            self._set_layer(self.LAYER_BG)

        if self._active_layer == self.LAYER_BG:
            self._drag_origin = (event.x, event.y,
                                 self.bg_x_var.get(), self.bg_y_var.get())
        else:
            self._drag_origin = (event.x, event.y,
                                 self.fg_x_var.get(), self.fg_y_var.get())

    def _on_drag(self, event):
        if self._drag_origin is None:
            return
        ox, oy, x0, y0 = self._drag_origin
        dx = (event.x - ox) * (100.0 / PREV_W)
        dy = (event.y - oy) * (100.0 / PREV_H)
        if self._active_layer == self.LAYER_BG:
            self.bg_x_var.set(max(-100, min(100, x0 + dx)))
            self.bg_y_var.set(max(-100, min(100, y0 + dy)))
        else:
            self.fg_x_var.set(max(-100, min(100, x0 + dx)))
            self.fg_y_var.set(max(-100, min(100, y0 + dy)))
        self._schedule_update(draft=True)

    def _on_release(self, event):
        self._drag_origin = None
        self._schedule_update(draft=False)

    def _schedule_update(self, draft=False):
        if hasattr(self, "_after_id"):
            self.after_cancel(self._after_id)
        if hasattr(self, "_draft_id"):
            self.after_cancel(self._draft_id)
        if draft:
            self._draft_id = self.after(0, self._update_preview_draft)
        self._after_id = self.after(120, self._update_preview_full)

    def _snapshot(self):
        return dict(
            blur=self.blur_var.get(), bg_zoom=self.bg_zoom_var.get(),
            bg_x=self.bg_x_var.get(), bg_y=self.bg_y_var.get(),
            bg_rotate=self.bg_rotate_var.get(),
            fg_zoom=self.fg_zoom_var.get(),
            fg_x=self.fg_x_var.get(), fg_y=self.fg_y_var.get(),
            fg_rotate=self.fg_rotate_var.get(),
        )

    def _composite_at(self, w, h, quality, snap=None):
        if snap is None:
            snap = self._snapshot()
        composite, fg_rect = build_vertical_composite(
            self.source_img,
            blur_radius   = snap["blur"] / 100 * 80,
            bg_zoom       = snap["bg_zoom"] / 100,
            bg_x_pct      = snap["bg_x"],
            bg_y_pct      = snap["bg_y"],
            fg_zoom       = snap["fg_zoom"] / 100,
            fg_x_pct      = snap["fg_x"],
            fg_y_pct      = snap["fg_y"],
            fg_rotate_deg = snap["fg_rotate"],
            bg_rotate_deg = snap["bg_rotate"],
        )
        return composite.resize((w, h), quality), fg_rect

    def _update_preview_draft(self):
        dw = PREV_W // DRAFT_SCALE
        dh = PREV_H // DRAFT_SCALE
        img, fg_rect = self._composite_at(dw, dh, Image.BILINEAR)
        img = img.resize((PREV_W, PREV_H), Image.NEAREST)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)
        sx = PREV_W / W_VERT; sy = PREV_H / H_VERT
        self._fg_prev_rect = (int(fg_rect[0]*sx), int(fg_rect[1]*sy),
                              int(fg_rect[2]*sx), int(fg_rect[3]*sy))
        self._draw_selection_border()

    def _update_preview_full(self):
        """
        Background thread: renders at native 1280x1920, downscales to canvas.
        The UI stays live while this runs.
        """
        snap = self._snapshot()
        self._render_token = getattr(self, "_render_token", 0) + 1
        token = self._render_token

        def worker():
            # Full native resolution composite
            full, fg_rect = self._composite_at(FULL_W, FULL_H, Image.LANCZOS, snap)
            # Downscale to canvas size for display
            preview = full.resize((PREV_W, PREV_H), Image.LANCZOS)
            if getattr(self, "_render_token", 0) == token:
                self.after(0, lambda: self._apply_preview_vert(preview, fg_rect))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_preview_vert(self, preview, fg_rect):
        self._tk_img = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)
        sx = PREV_W / W_VERT; sy = PREV_H / H_VERT
        self._fg_prev_rect = (int(fg_rect[0]*sx), int(fg_rect[1]*sy),
                              int(fg_rect[2]*sx), int(fg_rect[3]*sy))
        self._draw_selection_border()

    def _update_preview(self):
        self._update_preview_full()



    def _draw_selection_border(self):
        self.canvas.delete("border")
        if self._active_layer == self.LAYER_BG:
            self.canvas.create_rectangle(
                1, 1, PREV_W - 1, PREV_H - 1,
                outline="#5bc8f5", width=2, tags="border"
            )
        else:
            x0, y0, x1, y1 = self._fg_prev_rect
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="#f5c842", width=2, tags="border"
            )

    def get_final_image(self):
        composite, _ = build_vertical_composite(
            self.source_img,
            blur_radius   = self.blur_var.get() / 100 * 80,
            bg_zoom       = self.bg_zoom_var.get() / 100,
            bg_x_pct      = self.bg_x_var.get(),
            bg_y_pct      = self.bg_y_var.get(),
            fg_zoom       = self.fg_zoom_var.get() / 100,
            fg_x_pct      = self.fg_x_var.get(),
            fg_y_pct      = self.fg_y_var.get(),
            fg_rotate_deg = self.fg_rotate_var.get(),
            bg_rotate_deg = self.bg_rotate_var.get(),
        )
        return composite

    def _reset(self):
        self.blur_var.set(40.0)
        self.bg_zoom_var.set(100.0)
        self.bg_x_var.set(0.0)
        self.bg_y_var.set(0.0)
        self.bg_rotate_var.set(0.0)
        self.fg_zoom_var.set(220.0)
        self.fg_x_var.set(0.0)
        self.fg_y_var.set(0.0)
        self.fg_rotate_var.set(0.0)
        self._set_layer(self.LAYER_BG)

    def _save(self):
        self.result = "save"
        self.destroy()

    def _skip(self):
        self.result = "skip"
        self.destroy()

# ── Custom neon checkbox ─────────────────────────────────────────────────────

class _NeonCheckbox(tk.Canvas):
    """
    Canvas-drawn checkbox: white rounded box, neon cyan/green checkmark.
    Toggles on click. Syncs with a tk.BooleanVar.
    """
    SIZE   = 22
    RADIUS = 4
    CHECK_COLOR = "#00e5ff"   # neon cyan — visible on any dark background
    BOX_FILL    = "#ffffff"
    BOX_OUTLINE = "#aaaaaa"

    def __init__(self, parent, variable, **kw):
        super().__init__(parent,
                         width=self.SIZE, height=self.SIZE,
                         bg="#1e1e1e", highlightthickness=0,
                         cursor="hand2", **kw)
        self._var = variable
        self._draw()
        self.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *_: self._draw())

    def _draw(self):
        self.delete("all")
        s = self.SIZE
        r = self.RADIUS
        # White rounded-rect box
        self.create_rounded_rect(2, 2, s-2, s-2, r,
                                 fill=self.BOX_FILL, outline=self.BOX_OUTLINE, width=1)
        if self._var.get():
            # Neon checkmark — bold two-segment line
            m = s * 0.18
            self.create_line(m+1, s*0.52, s*0.42, s*0.78,
                             fill=self.CHECK_COLOR, width=3,
                             capstyle=tk.ROUND, joinstyle=tk.ROUND)
            self.create_line(s*0.42, s*0.78, s-m, s*0.24,
                             fill=self.CHECK_COLOR, width=3,
                             capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        self.create_arc(x1, y1, x1+2*r, y1+2*r, start=90,  extent=90, style=tk.PIESLICE, **kw)
        self.create_arc(x2-2*r, y1, x2, y1+2*r, start=0,   extent=90, style=tk.PIESLICE, **kw)
        self.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, style=tk.PIESLICE, **kw)
        self.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, style=tk.PIESLICE, **kw)
        self.create_rectangle(x1+r, y1, x2-r, y2, **kw)
        self.create_rectangle(x1, y1+r, x2, y2-r, **kw)

    def _toggle(self, _=None):
        self._var.set(not self._var.get())

# ── Delete confirmation dialog ────────────────────────────────────────────────

class DeleteDialog(tk.Toplevel):

    def __init__(self, parent, image_files):
        super().__init__(parent)
        self.title("Delete Original Files?")
        self.configure(bg="#1e1e1e")
        self.resizable(False, False)
        self.image_files = image_files
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="Move Originals to Recycle Bin?",
                 bg="#1e1e1e", fg="white",
                 font=("Arial", 14, "bold")).pack(pady=(18, 4), padx=24)
        tk.Label(self,
                 text="Check the files you want to move to the Recycle Bin.\nExported copies will NOT be affected.",
                 bg="#1e1e1e", fg="#aaaaaa",
                 font=("Arial", 10), justify=tk.CENTER).pack(padx=24, pady=(0, 12))

        frame = tk.Frame(self, bg="#1e1e1e")
        frame.pack(padx=24, fill=tk.BOTH)

        list_h = min(280, len(self.image_files) * 30 + 10)
        cv = tk.Canvas(frame, bg="#1e1e1e", highlightthickness=0,
                       width=420, height=list_h)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=cv.yview)
        inner = tk.Frame(cv, bg="#1e1e1e")
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.check_vars = []
        for path in self.image_files:
            var = tk.BooleanVar(value=True)
            self.check_vars.append((path, var))
            row = tk.Frame(inner, bg="#1e1e1e")
            row.pack(fill=tk.X, pady=3)
            # Custom canvas-drawn checkbox: white box, neon green checkmark
            cb = _NeonCheckbox(row, variable=var)
            cb.pack(side=tk.LEFT, padx=(4, 8))
            tk.Label(row, text=path.name, bg="#1e1e1e", fg="#dddddd",
                     font=("Arial", 10), anchor="w").pack(side=tk.LEFT)

        tog = tk.Frame(self, bg="#1e1e1e")
        tog.pack(pady=(8, 0))
        tk.Button(tog, text="Select All",
                  command=lambda: [v.set(True)  for _, v in self.check_vars],
                  bg="#1e1e1e", fg="#5bc8f5", relief=tk.FLAT,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.LEFT, padx=8)
        tk.Button(tog, text="Deselect All",
                  command=lambda: [v.set(False) for _, v in self.check_vars],
                  bg="#1e1e1e", fg="#5bc8f5", relief=tk.FLAT,
                  font=("Arial", 9), cursor="hand2").pack(side=tk.LEFT, padx=8)

        btn = tk.Frame(self, bg="#1e1e1e")
        btn.pack(pady=16)
        tk.Button(btn, text="🗑  Move to Recycle Bin", command=self._delete,
                  bg="#c0392b", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Button(btn, text="Keep All", command=self.destroy,
                  bg="#555555", fg="white", font=("Arial", 12, "bold"),
                  padx=16, pady=8, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=6)

    def _delete(self):
        to_delete = [p for p, v in self.check_vars if v.get()]
        if not to_delete:
            self.destroy()
            return
        names = "\n".join(f"  • {p.name}" for p in to_delete)
        if messagebox.askyesno("Move to Recycle Bin",
                               f"Move {len(to_delete)} file(s) to the Recycle Bin?\n\n{names}",
                               icon="question", parent=self):
            moved, failed = [], []
            for path in to_delete:
                try:
                    send2trash(str(path))
                    moved.append(path.name)
                except Exception as e:
                    failed.append(f"{path.name} ({e})")
            summary = f"Moved {len(moved)} file(s) to the Recycle Bin."
            if failed:
                summary += "\n\nFailed to move:\n" + "\n".join(failed)
            messagebox.showinfo("Done", summary, parent=self.master)
        self.destroy()

# ── Main app window ───────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self, image_files):
        super().__init__()
        self.title("Image Resizer — Processing")
        self.configure(bg="#1a1a2e")
        self.resizable(False, False)
        self.image_files   = image_files
        self.current_index = 0
        self.saved         = []
        self.skipped       = []
        self._cancelled    = False
        self._active_editor = None
        self._build_ui()
        self._process_next()

    # Thumbnail size in the log window
    THUMB_W = 160
    THUMB_H = 120

    def _build_ui(self):
        tk.Label(self, text="Image Resizer", bg="#1a1a2e", fg="white",
                 font=("Arial", 18, "bold")).pack(pady=(20, 4))
        tk.Label(self, text="2560×1440  +  1280×1920  exports",
                 bg="#1a1a2e", fg="#5bc8f5", font=("Arial", 11)).pack()

        self.status_lbl = tk.Label(self, text="", bg="#1a1a2e", fg="#aaaaaa",
                                   font=("Arial", 10), wraplength=420)
        self.status_lbl.pack(pady=(14, 4), padx=24)

        # ── Side-by-side: thumbnail on left, log on right ─────────────────────
        mid = tk.Frame(self, bg="#1a1a2e")
        mid.pack(padx=20, pady=4, fill=tk.BOTH)

        # Thumbnail panel
        thumb_frame = tk.Frame(mid, bg="#0f0f1a",
                               width=self.THUMB_W + 8,
                               highlightthickness=1,
                               highlightbackground="#333355")
        thumb_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        thumb_frame.pack_propagate(False)

        tk.Label(thumb_frame, text="Current Image",
                 bg="#0f0f1a", fg="#555577",
                 font=("Arial", 8)).pack(pady=(6, 2))

        self.thumb_canvas = tk.Canvas(thumb_frame,
                                      width=self.THUMB_W,
                                      height=self.THUMB_H,
                                      bg="#0a0a14",
                                      highlightthickness=0)
        self.thumb_canvas.pack(padx=4, pady=4)

        self.thumb_name_lbl = tk.Label(thumb_frame, text="",
                                       bg="#0f0f1a", fg="#888899",
                                       font=("Arial", 7), wraplength=self.THUMB_W)
        self.thumb_name_lbl.pack(pady=(0, 6), padx=4)

        # Log text
        self.log_text = tk.Text(mid, width=44, height=14,
                                bg="#0f0f1a", fg="#cccccc",
                                font=("Courier", 9), relief=tk.FLAT,
                                state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.done_btn = tk.Button(self, text="Done", command=self.quit,
                                  bg="#2980b9", fg="white",
                                  font=("Arial", 11, "bold"),
                                  padx=20, pady=6, relief=tk.FLAT,
                                  state=tk.DISABLED)
        self.done_btn.pack(pady=(8, 20))

    def _stop_and_close(self):
        """Stop processing — enable Done button so user can close when ready."""
        self._cancelled = True
        ed = getattr(self, "_active_editor", None)
        if ed:
            try:
                if ed.winfo_exists():
                    ed.grab_release()
                    ed.result = "stop"
                    ed.destroy()
            except Exception:
                pass
        self._active_editor = None
        try:
            self._log(f"\n  ⛔  Stopped by user.")
        except Exception:
            pass
        try:
            self.done_btn.config(state=tk.NORMAL)
            self.status_lbl.config(text="Stopped. Click Done to close.")
        except Exception:
            pass

    def _show_thumbnail(self, img):
        """Scale image to fit the thumbnail canvas and display it."""
        thumb = img.copy()
        thumb.thumbnail((self.THUMB_W, self.THUMB_H), Image.LANCZOS)
        # Centre on canvas
        self._thumb_tk = ImageTk.PhotoImage(thumb)
        self.thumb_canvas.delete("all")
        x = self.THUMB_W // 2
        y = self.THUMB_H // 2
        self.thumb_canvas.create_image(x, y, anchor=tk.CENTER,
                                       image=self._thumb_tk)

    def _log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.update_idletasks()

    def _process_next(self):
        if self._cancelled:
            return
        if self.current_index >= len(self.image_files):
            self._finish()
            return

        path  = self.image_files[self.current_index]
        total = len(self.image_files)
        self.status_lbl.config(
            text=f"Processing {self.current_index + 1} / {total}:  {path.name}"
        )
        self._log(f"\n[{self.current_index + 1}/{total}] {path.name}")
        self.update_idletasks()

        try:
            img = Image.open(path)
            img.load()
            self._show_thumbnail(img)
            self.thumb_name_lbl.config(text=path.name)
            self.update_idletasks()
            self._log(f"  📐  {img.width} × {img.height} px")
            stem    = path.stem
            out_dir = path.parent

            # 2560×1440 — editor with zoom/pan
            self._active_editor = HorizontalEditor(self, img, path.name)
            h_editor = self._active_editor
            self.wait_window(h_editor)
            self._active_editor = None

            # If user hit Stop & Close, bail — do NOT open vert editor
            if self._cancelled or h_editor.result == "stop":
                return

            if h_editor.result == "save":
                horiz      = h_editor.get_final_image()
                horiz_path = out_dir / f"{stem}_2560x1440.jpg"
                horiz.save(horiz_path, "JPEG", quality=JPEG_QUALITY, subsampling=0)
                self._log(f"  \u2705  {horiz_path.name}")
            else:
                self._log(f"  \u23ed   Skipped 2560\u00d71440 for {path.name}")

            # 1280×1920 — open editor (main window stays visible alongside it)
            self._active_editor = VerticalEditor(self, img, path.name)
            editor = self._active_editor
            self.wait_window(editor)
            self._active_editor = None

            if editor.result == "save":
                vert      = editor.get_final_image()
                vert_path = out_dir / f"{stem}_1280x1920.jpg"
                vert.save(vert_path, "JPEG", quality=JPEG_QUALITY, subsampling=0)
                self._log(f"  ✅  {vert_path.name}")
                self.saved.append(path.name)
            else:
                self._log(f"  ⏭   Skipped 1280×1920 for {path.name}")
                self.skipped.append(path.name)

        except Exception as e:
            self._log(f"  ❌  Error: {e}")

        self.current_index += 1
        self.after(50, self._process_next)

    def _finish(self):
        self._log(f"\n{'─' * 44}")
        self._log(f"  Done!  {len(self.saved)} saved, {len(self.skipped)} skipped.")
        self._log(f"{'─' * 44}")
        self.status_lbl.config(text="All images processed.")
        self.thumb_canvas.delete("all")
        self.thumb_name_lbl.config(text="All done!")
        self.done_btn.config(state=tk.NORMAL)
        self.after(400, self._prompt_delete)

    def _prompt_delete(self):
        DeleteDialog(self, self.image_files)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    cwd  = Path.cwd()
    exts = {".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"}
    image_files = sorted(
        f for f in cwd.iterdir()
        if f.is_file()
        and f.suffix in exts
        and "_2560x1440" not in f.stem
        and "_1280x1920" not in f.stem
    )

    if not image_files:
        print(f"\n  No PNG or JPEG images found in: {cwd}\n")
        sys.exit(0)

    print(f"\n  Found {len(image_files)} image(s) — launching GUI...\n")
    app = App(image_files)
    app.mainloop()


if __name__ == "__main__":
    main()