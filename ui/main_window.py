import os
import json
import threading
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
from dotenv import load_dotenv

from config.settings import (
    PRESETS, APP_NAME, APP_VERSION, DPI, DEFAULT_BG,
    DEFAULT_MARGIN_X_MM, DEFAULT_MARGIN_Y_MM,
    DEFAULT_GAP_X_MM, DEFAULT_GAP_Y_MM, DEFAULT_BORDER_MM,
    DEFAULT_PHOTOS_PER_LINE, DEFAULT_QUANTITY, MAX_HISTORY,
)
from core.image_engine import (
    smart_crop_and_resize, apply_adjustments,
    rotate_90, flip_horizontal, flip_vertical,
    apply_filter_preset, auto_white_balance, denoise,
    adjust_exposure, adjust_saturation, adjust_highlights_shadows,
    vignette, sharpen_portrait, auto_enhance_portrait,
    FILTER_PRESETS,
)
from core.background_engine import composite_on_color
from core.smart_passport_crop import smart_passport_crop, analyze_crop, draw_crop_guide
from core.advanced_detection import detect_advanced
from core.manual_training_bot import make_example, learn_profile, save_profile as save_crop_bot_profile, load_profile as load_crop_bot_profile
from core.print_engine import make_a4_sheet, calculate_a4_layout
from core.export_engine import save_image
from services.remove_bg import RemoveBGService
from core.style_trainer import extract_pdf_text, parse_instructions, save_profile, load_profile
from core.ai_style_learning import learn_style, save_learned_style, load_learned_style, apply_learned_style

load_dotenv()

# Smooth & Cool Modern Styling Defaults
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
CONFIG_DIR = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "PassportPhotoStudioPro")
CONFIG_FILE = os.path.join(CONFIG_DIR, "user_config.json")
ACCENT = "#4f8cff"
ACCENT_HOVER = "#3b73e8"
SURFACE = "#17181c"
SURFACE_2 = "#202228"
SURFACE_3 = "#282b31"
TEXT_MUTED = "#9aa0ad"


def load_user_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_user_config(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save user config: {e}")

def is_first_time_user():
    return load_user_config().get("first_time", True)

def mark_first_time_complete():
    data = load_user_config()
    data["first_time"] = False
    save_user_config(data)

def configured_remove_bg_key():
    # Prefer an environment variable; otherwise use the local user configuration.
    return os.getenv("REMOVE_BG_API_KEY", "").strip() or load_user_config().get("remove_bg_api_key", "").strip()


class SplashScreen(ctk.CTkToplevel):
    """Windows 11-inspired startup screen with a lightweight progress animation."""
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.geometry("560x330")
        self.configure(fg_color=SURFACE)
        self._progress = 0
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, corner_radius=24, fg_color=SURFACE_2, border_width=1, border_color="#30343c")
        card.pack(expand=True, fill="both", padx=2, pady=2)

        logo = ctk.CTkFrame(card, width=76, height=76, corner_radius=20, fg_color=ACCENT)
        logo.pack(pady=(42, 12))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="ID", text_color="white",
                     font=ctk.CTkFont(size=27, weight="bold")).place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(card, text=APP_NAME, font=ctk.CTkFont(size=21, weight="bold"),
                     text_color="#f5f7fb").pack()
        ctk.CTkLabel(card, text="Professional passport & ID photo editor",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(pady=(3, 18))

        self.bar = ctk.CTkProgressBar(card, height=5, corner_radius=5, progress_color=ACCENT)
        self.bar.pack(fill="x", padx=110)
        self.bar.set(0)
        self.status = ctk.CTkLabel(card, text="Starting…", font=ctk.CTkFont(size=10),
                                   text_color=TEXT_MUTED)
        self.status.pack(pady=(9, 0))

    def animate(self, callback):
        steps = [
            (0.25, "Loading editor…"),
            (0.50, "Preparing photo tools…"),
            (0.75, "Preparing print engine…"),
            (1.00, "Ready"),
        ]
        def tick(i=0):
            if i >= len(steps):
                self.after(180, callback)
                return
            value, label = steps[i]
            self.bar.set(value)
            self.status.configure(text=label)
            self.after(180, lambda: tick(i + 1))
        tick()


class FirstTimeOnboardingModal(ctk.CTkToplevel):
    """Clean, user-friendly intro guide for first-time users."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Welcome to Passport Photo Studio")
        self.geometry("560x520")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1e1e24")
        frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        ctk.CTkLabel(
            frame, text="👋 Welcome to Passport Studio Pro!",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            frame,
            text="Get standard passport photos ready for printing in 3 simple steps.",
            font=ctk.CTkFont(size=12), text_color="#a0a0a0"
        ).pack(pady=(0, 15))

        steps = [
            ("1️⃣ Open Photo", "Click 'Open Photo' (Ctrl+O) to load any portrait image."),
            ("2️⃣ Crop & Enhance", "Use Smart Passport Crop, change background color, or apply soft retouching."),
            ("3️⃣ Print Layout", "Select your required print quantity and generate an A4 sheet layout instantly.")
        ]

        for title, desc in steps:
            card = ctk.CTkFrame(frame, fg_color="#2b2b36", corner_radius=8)
            card.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=12), text_color="#b0b0b0", justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        # Helpful Shortcuts Summary
        shortcuts_frame = ctk.CTkFrame(frame, fg_color="transparent")
        shortcuts_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(
            shortcuts_frame,
            text="⚡ Shortcuts:  Ctrl+O (Open)  •  Ctrl+S (Save)  •  Ctrl+Z (Undo)  •  F11 (Fullscreen)",
            font=ctk.CTkFont(size=11), text_color="#707080"
        ).pack()

        ctk.CTkButton(
            frame, text="Get Started", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#3a86ff", hover_color=ACCENT_HOVER, height=38,
            command=self._finish
        ).pack(pady=(10, 15))

    def _finish(self):
        mark_first_time_complete()
        self.destroy()


class ScrollImageViewer(ctk.CTkFrame):
    """Zoomable image viewer with vertical/horizontal scrollbars."""

    def __init__(self, master, empty_text="Open an image to begin"):
        super().__init__(master, fg_color="transparent")
        self.zoom = 1.0
        self.source_image = None
        self._photo = None
        self._preview_base = None
        self._preview_key = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self, background="#121214", highlightthickness=0,
            xscrollincrement=20, yscrollincrement=20
        )
        self.vbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.hbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        self.empty_text = empty_text
        self._draw_empty()

        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
        self.canvas.bind("<Shift-MouseWheel>", self._horizontal_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._zoom_wheel)
        self.bind("<Configure>", lambda e: self._redraw())

    def clear(self):
        self.source_image = None
        self._photo = None
        self._draw_empty()

    def _draw_empty(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            300, 250, text=self.empty_text, fill="#555560",
            font=("Segoe UI", 15, "italic"), tags="empty"
        )

    def set_image(self, image, reset_zoom=False):
        self.source_image = image.copy()
        self._preview_base = None
        self._preview_key = None
        if reset_zoom:
            self.zoom = self.fit_zoom()
        self._redraw()

    def fit_zoom(self):
        if not self.source_image:
            return 1.0
        w = max(1, self.canvas.winfo_width() - 30)
        h = max(1, self.canvas.winfo_height() - 30)
        return max(0.05, min(w / self.source_image.width, h / self.source_image.height))

    def set_zoom(self, value, preserve_center=True):
        if not self.source_image:
            return
        old = self.zoom
        self.zoom = max(0.10, min(3.00, float(value)))
        self._redraw(preserve_center=preserve_center)
        return old

    def _redraw(self, preserve_center=True):
        if not self.source_image:
            return
        if self.winfo_width() <= 1 or self.winfo_height() <= 1:
            return

        self.canvas.delete("all")
        # Keep display RAM small: downscale large camera images before rendering.
        # The original source_image remains untouched for export/cropping.
        display_src = self.source_image
        if max(self.source_image.size) > 1800 and self.zoom <= 1.25:
            if self._preview_base is None:
                self._preview_base = self.source_image.copy()
                self._preview_base.thumbnail((1800, 1800), Image.Resampling.BILINEAR)
            display_src = self._preview_base
            scale_from_preview = 1.0
        else:
            scale_from_preview = 1.0
        w = max(1, int(display_src.width * self.zoom))
        h = max(1, int(display_src.height * self.zoom))
        preview = display_src.resize((w, h), Image.Resampling.BILINEAR if self.zoom <= 1.25 else Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(preview)

        cw = max(self.canvas.winfo_width(), w + 40)
        ch = max(self.canvas.winfo_height(), h + 40)
        self.canvas.configure(scrollregion=(0, 0, cw, ch))

        x = max(20, (cw - w) // 2)
        y = max(20, (ch - h) // 2)
        self.canvas.create_image(x, y, image=self._photo, anchor="nw")

    def _wheel(self, event):
        if event.state & 0x4:
            self._zoom_wheel(event)
        else:
            self.canvas.yview_scroll(-int(event.delta / 120) * 3, "units")

    def _horizontal_wheel(self, event):
        self.canvas.xview_scroll(-int(event.delta / 120) * 3, "units")

    def _zoom_wheel(self, event):
        factor = 1.10 if event.delta > 0 else 0.90
        self.set_zoom(self.zoom * factor)


class PassportPhotoStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — Professional Windows 11 Edition")
        self.geometry("1500x940")
        self.minsize(1100, 720)

        self.original_image = None
        self.processed_image = None
        self.a4_image = None
        self.history = []
        self.future = []
        self.bg_color = DEFAULT_BG
        self.dpi = DPI
        self.photo_preset = PRESETS[0]
        self.remove_service = RemoveBGService(configured_remove_bg_key())
        self.current_zoom = 1.0
        self.style_profile = None
        self.ai_style_profile = None
        self.crop_bot_profile = None
        self.crop_training_examples = []
        self.crop_training_file = os.path.join(CONFIG_DIR, "crop_training_examples.json")
        self.crop_bot_profile_file = os.path.join(CONFIG_DIR, "manual_crop_bot_profile.json")
        self.auto_apply_crop_bot = False
        self._load_crop_training_examples()
        self._load_crop_bot_profile()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-o>", lambda e: self.load_image())
        self.bind_all("<Control-s>", lambda e: self.save_photo())
        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())
        self.bind_all("<F11>", lambda e: self._toggle_fullscreen())
        # Hidden advanced style system: not exposed in the public sidebar.
        self.bind_all("<Control-Shift-Alt-T>", lambda e: self.open_style_trainer())
        self.bind_all("<Control-Shift-Alt-A>", lambda e: self.open_ai_style_learning())
        self.bind_all("<Control-Shift-Alt-D>", lambda e: self.open_advanced_detection())
        self.bind_all("<Control-Shift-Alt-M>", lambda e: self.open_manual_crop_trainer())

        try:
            self.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "app_icon.ico"))
        except Exception:
            pass

        self._build_gui()
        if self.crop_bot_profile:
            self.btn_apply_crop_bot.configure(state="normal")
            self.auto_crop_var.set(self.auto_apply_crop_bot)
            self.auto_crop_check.configure(state="normal")

        # Trigger first-time intro modal
        if is_first_time_user():
            self.after(300, lambda: FirstTimeOnboardingModal(self))

    def _load_crop_training_examples(self):
        try:
            with open(self.crop_training_file, "r", encoding="utf-8") as f:
                data=json.load(f)
            if isinstance(data,list): self.crop_training_examples=data[-100:]
        except Exception:
            self.crop_training_examples=[]

    def _load_crop_bot_profile(self):
        try:
            self.crop_bot_profile = load_crop_bot_profile(self.crop_bot_profile_file)
            self.auto_apply_crop_bot = bool(self.crop_bot_profile.get("auto_apply", False))
        except Exception:
            self.crop_bot_profile = None
            self.auto_apply_crop_bot = False

    def _save_crop_bot_profile(self):
        if not self.crop_bot_profile:
            return
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            self.crop_bot_profile["auto_apply"] = bool(self.auto_apply_crop_bot)
            save_crop_bot_profile(self.crop_bot_profile_file, self.crop_bot_profile)
        except Exception as e:
            print(f"Failed to save crop bot profile: {e}")

    def _save_crop_training_examples(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(self.crop_training_file, "w", encoding="utf-8") as f:
                json.dump(self.crop_training_examples[-100:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save crop training data: {e}")

    def _build_gui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.pane = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6, showhandle=False,
            bg="#0f1013", bd=0, relief="flat"
        )
        self.pane.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))

        self.side_container = tk.Frame(self.pane, bg="#0f1013")
        self.workspace_container = tk.Frame(self.pane, bg="#0f1013")

        self.side = ctk.CTkScrollableFrame(self.side_container, corner_radius=10, fg_color=SURFACE_2)
        self.side.pack(fill="both", expand=True)

        self.workspace = ctk.CTkFrame(self.workspace_container, corner_radius=10, fg_color=SURFACE_2)
        self.workspace.pack(fill="both", expand=True)

        self.pane.add(self.side_container, minsize=320, width=360)
        self.pane.add(self.workspace_container, minsize=650)

        self._build_sidebar()
        self._build_workspace()

        self.statusbar = ctk.CTkLabel(
            self, text="Ready • Open an image to start", anchor="w", text_color="#888898",
            height=28, font=ctk.CTkFont(size=11)
        )
        self.statusbar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))

    def _build_sidebar(self):
        side = self.side
        ctk.CTkLabel(
            side, text="PASSPORT PHOTO STUDIO",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT
        ).pack(pady=(12, 1))

        ctk.CTkLabel(
            side, text=f"v{APP_VERSION} • Windows 11 Professional",
            text_color="#707080", font=ctk.CTkFont(size=11)
        ).pack(pady=(0, 10))

        self.btn_load = ctk.CTkButton(
            side, text="＋  Open Photo   Ctrl+O", command=self.load_image,
            fg_color="#3a86ff", hover_color=ACCENT_HOVER, height=36,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.btn_load.pack(fill="x", padx=10, pady=4)

        self._separator(side)

        # Photo Preset Section
        self._section_title(side, "1. PHOTO SPECIFICATION")
        self.preset_var = ctk.StringVar(value=self.photo_preset.name)
        self.preset_menu = ctk.CTkOptionMenu(
            side, values=[p.name for p in PRESETS], variable=self.preset_var,
            command=lambda _: self._refresh_layout_info(), height=30
        )
        self.preset_menu.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(
            side, text=f"{len(PRESETS)-4} country presets + international standards • 300 DPI",
            text_color=TEXT_MUTED, font=ctk.CTkFont(size=9), anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 3))

        crop_row = ctk.CTkFrame(side, fg_color="transparent")
        crop_row.pack(fill="x", padx=10, pady=3)
        self.btn_crop = ctk.CTkButton(
            crop_row, text="✂️  Smart Passport Crop", command=self.crop_image, state="disabled", height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER
        )
        self.btn_crop.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_crop_guide = ctk.CTkButton(
            crop_row, text="▣ Guide", command=self.show_crop_guide, state="disabled", height=32,
            fg_color="#2b2b36"
        )
        self.btn_crop_guide.pack(side="left", fill="x", padx=(2, 0))
        self.btn_adjust_crop = ctk.CTkButton(
            side, text="✥ Adjustable Crop (Photoshop-style)", command=self.open_adjustable_crop, state="disabled", height=30,
            fg_color="#354052", hover_color="#43516a"
        )
        self.btn_adjust_crop.pack(fill="x", padx=10, pady=(1, 4))
        self.btn_passport_ready = ctk.CTkButton(
            side, text="⚡ Passport Ready — BG + Smart Crop", command=lambda: self.start_bg_removal(True),
            state="disabled", height=32, fg_color="#7b2cbf", hover_color="#5a189a"
        )
        self.btn_passport_ready.pack(fill="x", padx=10, pady=(1, 4))

        self._section_title(side, "1A. ADVANCED DETECTION & LEARNING")
        detect_row = ctk.CTkFrame(side, fg_color="transparent")
        detect_row.pack(fill="x", padx=10, pady=2)
        self.btn_advanced_detect = ctk.CTkButton(detect_row, text="🧠 Advanced Detect", command=self.open_advanced_detection, state="disabled", height=29, fg_color="#304a6e")
        self.btn_advanced_detect.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_crop_trainer = ctk.CTkButton(detect_row, text="🎯 Manual Train", command=self.open_manual_crop_trainer, state="disabled", height=29, fg_color="#304a6e")
        self.btn_crop_trainer.pack(side="left", expand=True, fill="x", padx=(2, 0))
        self.btn_crop_pdf = ctk.CTkButton(side, text="📘 Crop Learning Guide (PDF)", command=self.open_crop_learning_pdf, height=29, fg_color="#2b2b36")
        self.btn_crop_pdf.pack(fill="x", padx=10, pady=2)
        self.btn_apply_crop_bot = ctk.CTkButton(side, text="🤖 Apply Learned Crop Profile", command=self.apply_crop_bot_profile, state="disabled", height=29, fg_color="#6d28a8")
        self.btn_apply_crop_bot.pack(fill="x", padx=10, pady=(1, 2))
        self.auto_crop_var = tk.BooleanVar(value=self.auto_apply_crop_bot)
        self.auto_crop_check = ctk.CTkCheckBox(
            side, text="⚡ Auto-apply learned crop to new photos",
            variable=self.auto_crop_var, command=self._toggle_auto_crop_bot,
            text_color="#b9bfd0", font=ctk.CTkFont(size=11)
        )
        self.auto_crop_check.pack(fill="x", padx=12, pady=(0, 5))
        if not self.crop_bot_profile:
            self.auto_crop_check.configure(state="disabled")

        self._separator(side)

        # Background Controls
        self._section_title(side, "2. BACKGROUND & COLOR")
        self.btn_color = ctk.CTkButton(side, text="🎨  Select Background Color", command=self.choose_bg_color, height=30)
        self.btn_color.pack(fill="x", padx=10, pady=3)

        self.btn_rembg = ctk.CTkButton(
            side, text="✨  Auto Remove Background", command=self.start_bg_removal, state="disabled", height=30
        )
        self.btn_rembg.pack(fill="x", padx=10, pady=3)

        # Advanced style-learning system is intentionally hidden from the normal UI.
        # It remains available through private developer/user hotkeys.
        self.btn_style_trainer = None
        self.btn_apply_style = None
        self.btn_ai_style = None
        self.btn_apply_ai_style = None

        self._separator(side)

        # Photoshop-style Editor Tools
        self._section_title(side, "3. PHOTO EDITOR TOOLS")
        rotate_row = ctk.CTkFrame(side, fg_color="transparent")
        rotate_row.pack(fill="x", padx=10, pady=2)
        self.btn_rotate_l = ctk.CTkButton(rotate_row, text="⟲ Rotate L", command=lambda: self.rotate_photo(False), state="disabled", height=28, fg_color="#2b2b36")
        self.btn_rotate_l.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_rotate_r = ctk.CTkButton(rotate_row, text="⟳ Rotate R", command=lambda: self.rotate_photo(True), state="disabled", height=28, fg_color="#2b2b36")
        self.btn_rotate_r.pack(side="left", expand=True, fill="x", padx=(2, 0))

        flip_row = ctk.CTkFrame(side, fg_color="transparent")
        flip_row.pack(fill="x", padx=10, pady=2)
        self.btn_flip_h = ctk.CTkButton(flip_row, text="⇋ Flip H", command=lambda: self.flip_photo("h"), state="disabled", height=28, fg_color="#2b2b36")
        self.btn_flip_h.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_flip_v = ctk.CTkButton(flip_row, text="⇅ Flip V", command=lambda: self.flip_photo("v"), state="disabled", height=28, fg_color="#2b2b36")
        self.btn_flip_v.pack(side="left", expand=True, fill="x", padx=(2, 0))

        self.filter_var = ctk.StringVar(value=FILTER_PRESETS[0])
        self.filter_menu = ctk.CTkOptionMenu(side, values=FILTER_PRESETS, variable=self.filter_var, height=28)
        self.filter_menu.pack(fill="x", padx=10, pady=(6, 2))
        self.btn_apply_filter = ctk.CTkButton(
            side, text="🖼️  Apply Filter", command=self.apply_filter, state="disabled", height=28, fg_color="#2b2b36"
        )
        self.btn_apply_filter.pack(fill="x", padx=10, pady=2)

        tool_row = ctk.CTkFrame(side, fg_color="transparent")
        tool_row.pack(fill="x", padx=10, pady=2)
        self.btn_white_balance = ctk.CTkButton(tool_row, text="⚖️ Auto Color Fix", command=self.apply_white_balance, state="disabled", height=28, fg_color="#2b2b36")
        self.btn_white_balance.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_denoise = ctk.CTkButton(tool_row, text="🧹 Denoise", command=self.apply_denoise, state="disabled", height=28, fg_color="#2b2b36")
        self.btn_denoise.pack(side="left", expand=True, fill="x", padx=(2, 0))

        self._separator(side)

        # Professional Color & Portrait Tools
        self._section_title(side, "4. PRO COLOR & PORTRAIT")
        self.btn_auto_enhance = ctk.CTkButton(
            side, text="✦  Auto Enhance Portrait", command=self.apply_auto_enhance,
            state="disabled", height=30, fg_color=ACCENT, hover_color=ACCENT_HOVER
        )
        self.btn_auto_enhance.pack(fill="x", padx=10, pady=3)

        pro_grid = ctk.CTkFrame(side, fg_color="transparent")
        pro_grid.pack(fill="x", padx=10, pady=2)

        for label, attr, lo, hi, default in [
            ("Exposure", "Exposure", -1.5, 1.5, 0.0),
            ("Saturation", "Saturation", 0.0, 2.0, 1.0),
            ("Highlights", "Highlights", -1.0, 1.0, 0.0),
            ("Shadows", "Shadows", -1.0, 1.0, 0.0),
            ("Vignette", "Vignette", 0.0, 1.0, 0.0),
        ]:
            row = ctk.CTkFrame(pro_grid, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label, width=78, anchor="w",
                         font=ctk.CTkFont(size=10)).pack(side="left")
            slider = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=60, height=12)
            slider.set(default)
            slider.pack(side="left", fill="x", expand=True)
            setattr(self, f"pro_{attr.lower()}", slider)

        self.btn_apply_pro = ctk.CTkButton(
            side, text="Apply Pro Adjustments", command=self.apply_pro_adjustments,
            state="disabled", height=28, fg_color=SURFACE_3
        )
        self.btn_apply_pro.pack(fill="x", padx=10, pady=(3, 6))

        # Image Enhancements
        self._section_title(side, "5. QUICK RETOUCHING")
        self.sliders = {}
        for name, default, lo, hi in [
            ("Brightness", 1.03, 0.70, 1.40),
            ("Contrast", 1.05, 0.70, 1.40),
            ("Color", 1.04, 0.70, 1.40),
            ("Sharpness", 1.10, 0.70, 1.50),
            ("Smooth Skin", 0.10, 0.00, 0.50),
        ]:
            row = ctk.CTkFrame(side, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(row, text=name, width=95, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
            slider = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=50, height=14)
            slider.set(default)
            slider.pack(side="left", fill="x", expand=True)
            self.sliders[name] = slider

        self.btn_enhance = ctk.CTkButton(
            side, text="💎  Apply Retouching", command=self.apply_enhancement,
            state="disabled", fg_color="#7b2cbf", hover_color="#5a189a", height=32
        )
        self.btn_enhance.pack(fill="x", padx=10, pady=6)

        self.btn_reset = ctk.CTkButton(
            side, text="↺  Reset Image", command=self.reset_to_original, state="disabled", height=28, fg_color="#33333e"
        )
        self.btn_reset.pack(fill="x", padx=10, pady=2)

        self._separator(side)

        # Print & Layout Section
        self._section_title(side, "6. PRINT & A4 LAYOUT")
        self.qty = self._entry(side, "Quantity", str(DEFAULT_QUANTITY))
        self.per_line = self._entry(side, "Photos/Line", str(DEFAULT_PHOTOS_PER_LINE))
        self.margin_x = self._entry(side, "Margin X (mm)", str(DEFAULT_MARGIN_X_MM))
        self.margin_y = self._entry(side, "Margin Y (mm)", str(DEFAULT_MARGIN_Y_MM))
        self.gap_x = self._entry(side, "Gap X (mm)", str(DEFAULT_GAP_X_MM))
        self.gap_y = self._entry(side, "Gap Y (mm)", str(DEFAULT_GAP_Y_MM))
        self.border = self._entry(side, "Border (mm)", str(DEFAULT_BORDER_MM))

        self.center_last = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(side, text="Center incomplete last row", variable=self.center_last,
                        command=self._refresh_layout_info, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=4)

        self.layout_info = ctk.CTkLabel(side, text="A4: 5 per line • Ready", text_color=ACCENT, font=ctk.CTkFont(size=11), wraplength=300)
        self.layout_info.pack(fill="x", padx=10, pady=2)

        self.btn_a4 = ctk.CTkButton(
            side, text="🖨️  Generate A4 Print Sheet", command=self.generate_a4,
            state="disabled", fg_color="#2ec4b6", hover_color="#0f9f90", text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"), height=34
        )
        self.btn_a4.pack(fill="x", padx=10, pady=6)

        export_row = ctk.CTkFrame(side, fg_color="transparent")
        export_row.pack(fill="x", padx=10, pady=2)
        self.btn_save_photo = ctk.CTkButton(export_row, text="💾 Save Photo", command=self.save_photo, state="disabled", height=30)
        self.btn_save_photo.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_save_a4 = ctk.CTkButton(export_row, text="📄 Save A4", command=self.save_a4, state="disabled", height=30)
        self.btn_save_a4.pack(side="left", expand=True, fill="x", padx=(2, 0))

        self._separator(side)

        # Bottom Utilities
        nav_row = ctk.CTkFrame(side, fg_color="transparent")
        nav_row.pack(fill="x", padx=10, pady=2)

        self.btn_undo = ctk.CTkButton(nav_row, text="↶ Undo", command=self.undo, state="disabled", height=28, fg_color="#2b2b36")
        self.btn_undo.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.btn_redo = ctk.CTkButton(nav_row, text="↷ Redo", command=self.redo, state="disabled", height=28, fg_color="#2b2b36")
        self.btn_redo.pack(side="left", expand=True, fill="x", padx=(2, 0))

        ctk.CTkButton(
            side, text="⚙  Background API Settings", command=self.configure_api_key,
            height=28, fg_color="transparent", text_color=TEXT_MUTED
        ).pack(fill="x", padx=10, pady=(4, 1))

        ctk.CTkButton(side, text="❓ Help / Introduction", command=lambda: FirstTimeOnboardingModal(self), height=26, fg_color="transparent", text_color="#a0a0a0").pack(fill="x", padx=10, pady=(6, 12))

        self._a4_entries = [self.qty, self.per_line, self.margin_x, self.margin_y, self.gap_x, self.gap_y, self.border]
        for entry in self._a4_entries:
            entry.bind("<KeyRelease>", lambda e: self._refresh_layout_info())

        self._buttons = [
            self.btn_crop, self.btn_crop_guide, self.btn_passport_ready, self.btn_rembg, self.btn_enhance, self.btn_a4, self.btn_reset, self.btn_save_photo,
            self.btn_rotate_l, self.btn_rotate_r, self.btn_flip_h, self.btn_flip_v,
            self.btn_apply_filter, self.btn_white_balance, self.btn_denoise,
            self.btn_auto_enhance, self.btn_apply_pro,
            self.btn_advanced_detect, self.btn_crop_trainer, self.btn_apply_crop_bot        ]

    def _section_title(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT).pack(anchor="w", padx=10, pady=(6, 2))

    def _entry(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=1)
        ctk.CTkLabel(row, text=label, anchor="w", font=ctk.CTkFont(size=11)).pack(side="left")
        entry = ctk.CTkEntry(row, width=72, height=24, font=ctk.CTkFont(size=11))
        entry.insert(0, value)
        entry.pack(side="right")
        return entry

    def _separator(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color="#2b2b36").pack(fill="x", padx=10, pady=6)

    def _build_workspace(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(self.workspace, corner_radius=8, fg_color=SURFACE)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        toolbar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(toolbar, text="Workspace", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=10, pady=6)
        self.mode_label = ctk.CTkLabel(toolbar, text="Single Photo", text_color="#707080", font=ctk.CTkFont(size=11))
        self.mode_label.grid(row=0, column=1, padx=6)

        ctk.CTkButton(toolbar, text="Fit View", width=60, height=24, command=self.fit_current_view, fg_color="#2b2b36").grid(row=0, column=2, padx=2)
        ctk.CTkButton(toolbar, text="100%", width=50, height=24, command=lambda: self.set_current_zoom(1.0), fg_color="#2b2b36").grid(row=0, column=3, padx=2)

        ctk.CTkLabel(toolbar, text="Zoom", font=ctk.CTkFont(size=11)).grid(row=0, column=5, padx=(8, 2))
        self.zoom_slider = ctk.CTkSlider(toolbar, from_=0.10, to=3.00, number_of_steps=50, command=self._zoom_slider_changed, width=140, height=14)
        self.zoom_slider.set(1.0)
        self.zoom_slider.grid(row=0, column=6, padx=4)
        self.zoom_value = ctk.CTkLabel(toolbar, text="100%", width=40, font=ctk.CTkFont(size=11))
        self.zoom_value.grid(row=0, column=7, padx=(2, 6))

        self.tabs = ctk.CTkTabview(self.workspace, fg_color="transparent")
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self.photo_tab = self.tabs.add("Photo Workspace")
        self.a4_tab = self.tabs.add("A4 Print Preview")

        self.photo_viewer = ScrollImageViewer(self.photo_tab, "Open a photo to begin editing")
        self.photo_viewer.pack(expand=True, fill="both", padx=2, pady=2)

        self.a4_viewer = ScrollImageViewer(self.a4_tab, "Generate an A4 sheet layout to preview")
        self.a4_viewer.pack(expand=True, fill="both", padx=2, pady=2)

        self.a4_header = ctk.CTkLabel(self.a4_tab, text="A4 Layout Preview", font=ctk.CTkFont(size=14, weight="bold"))
        self.a4_header.place(relx=0.5, y=6, anchor="n")

        self.tabs.configure(command=self._tab_changed)

    def _tab_changed(self):
        self.mode_label.configure(text=self.tabs.get())
        viewer = self.a4_viewer if self.tabs.get() == "A4 Print Preview" else self.photo_viewer
        self.zoom_slider.set(viewer.zoom)
        self.zoom_value.configure(text=f"{round(viewer.zoom*100)}%")

    def _current_viewer(self):
        return self.a4_viewer if self.tabs.get() == "A4 Print Preview" else self.photo_viewer

    def _zoom_slider_changed(self, value):
        viewer = self._current_viewer()
        viewer.set_zoom(float(value))
        self.zoom_value.configure(text=f"{round(float(value)*100)}%")

    def set_current_zoom(self, value):
        viewer = self._current_viewer()
        viewer.set_zoom(value)
        self.zoom_slider.set(viewer.zoom)
        self.zoom_value.configure(text=f"{round(viewer.zoom*100)}%")

    def fit_current_view(self):
        viewer = self._current_viewer()
        viewer.set_zoom(viewer.fit_zoom())
        self.zoom_slider.set(viewer.zoom)
        self.zoom_value.configure(text=f"{round(viewer.zoom*100)}%")

    def _refresh_layout_info(self):
        if not self.processed_image:
            self.layout_info.configure(text="A4: Open a photo first.")
            return
        try:
            cols = int(self.per_line.get())
            mx = float(self.margin_x.get())
            my = float(self.margin_y.get())
            gx = float(self.gap_x.get())
            gy = float(self.gap_y.get())
            border = float(self.border.get())
            layout = calculate_a4_layout(
                self.processed_image, self.dpi, mx, my, gx, gy, border, cols
            )
            qty = int(self.qty.get())
            self.layout_info.configure(
                text=f"A4: {cols} cols × {layout['rows']} rows • capacity {layout['capacity']} • requested {qty}"
            )
        except Exception as e:
            self.layout_info.configure(text=f"Layout config error: {e}")

    def _set_ready_buttons(self):
        active = self.processed_image is not None
        for b in self._buttons:
            b.configure(state="normal" if active else "disabled")
        self.btn_undo.configure(state="normal" if len(self.history) > 0 else "disabled")
        self.btn_redo.configure(state="normal" if len(self.future) > 0 else "disabled")
        self.btn_save_a4.configure(state="normal" if self.a4_image else "disabled")

    def _toggle_auto_crop_bot(self):
        self.auto_apply_crop_bot = bool(self.auto_crop_var.get())
        if self.crop_bot_profile:
            self._save_crop_bot_profile()
        self.set_status("Learned crop auto-apply: ON" if self.auto_apply_crop_bot else "Learned crop auto-apply: OFF")

    def set_status(self, text):
        self.statusbar.configure(text=text)

    def selected_preset(self):
        for p in PRESETS:
            if p.name == self.preset_var.get():
                return p
        return PRESETS[0]

    def push_history(self):
        if self.processed_image:
            self.history.append(self.processed_image.copy())
            if len(self.history) > MAX_HISTORY:
                self.history.pop(0)
            self.future.clear()
            self._set_ready_buttons()

    def load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        try:
            image = Image.open(path).convert("RGB")
            self.original_image = image
            self.processed_image = image.copy()
            self.a4_image = None
            self.history.clear()
            self.future.clear()

            self.photo_viewer.set_image(image, reset_zoom=True)
            self.tabs.set("Photo Workspace")
            self._tab_changed()
            self._refresh_layout_info()
            self.set_status(f"Loaded: {os.path.basename(path)} ({image.width}×{image.height}px)")
            self._set_ready_buttons()
            # If the user trained a crop template once and enabled auto-apply,
            # reuse that exact composition on every newly opened photo. Detection
            # runs in the existing background worker so the UI stays responsive.
            if self.crop_bot_profile and self.auto_apply_crop_bot:
                self.after(80, self.crop_image)
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def crop_image(self):
        if not self.processed_image or getattr(self, "_busy", False):
            return
        try:
            self._busy = True
            self.push_history()
            p = self.selected_preset()
            src = self.processed_image.copy()
            self.set_status("⚡ Smart crop analyzing… (low-CPU mode)")
            for b in (self.btn_crop, self.btn_advanced_detect, self.btn_crop_trainer, self.btn_adjust_crop):
                b.configure(state="disabled")

            def worker():
                try:
                    out, analysis = smart_passport_crop(src, p.width_mm, p.height_mm, self.dpi, self.crop_bot_profile)
                    self.after(0, lambda: self._finish_smart_crop(out, analysis, p))
                except Exception as exc:
                    self.after(0, lambda: self._finish_processing_error("Smart Crop Error", exc))
            threading.Thread(target=worker, daemon=True, name="PPS-SmartCrop").start()
        except Exception as e:
            self._busy = False
            messagebox.showerror("Smart Crop Error", str(e))

    def _finish_smart_crop(self, out, analysis, p):
        self._busy = False
        self.processed_image = out
        self.photo_viewer.set_image(out, reset_zoom=True)
        face_text = "face detected" if analysis.face else "center fallback"
        self.set_status(f"Smart crop complete • {p.width_mm:g}×{p.height_mm:g} mm @ {self.dpi} DPI • {face_text} • framing {analysis.score}/100")
        self._refresh_layout_info(); self._set_ready_buttons()

    def _finish_processing_error(self, title, exc):
        self._busy = False
        self._set_ready_buttons()
        messagebox.showerror(title, str(exc))

    def open_adjustable_crop(self):
        """Photoshop-style interactive crop: move, resize from 8 handles, lock passport ratio."""
        if not self.processed_image or getattr(self, "_busy", False): return
        try:
            img = self.processed_image.copy()
            p = self.selected_preset(); target_ratio = p.width_mm / p.height_mm
            dialog = ctk.CTkToplevel(self); dialog.title("Adjustable Crop • Photoshop-style"); dialog.geometry("1100x780"); dialog.transient(self); dialog.grab_set()
            root = ctk.CTkFrame(dialog, fg_color=SURFACE_2, corner_radius=14); root.pack(expand=True, fill="both", padx=10, pady=10)
            ctk.CTkLabel(root, text=f"✥ Adjustable Crop • {p.width_mm:g}×{p.height_mm:g} mm", font=ctk.CTkFont(size=19, weight="bold"), text_color=ACCENT).pack(pady=(10,2))
            ctk.CTkLabel(root, text="Drag inside to move • drag corners/edges to resize • lock ratio for passport output • mouse wheel zoom", text_color=TEXT_MUTED).pack(pady=(0,8))
            body = ctk.CTkFrame(root, fg_color="transparent"); body.pack(expand=True, fill="both", padx=8); body.grid_columnconfigure(0,weight=1); body.grid_rowconfigure(0,weight=1)
            canvas = tk.Canvas(body, background="#0f1014", highlightthickness=0, cursor="crosshair"); canvas.grid(row=0,column=0,sticky="nsew")
            side = ctk.CTkFrame(body, width=230, fg_color="#1b1d23", corner_radius=10); side.grid(row=0,column=1,sticky="ns",padx=(8,0)); side.grid_propagate(False)
            lock_var=tk.BooleanVar(value=True); show_grid=tk.BooleanVar(value=True); zoom_var=tk.DoubleVar(value=1.0)
            state={"img":img,"scale":1.0,"ox":0,"oy":0,"photo":None,"rect":None,"drag":None,"start":None,"last":None,"zoom":1.0}

            def fit_rect():
                iw,ih=img.size; h=ih*0.82; w=h*target_ratio
                if w>iw*.88: w=iw*.88; h=w/target_ratio
                if h>ih*.88: h=ih*.88; w=h*target_ratio
                l=(iw-w)/2; t=(ih-h)*.28
                return [l,t,l+w,t+h]
            state["rect"]=fit_rect()

            def render():
                cw=max(600,canvas.winfo_width()-10); ch=max(500,canvas.winfo_height()-10);
                base=min(cw/img.width,ch/img.height,1.0)*state["zoom"]; state["scale"]=base
                dw=max(1,int(img.width*base)); dh=max(1,int(img.height*base)); disp=img.resize((dw,dh),Image.Resampling.BILINEAR)
                state["photo"]=ImageTk.PhotoImage(disp); canvas.delete("all"); state["ox"]=(canvas.winfo_width()-dw)//2; state["oy"]=(canvas.winfo_height()-dh)//2; canvas.create_image(state["ox"],state["oy"],anchor="nw",image=state["photo"])
                l,t,r,b=state["rect"]; X=lambda q:state["ox"]+q*base; Y=lambda q:state["oy"]+q*base
                # dark overlay outside crop
                canvas.create_rectangle(state["ox"],state["oy"],state["ox"]+dw,state["oy"]+dh,fill="",outline="")
                canvas.create_rectangle(state["ox"],state["oy"],X(l),state["oy"]+dh,fill="#000000",stipple="gray50",outline="")
                canvas.create_rectangle(X(r),state["oy"],state["ox"]+dw,state["oy"]+dh,fill="#000000",stipple="gray50",outline="")
                canvas.create_rectangle(X(l),state["oy"],X(r),Y(t),fill="#000000",stipple="gray50",outline="")
                canvas.create_rectangle(X(l),Y(b),X(r),state["oy"]+dh,fill="#000000",stipple="gray50",outline="")
                canvas.create_rectangle(X(l),Y(t),X(r),Y(b),outline="#ffffff",width=2)
                if show_grid.get():
                    for frac in (1/3,2/3): canvas.create_line(X(l),Y(t+(b-t)*frac),X(r),Y(t+(b-t)*frac),fill="#ffffff",dash=(4,5)); canvas.create_line(X(l+(r-l)*frac),Y(t),X(l+(r-l)*frac),Y(b),fill="#ffffff",dash=(4,5))
                hs=6
                pts=[(l,t),( (l+r)/2,t),(r,t),(r,(t+b)/2),(r,b),((l+r)/2,b),(l,b),(l,(t+b)/2)]
                for qx,qy in pts: canvas.create_rectangle(X(qx)-hs,Y(qy)-hs,X(qx)+hs,Y(qy)+hs,fill="#ffffff",outline="#202228")
                canvas.create_text(X(l)+8,Y(t)+8,anchor="nw",text=f"{int(r-l)}×{int(b-t)} px",fill="#ffffff")

            def to_img(e): return ((e.x-state["ox"])/state["scale"],(e.y-state["oy"])/state["scale"])
            def hit(e):
                x,y=to_img(e); l,t,r,b=state["rect"]; tol=max(12/state["scale"],8)
                pts={"nw":(l,t),"n":((l+r)/2,t),"ne":(r,t),"e":(r,(t+b)/2),"se":(r,b),"s":((l+r)/2,b),"sw":(l,b),"w":(l,(t+b)/2)}
                for k,(px,py) in pts.items():
                    if abs(x-px)<=tol and abs(y-py)<=tol:return k
                if l<=x<=r and t<=y<=b:return "move"
                return None
            def constrain(l,t,r,b,handle):
                iw,ih=img.size; minw=max(80,iw*.05); minh=max(80,ih*.05)
                if lock_var.get():
                    # Resize around the opposite corner/edge while preserving passport ratio.
                    if handle in ("nw","n","ne","e","se","s","sw","w"):
                        cx=(l+r)/2; cy=(t+b)/2; w=max(minw,r-l); h=w/target_ratio
                        # Use the changed rectangle's center, then clamp.
                        if h<minh: h=minh; w=h*target_ratio
                        l=cx-w/2; r=cx+w/2; t=cy-h/2; b=cy+h/2
                l=max(0,min(iw-1,l)); r=max(l+1,min(iw,r)); t=max(0,min(ih-1,t)); b=max(t+1,min(ih,b))
                if lock_var.get():
                    w=r-l; h=w/target_ratio
                    if h>ih: h=ih*.96; w=h*target_ratio
                    if w>iw: w=iw*.96; h=w/target_ratio
                    cx=(l+r)/2; cy=(t+b)/2; l=max(0,cx-w/2); r=min(iw,cx+w/2); t=max(0,cy-h/2); b=min(ih,cy+h/2)
                return [l,t,r,b]
            def down(e):
                h=hit(e); state["drag"]=h; state["last"]=to_img(e)
            def move(e):
                if not state["drag"]: return
                x,y=to_img(e); lx,ly=state["last"]; dx=x-lx; dy=y-ly; l,t,r,b=state["rect"]; h=state["drag"]
                if h=="move": l+=dx; r+=dx; t+=dy; b+=dy
                else:
                    if "w" in h:l+=dx
                    if "e" in h:r+=dx
                    if "n" in h:t+=dy
                    if "s" in h:b+=dy
                if lock_var.get() and h!="move":
                    # Preserve ratio using the dragged dimension.
                    if h in ("e","w"): b=t+(r-l)/target_ratio
                    elif h in ("n","s"): r=l+(b-t)*target_ratio
                    else:
                        w=abs(r-l); hh=w/target_ratio; b=t+hh if "n" in h else b; t=b-hh if "s" in h else t
                        if "nw" in h: t=b-hh; l=r-w
                        elif "ne" in h: t=b-hh
                        elif "sw" in h: l=r-w
                        elif "se" in h: b=t+hh
                state["rect"]=constrain(l,t,r,b,h); state["last"]=(x,y); render()
            def up(e): state["drag"]=None
            canvas.bind("<ButtonPress-1>",down); canvas.bind("<B1-Motion>",move); canvas.bind("<ButtonRelease-1>",up)
            canvas.bind("<MouseWheel>",lambda e: (setattr(state,"x",0), None) if False else wheel(e))
            def wheel(e):
                state["zoom"]=max(.55,min(2.5,state["zoom"]*(1.08 if e.delta>0 else .92))); zoom_var.set(state["zoom"]); render()
            canvas.bind("<MouseWheel>",wheel)
            canvas.bind("<Configure>",lambda e:render())

            ctk.CTkCheckBox(side,text="Lock passport ratio",variable=lock_var).pack(fill="x",padx=12,pady=(16,7))
            ctk.CTkCheckBox(side,text="Rule-of-thirds grid",variable=show_grid,command=render).pack(fill="x",padx=12,pady=7)
            ctk.CTkLabel(side,text="Zoom",text_color=TEXT_MUTED).pack(anchor="w",padx=12,pady=(15,2))
            ctk.CTkSlider(side,from_=0.55,to=2.5,variable=zoom_var,command=lambda v:(state.update(zoom=float(v)),render())).pack(fill="x",padx=12,pady=3)
            ctk.CTkButton(side,text="↺ Reset Crop",command=lambda:(state.update(rect=fit_rect()),render()),height=32).pack(fill="x",padx=12,pady=(18,5))
            ctk.CTkButton(side,text="Auto Detect → Adjust",command=lambda:self._auto_adjust_in_dialog(state,render),height=32,fg_color="#304a6e").pack(fill="x",padx=12,pady=5)
            def apply():
                l,t,r,b=map(lambda v:int(round(v)),state["rect"]);
                if r-l<20 or b-t<20:return
                self.push_history(); crop=img.crop((l,t,r,b)).resize((round(p.width_mm/25.4*self.dpi),round(p.height_mm/25.4*self.dpi)),Image.Resampling.LANCZOS); crop.info["dpi"]=(self.dpi,self.dpi); self.processed_image=crop; self.photo_viewer.set_image(crop,reset_zoom=True); self._refresh_layout_info(); self._set_ready_buttons(); self.set_status(f"Adjustable crop applied • {p.width_mm:g}×{p.height_mm:g} mm @ {self.dpi} DPI"); dialog.destroy()
            ctk.CTkButton(side,text="✓ Apply Crop",command=apply,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER).pack(fill="x",padx=12,pady=(22,5))
            ctk.CTkButton(side,text="Cancel",command=dialog.destroy,height=32,fg_color="#2b2b36").pack(fill="x",padx=12,pady=4)
            render()
        except Exception as e: messagebox.showerror("Adjustable Crop",str(e))

    def _auto_adjust_in_dialog(self,state,render):
        if getattr(self,"_busy",False): return
        self._busy=True; src=state["img"].copy(); p=self.selected_preset()
        def worker():
            try:
                analysis=analyze_crop(src,p.width_mm,p.height_mm,self.crop_bot_profile)
                self.after(0,lambda:self._apply_detected_rect_to_dialog(state,render,analysis))
            except Exception as exc:
                self.after(0,lambda:messagebox.showerror("Auto Detection",str(exc)))
            finally:
                self.after(0,lambda:setattr(self,"_busy",False))
        threading.Thread(target=worker,daemon=True,name="PPS-DialogDetect").start()

    def _apply_detected_rect_to_dialog(self,state,render,analysis):
        state["rect"]=list(map(float,analysis.rect)); render(); self.set_status(f"Auto detection complete • framing {analysis.score}/100 — adjust handles if needed.")

    def show_crop_guide(self):
        if not self.processed_image:
            return
        try:
            p = self.selected_preset()
            analysis = analyze_crop(self.processed_image, p.width_mm, p.height_mm, self.crop_bot_profile)
            guide = draw_crop_guide(self.processed_image, analysis)

            dialog = ctk.CTkToplevel(self)
            dialog.title("Smart Passport Crop Guide")
            dialog.geometry("900x760")
            dialog.transient(self)
            dialog.grab_set()

            frame = ctk.CTkFrame(dialog, fg_color=SURFACE_2, corner_radius=14)
            frame.pack(expand=True, fill="both", padx=12, pady=12)
            ctk.CTkLabel(
                frame, text=f"Smart Crop Guide • {analysis.score}/100",
                font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT
            ).pack(pady=(12, 2))
            ctk.CTkLabel(
                frame, text=analysis.message, text_color=TEXT_MUTED
            ).pack(pady=(0, 8))

            viewer = ScrollImageViewer(frame, "")
            viewer.pack(expand=True, fill="both", padx=8, pady=8)
            viewer.set_image(guide, reset_zoom=True)

            face_state = "Detected" if analysis.face else "Not detected"
            info = (
                f"Face: {face_state}   •   Head top: {analysis.head_top_ratio*100:.1f}%   •   "
                f"Face height: {analysis.face_ratio*100:.1f}%   •   Center offset: {analysis.center_offset_ratio*100:.1f}%"
            )
            ctk.CTkLabel(frame, text=info, text_color="#b6bac6", font=ctk.CTkFont(size=10)).pack(pady=(0, 8))
            ctk.CTkButton(
                frame, text="Use This Crop", command=lambda: (dialog.destroy(), self.crop_image()),
                fg_color=ACCENT, hover_color=ACCENT_HOVER, height=34
            ).pack(fill="x", padx=14, pady=(0, 12))
        except Exception as e:
            messagebox.showerror("Crop Guide Error", str(e))

    def open_advanced_detection(self):
        if not self.processed_image or getattr(self,"_busy",False): return
        dialog=ctk.CTkToplevel(self); dialog.title("Advanced Detection Ensemble"); dialog.geometry("780x660"); dialog.transient(self); dialog.grab_set()
        frame=ctk.CTkFrame(dialog,fg_color=SURFACE_2,corner_radius=14); frame.pack(expand=True,fill="both",padx=12,pady=12)
        ctk.CTkLabel(frame,text="🧠 Advanced Detection Ensemble",font=ctk.CTkFont(size=20,weight="bold"),text_color=ACCENT).pack(pady=(14,2))
        status=ctk.CTkLabel(frame,text="Analyzing in background… UI remains responsive.",text_color=TEXT_MUTED); status.pack(pady=(0,8))
        viewer=ScrollImageViewer(frame,""); viewer.pack(expand=True,fill="both",padx=8,pady=8)
        info=ctk.CTkLabel(frame,text="Low-end mode: compact detection image • HOG disabled",text_color="#c3c8d4",justify="left",wraplength=700); info.pack(padx=14,pady=6)
        notes=ctk.CTkLabel(frame,text="",text_color=TEXT_MUTED,justify="left"); notes.pack(fill="x",padx=18,pady=4)
        btn=ctk.CTkButton(frame,text="Use Advanced Smart Crop",state="disabled",command=lambda:(dialog.destroy(),self.crop_image()),fg_color=ACCENT,hover_color=ACCENT_HOVER,height=34); btn.pack(fill="x",padx=14,pady=(6,12))
        src=self.processed_image.copy(); p=self.selected_preset(); self._busy=True
        def worker():
            try:
                det=detect_advanced(src,use_hog=False); analysis=analyze_crop(src,p.width_mm,p.height_mm,self.crop_bot_profile); guide=draw_crop_guide(src,analysis)
                self.after(0,lambda:finish(det,analysis,guide))
            except Exception as exc:
                self.after(0,lambda:fail(exc))
        def finish(det,analysis,guide):
            self._busy=False; viewer.set_image(guide,reset_zoom=True); status.configure(text="Detection complete • ready to adjust or apply")
            info.configure(text=f"Confidence: {det.confidence*100:.0f}%  • Face: {'Detected' if det.face else 'Not detected'}  • Eyes: {len(det.eyes)}  • Person cross-check: {'On' if det.person else 'Off'}  • Shoulders: {'Estimated' if det.shoulder_box else 'No'}\nCrop score: {analysis.score}/100 • Mode: {analysis.crop_mode}\nRAM/CPU mode: compact OpenCV detection; heavy HOG disabled")
            notes.configure(text="\n".join("• "+n for n in det.notes) or "• Fallback crop will be used."); btn.configure(state="normal")
        def fail(exc):
            self._busy=False; dialog.destroy(); messagebox.showerror("Advanced Detection",str(exc))
        threading.Thread(target=worker,daemon=True,name="PPS-AdvancedDetect").start()

    def open_crop_learning_pdf(self):
        pdf=os.path.join(os.path.dirname(os.path.dirname(__file__)),"docs","CROP_LEARNING_GUIDE.pdf")
        if not os.path.isfile(pdf): messagebox.showerror("Crop Learning Guide","The bundled PDF guide was not found."); return
        try: os.startfile(pdf); self.set_status("Opened Crop Learning Guide PDF.")
        except Exception as e: messagebox.showerror("Crop Learning Guide",str(e))

    def open_manual_crop_trainer(self):
        """Photoshop-like manual crop editor used for training examples.

        The training rectangle is stored in ORIGINAL IMAGE coordinates.  The user can
        move it, resize from 8 handles, lock the passport aspect ratio, zoom and pan.
        Auto detection is optional and never overwrites a manually adjusted crop unless
        the user explicitly presses Auto Detect -> Adjust.
        """
        if not self.processed_image:
            return
        try:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Manual Crop Training Bot • Photoshop-style Crop")
            dialog.geometry("1180x820")
            dialog.minsize(900, 650)
            dialog.transient(self)
            dialog.grab_set()

            root = ctk.CTkFrame(dialog, fg_color=SURFACE_2, corner_radius=14)
            root.pack(expand=True, fill="both", padx=10, pady=10)
            ctk.CTkLabel(
                root, text="🎯 Manual Crop Training Bot",
                font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT
            ).pack(pady=(10, 2))
            ctk.CTkLabel(
                root,
                text="Adjust the crop like Photoshop. Save the exact framing you want; the bot learns composition from your saved examples.",
                text_color=TEXT_MUTED
            ).pack(pady=(0, 8))

            work = ctk.CTkFrame(root, fg_color="transparent")
            work.pack(expand=True, fill="both", padx=8, pady=5)
            work.grid_columnconfigure(0, weight=1)
            work.grid_rowconfigure(0, weight=1)

            canvas = tk.Canvas(work, background="#0d0f13", highlightthickness=0, cursor="crosshair")
            canvas.grid(row=0, column=0, sticky="nsew")
            panel = ctk.CTkFrame(work, fg_color="#1b1d23", corner_radius=10, width=255)
            panel.grid(row=0, column=1, sticky="ns", padx=(8, 0))
            panel.grid_propagate(False)

            pset = self.selected_preset()
            target_ratio = float(pset.width_mm / pset.height_mm)
            state = {
                "image": self.processed_image.copy(),
                "path": None,
                "rect": None,            # ORIGINAL image coordinates: l,t,r,b
                "scale": 1.0,
                "ox": 0.0,
                "oy": 0.0,
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
                "photo": None,
                "drag": None,
                "last_img": None,
                "pan_start": None,
                "pan_origin": None,
                "render_job": None,
                "cursor_handle": None,
            }
            examples = list(self.crop_training_examples)
            lock_var = tk.BooleanVar(value=True)
            grid_var = tk.BooleanVar(value=True)
            zoom_var = tk.DoubleVar(value=1.0)
            count_var = tk.StringVar(value=f"Training examples: {len(examples)}")
            size_var = tk.StringVar(value="Crop: —")
            pos_var = tk.StringVar(value="Position: —")

            ctk.CTkLabel(
                panel, textvariable=count_var, text_color=ACCENT,
                font=ctk.CTkFont(size=13, weight="bold")
            ).pack(pady=(14, 6))
            ctk.CTkLabel(
                panel,
                text="PHOTOSHOP CROP MODE\nDrag inside = Move\n8 handles = Resize\nLock 38×48 ratio = ON\nWheel = Zoom • Middle drag = Pan\nSave = exact training target",
                text_color=TEXT_MUTED, justify="left", wraplength=225
            ).pack(padx=12, pady=(0, 8))

            ctk.CTkCheckBox(panel, text="Lock passport ratio", variable=lock_var, command=lambda: render()).pack(fill="x", padx=12, pady=5)
            ctk.CTkCheckBox(panel, text="Rule-of-thirds grid", variable=grid_var, command=lambda: render()).pack(fill="x", padx=12, pady=5)
            ctk.CTkLabel(panel, textvariable=size_var, text_color="#d7dbe5").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(panel, textvariable=pos_var, text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=1)

            ctk.CTkLabel(panel, text="Zoom", text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(12, 2))
            ctk.CTkSlider(
                panel, from_=0.5, to=3.0, variable=zoom_var,
                command=lambda v: set_zoom(float(v))
            ).pack(fill="x", padx=12, pady=2)

            def initial_rect(img):
                iw, ih = img.size
                h = ih * 0.62
                w = h * target_ratio
                if w > iw * 0.82:
                    w = iw * 0.82
                    h = w / target_ratio
                if h > ih * 0.82:
                    h = ih * 0.82
                    w = h * target_ratio
                cx = iw * 0.5
                top = ih * 0.14
                if top + h > ih:
                    top = max(0, (ih - h) * 0.5)
                return [cx - w / 2, top, cx + w / 2, top + h]

            state["rect"] = initial_rect(state["image"])

            def set_zoom(v, anchor=None):
                old = state["zoom"]
                state["zoom"] = max(0.5, min(3.0, float(v)))
                zoom_var.set(state["zoom"])
                if anchor is not None and old > 0:
                    # Keep the image point under the mouse stable while zooming.
                    ax, ay = anchor
                    state["pan_x"] += (ax - state["pan_x"]) * (1.0 - old / state["zoom"])
                    state["pan_y"] += (ay - state["pan_y"]) * (1.0 - old / state["zoom"])
                render()

            def image_to_canvas(x, y):
                return state["ox"] + x * state["scale"], state["oy"] + y * state["scale"]

            def canvas_to_image(x, y):
                sc = max(1e-6, state["scale"])
                return (x - state["ox"]) / sc, (y - state["oy"]) / sc

            def fit_view():
                img = state["image"]
                cw = max(400, canvas.winfo_width() - 20)
                ch = max(400, canvas.winfo_height() - 20)
                fit = min(cw / max(1, img.width), ch / max(1, img.height), 1.0)
                state["scale"] = fit * state["zoom"]
                dw = img.width * state["scale"]
                dh = img.height * state["scale"]
                state["ox"] = (canvas.winfo_width() - dw) / 2 + state["pan_x"]
                state["oy"] = (canvas.winfo_height() - dh) / 2 + state["pan_y"]

            def render():
                # Avoid expensive repeated renders during rapid mouse motion.
                if state["render_job"] is not None:
                    try:
                        dialog.after_cancel(state["render_job"])
                    except Exception:
                        pass
                state["render_job"] = dialog.after(8, _render_now)

            def _render_now():
                state["render_job"] = None
                if not dialog.winfo_exists():
                    return
                img = state["image"]
                fit_view()
                sc = state["scale"]
                dw = max(1, int(img.width * sc))
                dh = max(1, int(img.height * sc))
                # Preview only; original image remains untouched.
                resample = Image.Resampling.BILINEAR if sc < 1.0 else Image.Resampling.BICUBIC
                disp = img.resize((dw, dh), resample)
                state["photo"] = ImageTk.PhotoImage(disp)
                canvas.delete("all")
                canvas.create_image(state["ox"], state["oy"], anchor="nw", image=state["photo"])

                l, t, r, b = state["rect"]
                X, Y = image_to_canvas, image_to_canvas
                x1, y1 = X(l, t)
                x2, y2 = X(r, b)
                iw, ih = img.size
                ix0, iy0 = state["ox"], state["oy"]
                ix1, iy1 = state["ox"] + iw * sc, state["oy"] + ih * sc

                # Outside-crop dim overlay.
                overlay = "#000000"
                if x1 > ix0:
                    canvas.create_rectangle(ix0, iy0, x1, iy1, fill=overlay, stipple="gray50", outline="")
                if x2 < ix1:
                    canvas.create_rectangle(x2, iy0, ix1, iy1, fill=overlay, stipple="gray50", outline="")
                if y1 > iy0:
                    canvas.create_rectangle(x1, iy0, x2, y1, fill=overlay, stipple="gray50", outline="")
                if y2 < iy1:
                    canvas.create_rectangle(x1, y2, x2, iy1, fill=overlay, stipple="gray50", outline="")

                canvas.create_rectangle(x1, y1, x2, y2, outline="#ffffff", width=2)
                canvas.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, outline="#2f8cff", width=1)
                if grid_var.get():
                    for frac in (1/3, 2/3):
                        gx = x1 + (x2 - x1) * frac
                        gy = y1 + (y2 - y1) * frac
                        canvas.create_line(gx, y1, gx, y2, fill="#ffffff", dash=(5, 5))
                        canvas.create_line(x1, gy, x2, gy, fill="#ffffff", dash=(5, 5))

                # Photoshop-style 8 handles.
                pts = [
                    ("nw", l, t), ("n", (l+r)/2, t), ("ne", r, t),
                    ("e", r, (t+b)/2), ("se", r, b), ("s", (l+r)/2, b),
                    ("sw", l, b), ("w", l, (t+b)/2),
                ]
                hs = max(5, min(9, 7 * sc))
                for name, px, py in pts:
                    cx, cy = X(px, py)
                    if name in ("n", "s"):
                        hw, hh = hs * 1.6, hs
                    elif name in ("e", "w"):
                        hw, hh = hs, hs * 1.6
                    else:
                        hw = hh = hs
                    canvas.create_rectangle(cx-hw, cy-hh, cx+hw, cy+hh, fill="#ffffff", outline="#1d4f91", width=1)

                size_var.set(f"Crop: {int(round(r-l))} × {int(round(b-t))} px")
                pos_var.set(f"Position: {int(round(l))}, {int(round(t))}")

            def clamp_rect(rect):
                iw, ih = state["image"].size
                l, t, r, b = rect
                min_w = max(40.0, iw * 0.03)
                min_h = max(40.0, ih * 0.03)
                if lock_var.get():
                    # Keep the rectangle at the target ratio and inside the image.
                    w = max(min_w, r-l)
                    h = w / target_ratio
                    if h < min_h:
                        h = min_h
                        w = h * target_ratio
                    if w > iw:
                        w = iw * 0.98
                        h = w / target_ratio
                    if h > ih:
                        h = ih * 0.98
                        w = h * target_ratio
                    cx, cy = (l+r)/2, (t+b)/2
                    l, r = cx-w/2, cx+w/2
                    t, b = cy-h/2, cy+h/2
                else:
                    l, r = sorted((l, r))
                    t, b = sorted((t, b))
                    r = max(r, l + min_w)
                    b = max(b, t + min_h)
                if r > iw:
                    shift = r-iw; l-=shift; r-=shift
                if l < 0:
                    shift = -l; l+=shift; r+=shift
                if b > ih:
                    shift = b-ih; t-=shift; b-=shift
                if t < 0:
                    shift = -t; t+=shift; b+=shift
                # Final clamp for numerical edge cases.
                l=max(0.0,min(iw-1.0,l)); t=max(0.0,min(ih-1.0,t))
                r=max(l+1.0,min(float(iw),r)); b=max(t+1.0,min(float(ih),b))
                return [l,t,r,b]

            def hit_test(e):
                x, y = canvas_to_image(e.x, e.y)
                l, t, r, b = state["rect"]
                tol = max(10.0 / max(state["scale"], 0.05), 7.0)
                handles = {
                    "nw": (l,t), "n": ((l+r)/2,t), "ne": (r,t),
                    "e": (r,(t+b)/2), "se": (r,b), "s": ((l+r)/2,b),
                    "sw": (l,b), "w": (l,(t+b)/2),
                }
                for name,(px,py) in handles.items():
                    if abs(x-px) <= tol and abs(y-py) <= tol:
                        return name
                if l <= x <= r and t <= y <= b:
                    return "move"
                return None

            def resize_from_handle(rect, handle, x, y):
                l,t,r,b = rect
                iw,ih = state["image"].size
                if not lock_var.get():
                    if handle == "nw": l,r = min(x,r-1),r; t,b=min(y,b-1),b
                    elif handle == "n": t=min(y,b-1)
                    elif handle == "ne": r=max(x,l+1); t=min(y,b-1)
                    elif handle == "e": r=max(x,l+1)
                    elif handle == "se": r=max(x,l+1); b=max(y,t+1)
                    elif handle == "s": b=max(y,t+1)
                    elif handle == "sw": l=min(x,r-1); b=max(y,t+1)
                    elif handle == "w": l=min(x,r-1)
                    return clamp_rect([l,t,r,b])

                # Locked ratio: corner/edge handles resize around the appropriate anchor.
                if handle in ("nw","ne","se","sw"):
                    ax = r if "w" in handle else l
                    ay = b if "n" in handle else t
                    w = abs(x-ax)
                    h = w / target_ratio
                    if "n" in handle:
                        top, bottom = ay-h, ay
                    else:
                        top, bottom = ay, ay+h
                    if "w" in handle:
                        left, right = ax-w, ax
                    else:
                        left, right = ax, ax+w
                    return clamp_rect([left,top,right,bottom])
                if handle in ("e","w"):
                    ax = l if handle == "e" else r
                    w = abs(x-ax)
                    h = w / target_ratio
                    cy=(t+b)/2
                    left,right=(ax,ax+w) if handle=="e" else (ax-w,ax)
                    return clamp_rect([left,cy-h/2,right,cy+h/2])
                # n/s
                ay = b if handle == "n" else t
                h = abs(y-ay)
                w = h * target_ratio
                cx=(l+r)/2
                top,bottom=(ay-h,ay) if handle=="n" else (ay,ay+h)
                return clamp_rect([cx-w/2,top,cx+w/2,bottom])

            def update_cursor(handle):
                cursors={
                    "move":"fleur","nw":"size_nw_se","se":"size_nw_se",
                    "ne":"size_ne_sw","sw":"size_ne_sw","n":"sb_v_double_arrow",
                    "s":"sb_v_double_arrow","e":"sb_h_double_arrow","w":"sb_h_double_arrow"
                }
                canvas.configure(cursor=cursors.get(handle,"crosshair"))

            def down(e):
                handle=hit_test(e)
                state["drag"]=handle
                state["last_img"]=canvas_to_image(e.x,e.y)
                if handle is None:
                    state["drag"] = None
                update_cursor(handle)

            def move(e):
                handle=state["drag"]
                if not handle:
                    update_cursor(hit_test(e))
                    return
                x,y=canvas_to_image(e.x,e.y)
                lx,ly=state["last_img"]
                l,t,r,b=state["rect"]
                if handle=="move":
                    dx,dy=x-lx,y-ly
                    state["rect"]=clamp_rect([l+dx,t+dy,r+dx,b+dy])
                else:
                    state["rect"]=resize_from_handle(state["rect"],handle,x,y)
                state["last_img"]=(x,y)
                render()

            def up(e):
                state["drag"]=None
                state["last_img"]=None
                update_cursor(hit_test(e))

            def pan_down(e):
                state["pan_start"]=(e.x,e.y)
                state["pan_origin"]=(state["pan_x"],state["pan_y"])
                canvas.configure(cursor="fleur")

            def pan_move(e):
                if state["pan_start"] is None:
                    return
                sx,sy=state["pan_start"]; px,py=state["pan_origin"]
                state["pan_x"]=px+(e.x-sx); state["pan_y"]=py+(e.y-sy)
                render()

            def pan_up(e):
                state["pan_start"]=None
                state["pan_origin"]=None
                canvas.configure(cursor="crosshair")

            canvas.bind("<ButtonPress-1>", down)
            canvas.bind("<B1-Motion>", move)
            canvas.bind("<ButtonRelease-1>", up)
            canvas.bind("<ButtonPress-2>", pan_down)
            canvas.bind("<B2-Motion>", pan_move)
            canvas.bind("<ButtonRelease-2>", pan_up)

            def wheel(e):
                old=state["zoom"]
                new=old*(1.10 if e.delta>0 else 0.90)
                # Convert mouse position into an image point before zoom.
                anchor=canvas_to_image(e.x,e.y)
                set_zoom(new)
                # Recompute pan to keep the same image point approximately under cursor.
                cx,cy=image_to_canvas(*anchor)
                state["pan_x"] += e.x-cx
                state["pan_y"] += e.y-cy
                render()
            canvas.bind("<MouseWheel>", wheel)
            canvas.bind("<Configure>", lambda e: render())

            def reset_crop():
                state["rect"]=initial_rect(state["image"])
                state["pan_x"]=state["pan_y"]=0
                state["zoom"]=1.0
                zoom_var.set(1.0)
                render()

            def use_current():
                state["image"]=self.processed_image.copy()
                state["path"]=None
                state["rect"]=initial_rect(state["image"])
                state["pan_x"]=state["pan_y"]=0
                render()

            def open_photo():
                path=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff")])
                if not path:
                    return
                try:
                    state["image"]=Image.open(path).convert("RGB")
                    state["path"]=path
                    state["rect"]=initial_rect(state["image"])
                    state["pan_x"]=state["pan_y"]=0
                    state["zoom"]=1.0
                    zoom_var.set(1.0)
                    render()
                    self.set_status(f"Training photo loaded: {os.path.basename(path)}")
                except Exception as e:
                    messagebox.showerror("Training Photo",str(e))

            def save_example():
                l,t,r,b=state["rect"]
                if r-l<40 or b-t<40:
                    messagebox.showwarning("Training","Make a larger valid crop rectangle first.")
                    return
                import tempfile
                path=state["path"]
                if not path:
                    path=os.path.join(tempfile.gettempdir(),"pps_training_current.jpg")
                    state["image"].save(path,quality=95)
                rr=(int(round(l)),int(round(t)),int(round(r)),int(round(b)))
                try:
                    ex=make_example(path,rr,f"example_{len(examples)+1}")
                    # Keep the user's exact manual crop; no auto adjustment is applied here.
                    ex["manual"] = True
                    ex["target_ratio"] = target_ratio
                    examples.append(ex)
                    self.crop_training_examples=examples
                    self._save_crop_training_examples()
                    count_var.set(f"Training examples: {len(examples)}")
                    self.set_status(f"Saved exact manual crop example {len(examples)}.")
                except Exception as e:
                    messagebox.showerror("Training Example",str(e))

            def preview_crop():
                l,t,r,b=map(lambda v:int(round(v)),state["rect"])
                if r-l<20 or b-t<20:
                    return
                crop=state["image"].crop((l,t,r,b))
                preview=ctk.CTkToplevel(dialog)
                preview.title("Training Crop Preview")
                preview.geometry("520x680")
                preview.transient(dialog)
                maxw,maxh=460,570
                sc=min(maxw/crop.width,maxh/crop.height,1.0)
                out=crop.resize((max(1,int(crop.width*sc)),max(1,int(crop.height*sc))),Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(out)
                lbl=tk.Label(preview,image=photo,bg="#101116")
                lbl.image=photo; lbl.pack(expand=True,fill="both",padx=15,pady=15)

            def train_bot():
                if len(examples)<1:
                    messagebox.showwarning("Training Bot","Create at least one manual crop example first.")
                    return
                try:
                    self.crop_bot_profile=learn_profile(examples,"My Manual Crop Bot")
                    self.auto_apply_crop_bot = True
                    self._save_crop_bot_profile()
                    self.btn_apply_crop_bot.configure(state="normal")
                    self.auto_crop_var.set(True)
                    self.auto_crop_check.configure(state="normal")
                    messagebox.showinfo(
                        "Training Complete",
                        f"Learned from {len(examples)} manual example(s).\n\n"
                        f"Template mode: face-anchored Photoshop crop\n"
                        f"Face size: {self.crop_bot_profile['face_ratio']*100:.1f}%\n"
                        f"Top margin: {self.crop_bot_profile['top_ratio']*100:.1f}%\n"
                        f"Face center: {self.crop_bot_profile['center_ratio']*100:.1f}%\n\n"
                        "Auto-apply is ON. New photos will reuse this composition.\n"
                        "The bot learns composition, not identity."
                    )
                except Exception as e:
                    messagebox.showerror("Training Bot",str(e))

            def save_bot():
                if not self.crop_bot_profile:
                    messagebox.showwarning("Training Bot","Train the bot first.")
                    return
                path=filedialog.asksaveasfilename(
                    defaultextension=".json", initialfile="manual_crop_bot.json",
                    filetypes=[("Crop bot profile","*.json")]
                )
                if path:
                    save_crop_bot_profile(path,self.crop_bot_profile)
                    self._save_crop_bot_profile()
                    self.set_status("Manual crop bot profile saved.")

            def load_bot():
                path=filedialog.askopenfilename(filetypes=[("Crop bot profile","*.json")])
                if path:
                    try:
                        self.crop_bot_profile=load_crop_bot_profile(path)
                        self.auto_apply_crop_bot=bool(self.crop_bot_profile.get("auto_apply", False))
                        self._save_crop_bot_profile()
                        self.btn_apply_crop_bot.configure(state="normal")
                        self.auto_crop_var.set(self.auto_apply_crop_bot)
                        self.auto_crop_check.configure(state="normal")
                        self.set_status("Manual crop bot profile loaded.")
                    except Exception as e:
                        messagebox.showerror("Load Crop Bot",str(e))

            buttons=[
                ("📂 Open Training Photo",open_photo),
                ("↻ Use Current Photo",use_current),
                ("↺ Reset Crop",reset_crop),
                ("🔍 Preview Crop",preview_crop),
                ("💾 Save Exact Training Example",save_example),
                ("🧠 Train Bot",train_bot),
                ("Save Bot Profile",save_bot),
                ("Load Bot Profile",load_bot),
                ("✓ Apply Learned Crop",lambda:(dialog.destroy(),self.apply_crop_bot_profile())),
            ]
            for text,cmd in buttons:
                ctk.CTkButton(
                    panel,text=text,command=cmd,height=32,
                    fg_color=ACCENT if ("Train" in text or "Apply" in text or "Save Exact" in text) else "#2b2b36"
                ).pack(fill="x",padx=12,pady=3)
            ctk.CTkLabel(
                panel,
                text="Tip: adjust the rectangle exactly like a Photoshop crop. The saved rectangle is the training target.",
                text_color="#858a97",wraplength=225,justify="left"
            ).pack(padx=12,pady=12)
            render()
        except Exception as e:
            messagebox.showerror("Manual Crop Trainer",str(e))

    def apply_crop_bot_profile(self):
        if not self.processed_image or not self.crop_bot_profile: return
        try:
            self.push_history(); p=self.selected_preset(); out,analysis=smart_passport_crop(self.processed_image,p.width_mm,p.height_mm,self.dpi,self.crop_bot_profile); self.processed_image=out; self.photo_viewer.set_image(out,reset_zoom=True); self.set_status(f"Learned crop applied • {analysis.score}/100 • {analysis.crop_mode}"); self._refresh_layout_info(); self._set_ready_buttons()
        except Exception as e: messagebox.showerror("Apply Learned Crop",str(e))

    def choose_bg_color(self):
        result = colorchooser.askcolor(title="Select Background Color")
        if result[0]:
            self.bg_color = tuple(int(v) for v in result[0])
            self.btn_color.configure(fg_color=result[1])
            self.set_status(f"Selected background: {result[1]}")

    def start_bg_removal(self, finish_passport=False):
        if not self.processed_image:
            return
        self._finish_passport_after_bg = bool(finish_passport)
        self.btn_rembg.configure(state="disabled", text="⏳ Processing...")
        self.btn_passport_ready.configure(state="disabled", text="⏳ Preparing passport...")
        self.set_status("Removing background… online API if available, otherwise offline mode…")

        img_copy = self.processed_image.copy()
        bg_col = self.bg_color
        threading.Thread(target=self._bg_worker, args=(img_copy, bg_col), daemon=True).start()

    def _bg_worker(self, img, bg_col):
        try:
            rgba = self.remove_service.remove(img)
            final = composite_on_color(rgba, bg_col)
            self.after(0, lambda: self._bg_done(final, None))
        except Exception as e:
            self.after(0, lambda: self._bg_done(None, str(e)))

    def _bg_done(self, image, error):
        self.btn_rembg.configure(text="✨  Auto Remove Background")
        self.btn_passport_ready.configure(text="⚡ Passport Ready — BG + Smart Crop")
        if error:
            self.btn_rembg.configure(state="normal")
            self.btn_passport_ready.configure(state="normal")
            self.set_status("Background removal failed.")
            messagebox.showerror("Background Removal Error", error)
            return
        self.push_history()
        self.processed_image = image
        self.photo_viewer.set_image(image, reset_zoom=True)
        self.btn_rembg.configure(state="normal")
        self.btn_passport_ready.configure(state="normal")
        method = self.remove_service.last_method

        if getattr(self, "_finish_passport_after_bg", False):
            try:
                self.push_history()
                p = self.selected_preset()
                out, analysis = smart_passport_crop(self.processed_image, p.width_mm, p.height_mm, self.dpi, self.crop_bot_profile)
                self.processed_image = out
                self.photo_viewer.set_image(out, reset_zoom=True)
                self.set_status(
                    f"Passport Ready • {p.width_mm:g}×{p.height_mm:g} mm @ {self.dpi} DPI • "
                    f"background: {method} • framing: {analysis.score}/100"
                )
            except Exception as e:
                self.set_status(f"Background removed ({method}), but smart crop failed.")
                messagebox.showerror("Passport Ready", str(e))
            finally:
                self._finish_passport_after_bg = False
        else:
            self.set_status(f"Background removed & composited successfully ({method}).")
        self._refresh_layout_info()
        self._set_ready_buttons()

    def rotate_photo(self, clockwise):
        if not self.processed_image:
            return
        self.push_history()
        self.processed_image = rotate_90(self.processed_image, clockwise)
        self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
        self.set_status(f"Rotated {'clockwise' if clockwise else 'counter-clockwise'}.")
        self._refresh_layout_info()

    def flip_photo(self, axis):
        if not self.processed_image:
            return
        self.push_history()
        self.processed_image = flip_horizontal(self.processed_image) if axis == "h" else flip_vertical(self.processed_image)
        self.photo_viewer.set_image(self.processed_image)
        self.set_status("Flipped horizontally." if axis == "h" else "Flipped vertically.")

    def apply_filter(self):
        if not self.processed_image:
            return
        try:
            self.push_history()
            self.processed_image = apply_filter_preset(self.processed_image, self.filter_var.get())
            self.photo_viewer.set_image(self.processed_image)
            self.set_status(f"Filter applied: {self.filter_var.get()}")
        except Exception as e:
            messagebox.showerror("Filter Error", str(e))

    def apply_white_balance(self):
        if not self.processed_image:
            return
        try:
            self.push_history()
            self.processed_image = auto_white_balance(self.processed_image)
            self.photo_viewer.set_image(self.processed_image)
            self.set_status("Auto color fix applied.")
        except Exception as e:
            messagebox.showerror("Color Fix Error", str(e))

    def apply_denoise(self):
        if not self.processed_image:
            return
        try:
            self.set_status("Removing noise, please wait...")
            self.update_idletasks()
            self.push_history()
            self.processed_image = denoise(self.processed_image)
            self.photo_viewer.set_image(self.processed_image)
            self.set_status("Denoise applied.")
        except Exception as e:
            messagebox.showerror("Denoise Error", str(e))

    def apply_enhancement(self):
        if not self.processed_image:
            return
        try:
            self.push_history()
            vals = {k: s.get() for k, s in self.sliders.items()}
            self.processed_image = apply_adjustments(
                self.processed_image,
                vals["Brightness"], vals["Contrast"], vals["Color"],
                vals["Sharpness"], vals["Smooth Skin"]
            )
            self.photo_viewer.set_image(self.processed_image)
            self.set_status("Retouching applied.")
            self._refresh_layout_info()
        except Exception as e:
            messagebox.showerror("Retouching Error", str(e))

    def apply_auto_enhance(self):
        if not self.processed_image:
            return
        try:
            self.push_history()
            self.processed_image = auto_enhance_portrait(self.processed_image)
            self.photo_viewer.set_image(self.processed_image)
            self.set_status("Auto Enhance applied.")
        except Exception as e:
            messagebox.showerror("Enhancement Error", str(e))

    def apply_pro_adjustments(self):
        if not self.processed_image:
            return
        try:
            self.push_history()
            out = adjust_exposure(self.processed_image, self.pro_exposure.get())
            out = adjust_saturation(out, self.pro_saturation.get())
            out = adjust_highlights_shadows(out, self.pro_highlights.get(), self.pro_shadows.get())
            out = vignette(out, self.pro_vignette.get())
            self.processed_image = out
            self.photo_viewer.set_image(out)
            self.set_status("Pro color adjustments applied.")
        except Exception as e:
            messagebox.showerror("Pro Tools Error", str(e))

    def open_style_trainer(self):
        pdf_path = filedialog.askopenfilename(
            title="Select your style instruction PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not pdf_path:
            return
        try:
            text = extract_pdf_text(pdf_path)
            if not text:
                messagebox.showwarning("Style Trainer", "No selectable text was found in this PDF. A text-based instruction PDF works best.")
                return
            profile_name = os.path.splitext(os.path.basename(pdf_path))[0]
            profile = parse_instructions(text, profile_name)
            self.style_profile = profile
            if self.btn_apply_style is not None:
                self.btn_apply_style.configure(state="normal" if self.processed_image else "disabled")

            dialog = ctk.CTkToplevel(self)
            dialog.title("My Style Trainer")
            dialog.geometry("700x620")
            dialog.transient(self)
            dialog.grab_set()
            frame = ctk.CTkFrame(dialog, corner_radius=16, fg_color=SURFACE_2)
            frame.pack(expand=True, fill="both", padx=14, pady=14)
            ctk.CTkLabel(frame, text="🧠 My Style Trainer", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT).pack(pady=(16, 3))
            ctk.CTkLabel(frame, text="PDF instructions → reusable local photo style profile", text_color=TEXT_MUTED).pack(pady=(0, 12))

            summary = ctk.CTkTextbox(frame, height=270, corner_radius=10)
            summary.pack(fill="both", expand=True, padx=14, pady=6)
            summary.insert("1.0", json.dumps(profile, indent=2, ensure_ascii=False))
            summary.configure(state="disabled")

            ctk.CTkLabel(frame, text="This learns repeatable instructions/rules from your PDF; it does not fine-tune an AI model or upload your photos.", text_color="#a8a8b5", wraplength=620, justify="left").pack(fill="x", padx=16, pady=8)

            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(4, 14))
            def save_current():
                path = filedialog.asksaveasfilename(title="Save Style Profile", defaultextension=".json", filetypes=[("Style profile", "*.json")], initialfile=profile_name + ".json")
                if path:
                    save_profile(path, profile)
                    self.set_status(f"Style profile saved: {os.path.basename(path)}")
            def load_saved():
                path = filedialog.askopenfilename(title="Load Style Profile", filetypes=[("Style profile", "*.json")])
                if not path: return
                try:
                    self.style_profile = load_profile(path)
                    if self.btn_apply_style is not None:
                        self.btn_apply_style.configure(state="normal" if self.processed_image else "disabled")
                    dialog.destroy()
                    self.set_status(f"Loaded style: {self.style_profile.get('name', 'My Style')}")
                except Exception as e:
                    messagebox.showerror("Style Profile", str(e))
            ctk.CTkButton(row, text="Save Profile", command=save_current, height=34).pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkButton(row, text="Load Profile", command=load_saved, height=34).pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkButton(row, text="Apply to Current Photo", command=lambda: (dialog.destroy(), self.apply_style_profile()), fg_color=ACCENT, hover_color=ACCENT_HOVER, height=34).pack(side="left", expand=True, fill="x", padx=3)
        except Exception as e:
            messagebox.showerror("Style Trainer Error", str(e))

    def apply_style_profile(self):
        if not self.processed_image or not self.style_profile:
            return
        try:
            self.push_history()
            p = self.style_profile
            if p.get("preset_mm"):
                w, h = p["preset_mm"]
                self.processed_image = smart_crop_and_resize(self.processed_image, w, h, self.dpi)
            if p.get("background"):
                self.bg_color = tuple(int(x) for x in p["background"])
                self.processed_image = composite_on_color(self.processed_image.convert("RGBA"), self.bg_color).convert("RGB")
            if p.get("auto_white_balance"):
                self.processed_image = auto_white_balance(self.processed_image)
            if p.get("denoise"):
                self.processed_image = denoise(self.processed_image)
            if p.get("auto_enhance"):
                self.processed_image = auto_enhance_portrait(self.processed_image)

            vals = {k: self.sliders[k].get() for k in self.sliders}
            for key in ("brightness", "contrast", "color", "sharpness", "smooth_skin"):
                if p.get(key) is not None:
                    vals["Color" if key == "color" else "Smooth Skin" if key == "smooth_skin" else key.capitalize()] = p[key]
            self.processed_image = apply_adjustments(self.processed_image, vals["Brightness"], vals["Contrast"], vals["Color"], vals["Sharpness"], vals["Smooth Skin"])

            if any(p.get(k) is not None for k in ("exposure", "saturation", "highlights", "shadows", "vignette")):
                self.processed_image = adjust_exposure(self.processed_image, p.get("exposure", 0.0) or 0.0)
                self.processed_image = adjust_saturation(self.processed_image, p.get("saturation", 1.0) or 1.0)
                self.processed_image = adjust_highlights_shadows(self.processed_image, p.get("highlights", 0.0) or 0.0, p.get("shadows", 0.0) or 0.0)
                self.processed_image = vignette(self.processed_image, p.get("vignette", 0.0) or 0.0)
            self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
            self._refresh_layout_info()
            self.set_status(f"Applied style: {p.get('name', 'My Style')}")
        except Exception as e:
            messagebox.showerror("Apply Style Error", str(e))

    def open_ai_style_learning(self):
        paths = filedialog.askopenfilenames(
            title="Select 5–20 example photos in your preferred style",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")]
        )
        if not paths:
            return
        if len(paths) < 3:
            messagebox.showwarning("AI Style Learning", "Select at least 3 examples. 5–20 examples are recommended for a stronger style profile.")
            return
        try:
            profile = learn_style(list(paths), os.path.splitext(os.path.basename(paths[0]))[0] + " — Learned Style")
            self.ai_style_profile = profile
            if self.btn_apply_ai_style is not None:
                self.btn_apply_ai_style.configure(state="normal" if self.processed_image else "disabled")

            dialog = ctk.CTkToplevel(self)
            dialog.title("AI Style Learning")
            dialog.geometry("720x620")
            dialog.transient(self)
            dialog.grab_set()
            frame = ctk.CTkFrame(dialog, corner_radius=16, fg_color=SURFACE_2)
            frame.pack(expand=True, fill="both", padx=14, pady=14)
            ctk.CTkLabel(frame, text="🤖 AI Style Learning", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT).pack(pady=(16, 3))
            ctk.CTkLabel(frame, text=f"Learned from {len(paths)} example photos — fully local", text_color=TEXT_MUTED).pack(pady=(0, 12))
            summary = ctk.CTkTextbox(frame, height=330, corner_radius=10)
            summary.pack(fill="both", expand=True, padx=14, pady=6)
            summary.insert("1.0", json.dumps(profile, indent=2, ensure_ascii=False))
            summary.configure(state="disabled")
            ctk.CTkLabel(frame, text="This learns global color, exposure, contrast, detail and crop characteristics. It does not learn a person's identity or facial features, and it does not upload photos.", text_color="#a8a8b5", wraplength=650, justify="left").pack(fill="x", padx=16, pady=8)
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(4, 14))
            def save_current():
                path = filedialog.asksaveasfilename(title="Save Learned Style", defaultextension=".json", filetypes=[("AI style profile", "*.json")], initialfile="learned_style.json")
                if path:
                    save_learned_style(path, profile)
                    self.set_status(f"Learned style saved: {os.path.basename(path)}")
            def load_saved():
                path = filedialog.askopenfilename(title="Load Learned Style", filetypes=[("AI style profile", "*.json")])
                if not path: return
                try:
                    self.ai_style_profile = load_learned_style(path)
                    if self.btn_apply_ai_style is not None:
                        self.btn_apply_ai_style.configure(state="normal" if self.processed_image else "disabled")
                    dialog.destroy()
                    self.set_status(f"Loaded learned style: {self.ai_style_profile.get('name', 'Learned Style')}")
                except Exception as e:
                    messagebox.showerror("Learned Style", str(e))
            ctk.CTkButton(row, text="Save Learned Style", command=save_current, height=34).pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkButton(row, text="Load Style", command=load_saved, height=34).pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkButton(row, text="Apply to Current Photo", command=lambda: (dialog.destroy(), self.apply_ai_style()), fg_color=ACCENT, hover_color=ACCENT_HOVER, height=34).pack(side="left", expand=True, fill="x", padx=3)
        except Exception as e:
            messagebox.showerror("AI Style Learning Error", str(e))

    def apply_ai_style(self):
        if not self.processed_image or not self.ai_style_profile:
            return
        try:
            self.push_history()
            self.processed_image = apply_learned_style(self.processed_image, self.ai_style_profile)
            self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
            self.set_status(f"Applied learned style: {self.ai_style_profile.get('name', 'Learned Style')}")
        except Exception as e:
            messagebox.showerror("Apply Learned Style Error", str(e))

    def configure_api_key(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Background API Settings")
        dialog.geometry("520x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog, corner_radius=16, fg_color=SURFACE_2)
        frame.pack(expand=True, fill="both", padx=14, pady=14)
        ctk.CTkLabel(frame, text="Background Removal API",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 5))
        ctk.CTkLabel(frame, text="Your key is stored only in the local app configuration.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=10)).pack()

        entry = ctk.CTkEntry(frame, height=34, show="•", placeholder_text="Paste API key")
        entry.pack(fill="x", padx=24, pady=(18, 8))
        current = configured_remove_bg_key()
        if current:
            entry.insert(0, current)

        def save_key():
            key = entry.get().strip()
            data = load_user_config()
            if key:
                data["remove_bg_api_key"] = key
            else:
                data.pop("remove_bg_api_key", None)
            save_user_config(data)
            self.remove_service.set_api_key(key)
            dialog.destroy()
            self.btn_rembg.configure(state="normal" if self.processed_image else "disabled")
            self.set_status("Background API settings updated.")

        ctk.CTkButton(frame, text="Save API Key", command=save_key,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, height=34).pack(pady=8)
        ctk.CTkLabel(frame, text="Tip: For distributed builds, prefer an environment variable or server-side proxy.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=9)).pack(pady=(2, 8))

    def reset_to_original(self):
        if not self.original_image:
            return
        self.push_history()
        self.processed_image = self.original_image.copy()
        self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
        self.a4_image = None
        self.a4_viewer.clear()
        self.set_status("Reset to original image.")
        self._refresh_layout_info()
        self._set_ready_buttons()

    def generate_a4(self):
        if not self.processed_image:
            return
        try:
            quantity = int(self.qty.get())
            per_line = int(self.per_line.get())
            mx = float(self.margin_x.get())
            my = float(self.margin_y.get())
            gx = float(self.gap_x.get())
            gy = float(self.gap_y.get())
            border = float(self.border.get())

            sheet, cols, rows, capacity = make_a4_sheet(
                self.processed_image, quantity, self.dpi,
                mx, my, gx, gy, border,
                requested_cols=per_line,
                center_last_row=self.center_last.get()
            )
            self.a4_image = sheet
            self.a4_viewer.set_image(sheet, reset_zoom=True)
            self.a4_header.configure(
                text=f"A4 Sheet • {quantity} photos ({cols} cols × {rows} rows)"
            )
            self.tabs.set("A4 Print Preview")
            self._tab_changed()
            self._set_ready_buttons()
            self.set_status(f"A4 generated • {quantity} photos arranged")
        except Exception as e:
            messagebox.showerror("A4 Error", str(e))
            self._refresh_layout_info()

    def save_photo(self):
        if not self.processed_image:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")]
        )
        if path:
            try:
                save_image(self.processed_image, path, self.dpi)
                self.set_status(f"Saved: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def save_a4(self):
        if not self.a4_image:
            messagebox.showinfo("Export", "Generate A4 print sheet first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")]
        )
        if path:
            try:
                save_image(self.a4_image, path, self.dpi)
                self.set_status(f"A4 sheet saved: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def undo(self):
        if not self.history:
            return
        self.future.append(self.processed_image.copy())
        self.processed_image = self.history.pop()
        self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
        self.set_status("Undo performed.")
        self._refresh_layout_info()
        self._set_ready_buttons()

    def redo(self):
        if not self.future:
            return
        self.history.append(self.processed_image.copy())
        self.processed_image = self.future.pop()
        self.photo_viewer.set_image(self.processed_image, reset_zoom=True)
        self.set_status("Redo performed.")
        self._refresh_layout_info()
        self._set_ready_buttons()

    def _toggle_fullscreen(self):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _on_close(self):
        self.destroy()


if __name__ == "__main__":
    app = PassportPhotoStudio()
    app.mainloop()