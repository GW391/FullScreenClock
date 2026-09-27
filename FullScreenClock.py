import json
import math
import os
import argparse
import random
import time
import tempfile
import sys
import tkinter as tk
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from tkinter import colorchooser, filedialog, font as tkfont, messagebox, simpledialog, ttk
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageChops
except ImportError:
    Image = None
    ImageTk = None


APP_TITLE = "Multi Clock"
APP_BASE = sys.executable if getattr(sys, "frozen", False) else __file__
APP_DIR = os.path.dirname(os.path.abspath(APP_BASE))
THEME_DIR = os.path.join(APP_DIR, "themes")
CURRENT_THEME_PACKAGE = os.path.join(THEME_DIR, "current.theme")
CURRENT_THEME_FILE = os.path.join(CURRENT_THEME_PACKAGE, "theme.json")
LEGACY_THEME_DIR = os.path.join(os.path.expanduser("~"), ".multi_clock_themes")
THEME_EXT = ".theme.json"
THEME_PACKAGE_SUFFIX = ".theme"
ASSET_DIRNAME = "images"
THEME_VERSION = 10
MAX_THEME_FILE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_FILE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000
MAX_IMAGE_WIDGETS = 32
MAX_QUOTES_PER_WIDGET = 5000
MAX_AUX_WIDGETS = 32
MAX_QUOTE_LENGTH = 10000

NIXIE_SKINS = {
    "classic_orange": {
        "label": "Classic Orange",
        "digit": "#FFB347",
        "glow": "#FF5A1F",
        "tube": "#140A06",
        "glass": "#7A3C18",
        "grid": "#6E3C22",
        "metal": "#A96F32",
        "off": "#2D160D",
    },
    "amber": {
        "label": "Amber",
        "digit": "#FFD27A",
        "glow": "#FF8A00",
        "tube": "#170D03",
        "glass": "#8A5A18",
        "grid": "#745018",
        "metal": "#C18A3C",
        "off": "#33200A",
    },
    "blue": {
        "label": "Cool Blue",
        "digit": "#BFE8FF",
        "glow": "#38A8FF",
        "tube": "#06121C",
        "glass": "#1E668C",
        "grid": "#25536E",
        "metal": "#5F8299",
        "off": "#102635",
    },
    "green": {
        "label": "Vintage Green",
        "digit": "#B8FFB0",
        "glow": "#32D36B",
        "tube": "#061208",
        "glass": "#2D7A42",
        "grid": "#2F5F3C",
        "metal": "#64825F",
        "off": "#12321B",
    },
    "ice_white": {
        "label": "Ice White",
        "digit": "#FFFFFF",
        "glow": "#8CD8FF",
        "tube": "#091016",
        "glass": "#5A84A0",
        "grid": "#455C70",
        "metal": "#8BA4B5",
        "off": "#172631",
    },
    "custom": {
        "label": "Custom",
        "digit": "#FFB347",
        "glow": "#FF5A1F",
        "tube": "#140A06",
        "glass": "#7A3C18",
        "grid": "#6E3C22",
        "metal": "#A96F32",
        "off": "#2D160D",
    },
}


@dataclass
class ClockData:
    clock_id: int
    kind: str = "digital"          # digital / segment / nixie / custom_image / analogue
    x: float = 0.5                 # relative centre position
    y: float = 0.5
    size: float = 0.28              # relative size of window height
    timezone: str = "local"
    label: str = ""
    font_family: str = "DejaVu Sans"
    font_weight: str = "normal"
    text_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    face_color: str = "#111111"
    text_transparent: bool = False
    accent_transparent: bool = False
    face_transparent: bool = False
    show_seconds: bool = True
    use_24h: bool = True
    show_ampm: bool = True
    segment_off_transparent: bool = True
    nixie_digit_paths: dict = field(default_factory=dict)  # legacy compatibility
    custom_digit_paths: dict = field(default_factory=dict)
    nixie_skin: str = "classic_orange"
    nixie_custom: dict = field(default_factory=dict)


@dataclass
class ImageData:
    image_id: int
    path: str
    x: float = 0.5
    y: float = 0.5
    size: float = 0.25             # relative width of the window
    label: str = ""


@dataclass
class QuoteData:
    quote_id: int
    quotes: list
    x: float = 0.5
    y: float = 0.75
    size: float = 0.45             # relative width of the window
    font_family: str = "DejaVu Sans"
    font_weight: str = "normal"
    text_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    face_color: str = "#111111"
    face_transparent: bool = True
    interval: float = 20.0         # seconds
    randomize: bool = False
    current_index: int = 0
    last_changed: float = 0.0
    label: str = ""


@dataclass
class AmpmData:
    ampm_id: int
    linked_clock_id: int = 1
    x: float = 0.5
    y: float = 0.5
    size: float = 0.16
    font_family: str = "DejaVu Sans"
    font_weight: str = "bold"
    text_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    face_color: str = "#111111"
    face_transparent: bool = True
    label: str = ""


@dataclass
class DayData:
    day_id: int
    linked_clock_id: int = 1
    x: float = 0.5
    y: float = 0.65
    size: float = 0.28
    day_format: str = "full"           # full / short / upper
    font_family: str = "DejaVu Sans"
    font_weight: str = "normal"
    text_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    face_color: str = "#111111"
    face_transparent: bool = True
    label: str = ""


@dataclass
class DateData:
    date_id: int
    linked_clock_id: int = 1
    x: float = 0.5
    y: float = 0.73
    size: float = 0.30
    date_format: str = "long"          # long / short / numeric_eu / numeric_us / iso / weekday_long
    font_family: str = "DejaVu Sans"
    font_weight: str = "normal"
    text_color: str = "#FFFFFF"
    accent_color: str = "#FFFFFF"
    face_color: str = "#111111"
    face_transparent: bool = True
    label: str = ""


class ClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x720")
        self.minsize(600, 400)
        self.configure(bg="#101010")

        self.fullscreen = False
        self.background_color = "#101010"
        self.background_image_path = ""
        self.background_image = None
        self.background_image_source = None
        self.background_image_signature = None
        self.background_image_cache = {}
        self.clocks = []
        self.next_id = 1
        self.images = []
        self.next_image_id = 1
        self.quotes = []
        self.next_quote_id = 1
        self.ampm_widgets = []
        self.next_ampm_id = 1
        self.day_widgets = []
        self.next_day_id = 1
        self.date_widgets = []
        self.next_date_id = 1
        self.selected_id = None
        self.selected_image_id = None
        self.selected_quote_id = None
        self.selected_ampm_id = None
        self.selected_day_id = None
        self.selected_date_id = None
        self.image_sources = {}
        self.image_refs = {}
        self.image_cache = {}
        self.nixie_digit_sources = {}
        self.nixie_digit_refs = {}
        self.nixie_digit_cache = {}
        self.custom_digit_sources = {}
        self.custom_digit_refs = {}
        self.custom_digit_cache = {}
        self.quote_font_cache = {}
        self.image_source_signatures = {}
        self.context_x = 0.5
        self.context_y = 0.5
        self.dragging_id = None
        self.dragging_image_id = None
        self.dragging_quote_id = None
        self.dragging_ampm_id = None
        self.dragging_day_id = None
        self.dragging_date_id = None
        self.drag_start = None
        self.resize_mode = None
        self.resize_start = None
        self.dark_mode = True
        self._autosave_after_id = None
        self._last_autosave_error = ""
        self.current_theme_name = "Default"
        self.current_theme_path = ""
        self.image_label_color = "#FFFFFF"
        self.theme_menu = None
        self.font_families = sorted(set(tkfont.families()))
        if "DejaVu Sans" not in self.font_families:
            self.font_families.insert(0, tkfont.nametofont("TkDefaultFont").actual("family"))
        try:
            self.timezone_choices = ["local", "UTC"] + sorted(
                tz for tz in available_timezones() if tz not in {"UTC", "local"}
            )
        except Exception:
            # Keep the editor usable on systems with incomplete zoneinfo data.
            self.timezone_choices = ["local", "UTC", "Europe/London"]

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.background_color)
        self.canvas.pack(fill="both", expand=True)

        self._build_menu()
        self._build_toolbar()
        self._build_context_menu()
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._restoring_settings = False

        self._migrate_legacy_current_theme()

        cli_theme = self._parse_command_line_theme()
        self._ensure_theme_dir()
        loaded = False
        if cli_theme:
            loaded = self.load_theme(cli_theme, silent=False)
        elif os.path.exists(CURRENT_THEME_FILE):
            loaded = self.load_theme(CURRENT_THEME_FILE, silent=True)
        if not loaded:
            self.add_clock("digital")
            self.add_clock("analogue", x=0.75, y=0.5, size=0.34)
            self.current_theme_name = "Current"
            self.current_theme_path = CURRENT_THEME_FILE
            self._autosave_theme_now()
        self._ensure_theme_defaults()
        self._refresh_theme_menu()
        self.update_clock()

    # ----------------------------- UI ---------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        clock_menu = tk.Menu(menubar, tearoff=False)
        clock_menu.add_command(label="Add Clock", command=lambda: self.add_clock("digital"))
        clock_menu.add_separator()
        clock_menu.add_command(label="Edit Selected Clock", command=self.edit_selected_clock)
        clock_menu.add_command(label="Delete Selected Clock", command=self.delete_selected_clock)
        clock_menu.add_separator()
        clock_menu.add_command(label="Add Image Widget...", command=self.add_image_dialog)
        clock_menu.add_command(label="Edit Selected Image", command=self.edit_selected_image)
        clock_menu.add_command(label="Delete Selected Image", command=self.delete_selected_image)
        clock_menu.add_separator()
        clock_menu.add_command(label="Add Quotes Widget...", command=self.add_quotes_dialog)
        clock_menu.add_command(label="Edit Selected Quotes", command=self.edit_selected_quote)
        clock_menu.add_command(label="Delete Selected Quotes", command=self.delete_selected_quote)
        clock_menu.add_separator()
        clock_menu.add_command(label="Add AM/PM Widget...", command=self.add_ampm_dialog)
        clock_menu.add_command(label="Edit Selected AM/PM", command=self.edit_selected_ampm)
        clock_menu.add_command(label="Delete Selected AM/PM", command=self.delete_selected_ampm)
        clock_menu.add_separator()
        clock_menu.add_command(label="Add Day Widget...", command=self.add_day_dialog)
        clock_menu.add_command(label="Edit Selected Day", command=self.edit_selected_day)
        clock_menu.add_command(label="Delete Selected Day", command=self.delete_selected_day)
        clock_menu.add_command(label="Add Date Widget...", command=self.add_date_dialog)
        clock_menu.add_command(label="Edit Selected Date", command=self.edit_selected_date)
        clock_menu.add_command(label="Delete Selected Date", command=self.delete_selected_date)
        clock_menu.add_separator()
        clock_menu.add_command(label="Increase Selected Size", command=lambda: self.change_selected_size(1.08))
        clock_menu.add_command(label="Decrease Selected Size", command=lambda: self.change_selected_size(1 / 1.08))
        menubar.add_cascade(label="Clock", menu=clock_menu)

        appearance = tk.Menu(menubar, tearoff=False)
        appearance.add_command(label="Background Colour...", command=self.choose_background_color)
        appearance.add_command(label="Background Image...", command=self.choose_background_image)
        appearance.add_command(label="Clear Background Image", command=self.clear_background_image)
        appearance.add_separator()
        appearance.add_command(label="Reset Background", command=self.reset_background)
        menubar.add_cascade(label="Appearance", menu=appearance)

        themes = tk.Menu(menubar, tearoff=False)
        themes.add_command(label="Create Theme From Current State...", command=self.create_theme_from_current)
        themes.add_command(label="Save Current Theme (All Settings)", command=self.save_current_theme)
        themes.add_command(label="Save Current Theme As...", command=self.save_current_theme_as)
        themes.add_separator()
        self.theme_menu = themes
        menubar.add_cascade(label="Themes", menu=themes)

        view = tk.Menu(menubar, tearoff=False)
        view.add_command(label="Toggle Fullscreen", command=self.toggle_fullscreen, accelerator="F11")
        view.add_command(label="Exit Fullscreen", command=lambda: self.set_fullscreen(False))
        menubar.add_cascade(label="View", menu=view)

        layout = tk.Menu(menubar, tearoff=False)
        layout.add_command(label="Save Full Theme State As...", command=self.save_layout)
        layout.add_command(label="Load Full Theme State...", command=self.load_layout)
        layout.add_separator()
        layout.add_command(label="Reset Layout", command=self.reset_layout)
        menubar.add_cascade(label="State", menu=layout)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Help", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_toolbar(self):
        # Toolbar is deliberately compact so the main canvas remains the focus.
        self.toolbar = tk.Frame(self, bg="#202020", height=34)
        self.toolbar.place(relx=0, rely=0, relwidth=1, height=34)

        buttons = [
            ("Clock +", lambda: self.add_clock("digital")),
            ("Image +", self.add_image_dialog),
            ("Quotes +", self.add_quotes_dialog),
            ("AM/PM +", self.add_ampm_dialog),
            ("Day +", self.add_day_dialog),
            ("Date +", self.add_date_dialog),
            ("Edit", self.edit_selected_any),
            ("Delete", self.delete_selected_any),
            ("Background", self.choose_background_color),
            ("Fullscreen", self.toggle_fullscreen),
        ]
        for label, command in buttons:
            b = tk.Button(self.toolbar, text=label, command=command, relief="flat", bd=0,
                          bg="#303030", fg="#FFFFFF", activebackground="#454545",
                          activeforeground="#FFFFFF", padx=8)
            b.pack(side="left", padx=2, pady=3)

        info = tk.Label(self.toolbar,
                        text="Drag clocks to move • Right-click for settings • Ctrl+wheel to resize",
                        bg="#202020", fg="#BEBEBE")
        info.pack(side="right", padx=8)

    def _build_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(label="Add Clock Here", command=self._context_add_digital)
        self.context_menu.add_command(label="Add Image Here...", command=self._context_add_image)
        self.context_menu.add_command(label="Add Quotes Here...", command=self._context_add_quotes)
        self.context_menu.add_command(label="Add AM/PM Here...", command=self._context_add_ampm)
        self.context_menu.add_command(label="Add Day Here...", command=self._context_add_day)
        self.context_menu.add_command(label="Add Date Here...", command=self._context_add_date)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Edit Clock", command=self.edit_selected_clock)
        self.context_menu.add_command(label="Delete Clock", command=self.delete_selected_clock)
        self.context_menu.add_command(label="Edit Image", command=self.edit_selected_image)
        self.context_menu.add_command(label="Delete Image", command=self.delete_selected_image)
        self.context_menu.add_command(label="Edit Quotes", command=self.edit_selected_quote)
        self.context_menu.add_command(label="Delete Quotes", command=self.delete_selected_quote)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Edit AM/PM", command=self.edit_selected_ampm)
        self.context_menu.add_command(label="Delete AM/PM", command=self.delete_selected_ampm)
        self.context_menu.add_command(label="Edit Day", command=self.edit_selected_day)
        self.context_menu.add_command(label="Delete Day", command=self.delete_selected_day)
        self.context_menu.add_command(label="Edit Date", command=self.edit_selected_date)
        self.context_menu.add_command(label="Delete Date", command=self.delete_selected_date)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Increase Size", command=lambda: self.change_selected_size(1.08))
        self.context_menu.add_command(label="Decrease Size", command=lambda: self.change_selected_size(1 / 1.08))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Background Colour...", command=self.choose_background_color)
        self.context_menu.add_command(label="Background Image...", command=self.choose_background_image)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Fullscreen", command=self.toggle_fullscreen)

    def _bind_events(self):
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.set_fullscreen(False))
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Double-Button-1>", lambda e: self._double_click(e))
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.on_ctrl_wheel(e, +1))
        self.canvas.bind("<Button-5>", lambda e: self.on_ctrl_wheel(e, -1))
        self.bind("<Configure>", self._on_window_configure)

    # ---------------------------- themes -------------------------------
    # ---------------------- validation helpers -----------------------
    @staticmethod
    def _bounded_float(value, default, low, high):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(value):
            return default
        return max(low, min(high, value))

    @staticmethod
    def _bounded_int(value, default, low, high):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return max(low, min(high, value))

    @staticmethod
    def _safe_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1", "on"}:
                return True
            if normalized in {"false", "no", "0", "off"}:
                return False
        return default

    @staticmethod
    def _safe_text(value, default="", max_len=10000):
        if value is None:
            return default
        text = str(value)
        return text[:max_len]

    def _safe_colour(self, value, default):
        value = self._safe_text(value, default, 32).strip()
        try:
            self.winfo_rgb(value)
            return value
        except tk.TclError:
            return default

    def _safe_font_family(self, value, default=None):
        if default is None:
            default = tkfont.nametofont("TkDefaultFont").actual("family")
        value = self._safe_text(value, default, 100).strip()
        return value if value in self.font_families else default

    def _safe_font_weight(self, value, default="normal"):
        value = self._safe_text(value, default, 20).lower()
        return value if value in {"normal", "bold"} else default

    def _normalise_clock(self, raw, fallback_id):
        if not isinstance(raw, dict):
            return None
        c = ClockData(
            clock_id=self._bounded_int(raw.get("clock_id"), fallback_id, 1, 2_000_000_000),
            kind=self._safe_text(raw.get("kind"), "digital", 20).lower(),
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.5, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.28, 0.08, 0.75),
            timezone=self._safe_text(raw.get("timezone"), "local", 100),
            label=self._safe_text(raw.get("label"), "", 200),
            font_family=self._safe_font_family(raw.get("font_family")),
            font_weight=self._safe_font_weight(raw.get("font_weight")),
            text_color=self._safe_colour(raw.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(raw.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(raw.get("face_color"), "#111111"),
            text_transparent=self._safe_bool(raw.get("text_transparent"), False),
            accent_transparent=self._safe_bool(raw.get("accent_transparent"), False),
            face_transparent=self._safe_bool(raw.get("face_transparent"), False),
            show_seconds=self._safe_bool(raw.get("show_seconds"), True),
            use_24h=self._safe_bool(raw.get("use_24h"), True),
            show_ampm=self._safe_bool(raw.get("show_ampm"), True),
            segment_off_transparent=self._safe_bool(raw.get("segment_off_transparent"), True),
            nixie_digit_paths=self._normalise_nixie_digit_paths(raw.get("nixie_digit_paths")),
            custom_digit_paths=self._normalise_nixie_digit_paths(raw.get("custom_digit_paths")),
            nixie_skin=self._safe_nixie_skin(raw.get("nixie_skin")),
            nixie_custom=self._normalise_nixie_custom(raw.get("nixie_custom")),
        )
        if c.kind not in {"digital", "segment", "nixie", "custom_image", "analogue"}:
            c.kind = "digital"
        return c

    def _normalise_nixie_digit_paths(self, raw):
        if not isinstance(raw, dict):
            return {}
        cleaned = {}
        # Custom-image clocks may also provide artwork for the time separator.
        # It is stored under the key "colon" alongside digit assets.
        for digit in list("0123456789") + ["colon"]:
            value = self._safe_text(raw.get(digit), "", 4096).strip()
            if value:
                cleaned[digit] = value
        return cleaned

    def _safe_nixie_skin(self, value):
        value = self._safe_text(value, "classic_orange", 40).strip().lower()
        return value if value in NIXIE_SKINS else "classic_orange"

    def _normalise_nixie_custom(self, raw):
        if not isinstance(raw, dict):
            return {}
        result = {}
        for key, default in NIXIE_SKINS["custom"].items():
            if key == "label":
                continue
            value = self._safe_colour(raw.get(key), default)
            result[key] = value
        return result

    def _nixie_palette(self, c):
        palette = dict(NIXIE_SKINS.get(c.nixie_skin, NIXIE_SKINS["classic_orange"]))
        if c.nixie_skin == "custom":
            palette.update(self._normalise_nixie_custom(c.nixie_custom))
        return palette

    def _normalise_image(self, raw, fallback_id, asset_root=None, allow_legacy_absolute=False):
        if not isinstance(raw, dict):
            return None
        path = self._safe_text(raw.get("path"), "", 4096).strip()
        if not path:
            return None
        resolved = self._resolve_theme_asset_path(asset_root, path, allow_legacy_absolute)
        if not resolved:
            return None
        return ImageData(
            image_id=self._bounded_int(raw.get("image_id"), fallback_id, 1, 2_000_000_000),
            path=resolved,
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.5, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.25, 0.04, 0.95),
            label=self._safe_text(raw.get("label"), "", 200),
        )

    def _normalise_quote(self, raw, fallback_id):
        if not isinstance(raw, dict):
            return None
        raw_quotes = raw.get("quotes", [])
        if not isinstance(raw_quotes, list):
            raw_quotes = []
        cleaned = []
        for item in raw_quotes[:MAX_QUOTES_PER_WIDGET]:
            text = self._safe_text(item, "", MAX_QUOTE_LENGTH).strip()
            if text:
                cleaned.append(text)
        q = QuoteData(
            quote_id=self._bounded_int(raw.get("quote_id"), fallback_id, 1, 2_000_000_000),
            quotes=cleaned,
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.75, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.45, 0.12, 0.95),
            font_family=self._safe_font_family(raw.get("font_family")),
            font_weight=self._safe_font_weight(raw.get("font_weight")),
            text_color=self._safe_colour(raw.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(raw.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(raw.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(raw.get("face_transparent"), True),
            interval=self._bounded_float(raw.get("interval"), 20.0, 1.0, 3600.0),
            randomize=self._safe_bool(raw.get("randomize"), False),
            current_index=self._bounded_int(raw.get("current_index"), 0, 0, max(0, len(cleaned) - 1)),
            last_changed=self._bounded_float(raw.get("last_changed"), 0.0, 0.0, 4_000_000_000.0),
            label=self._safe_text(raw.get("label"), "", 200),
        )
        return q if q.quotes else None

    def _normalise_ampm(self, raw, fallback_id):
        if not isinstance(raw, dict):
            return None
        return AmpmData(
            ampm_id=self._bounded_int(raw.get("ampm_id"), fallback_id, 1, 2_000_000_000),
            linked_clock_id=self._bounded_int(raw.get("linked_clock_id"), 1, 1, 2_000_000_000),
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.5, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.16, 0.08, 0.8),
            font_family=self._safe_font_family(raw.get("font_family")),
            font_weight=self._safe_font_weight(raw.get("font_weight"), "bold"),
            text_color=self._safe_colour(raw.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(raw.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(raw.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(raw.get("face_transparent"), True),
            label=self._safe_text(raw.get("label"), "", 200),
        )

    def _normalise_day(self, raw, fallback_id):
        if not isinstance(raw, dict):
            return None
        day = DayData(
            day_id=self._bounded_int(raw.get("day_id"), fallback_id, 1, 2_000_000_000),
            linked_clock_id=self._bounded_int(raw.get("linked_clock_id"), 1, 1, 2_000_000_000),
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.65, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.28, 0.08, 0.95),
            day_format=self._safe_text(raw.get("day_format"), "full", 20).lower(),
            font_family=self._safe_font_family(raw.get("font_family")),
            font_weight=self._safe_font_weight(raw.get("font_weight")),
            text_color=self._safe_colour(raw.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(raw.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(raw.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(raw.get("face_transparent"), True),
            label=self._safe_text(raw.get("label"), "", 200),
        )
        if day.day_format not in {"full", "short", "upper"}:
            day.day_format = "full"
        return day

    def _normalise_date(self, raw, fallback_id):
        if not isinstance(raw, dict):
            return None
        item = DateData(
            date_id=self._bounded_int(raw.get("date_id"), fallback_id, 1, 2_000_000_000),
            linked_clock_id=self._bounded_int(raw.get("linked_clock_id"), 1, 1, 2_000_000_000),
            x=self._bounded_float(raw.get("x"), 0.5, 0.01, 0.99),
            y=self._bounded_float(raw.get("y"), 0.73, 0.01, 0.99),
            size=self._bounded_float(raw.get("size"), 0.30, 0.08, 0.95),
            date_format=self._safe_text(raw.get("date_format"), "long", 40).lower(),
            font_family=self._safe_font_family(raw.get("font_family")),
            font_weight=self._safe_font_weight(raw.get("font_weight")),
            text_color=self._safe_colour(raw.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(raw.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(raw.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(raw.get("face_transparent"), True),
            label=self._safe_text(raw.get("label"), "", 200),
        )
        if item.date_format not in {"long", "short", "numeric_eu", "numeric_us", "iso", "weekday_long"}:
            item.date_format = "long"
        return item

    @staticmethod
    def _is_within_directory(path, directory):
        try:
            return os.path.commonpath([os.path.realpath(path), os.path.realpath(directory)]) == os.path.realpath(directory)
        except ValueError:
            return False

    def _resolve_theme_asset_path(self, asset_root, raw_path, allow_legacy_absolute=False):
        path = self._safe_text(raw_path, "", 4096).strip()
        if not path:
            return ""
        if asset_root:
            asset_dir = self._theme_asset_dir(asset_root)
            if os.path.isabs(path):
                candidate = os.path.realpath(os.path.expanduser(path))
            else:
                candidate = os.path.realpath(os.path.join(asset_root, path))
            if self._is_within_directory(candidate, asset_dir) and os.path.isfile(candidate):
                return candidate
            if allow_legacy_absolute and os.path.isabs(path):
                return os.path.abspath(os.path.expanduser(path))
            return ""
        if allow_legacy_absolute and os.path.isabs(path):
            return os.path.abspath(os.path.expanduser(path))
        return ""

    def _theme_asset_dir(self, package_dir):
        return os.path.join(package_dir, ASSET_DIRNAME)

    def _theme_json_path(self, package_dir):
        return os.path.join(package_dir, "theme.json")

    def _package_dir_from_theme_path(self, path):
        path = os.path.abspath(path)
        if os.path.basename(path) == "theme.json":
            return os.path.dirname(path)
        return path

    def _copy_asset_into_package(self, source_path, package_dir, prefix="asset"):
        source_path = os.path.abspath(os.path.expanduser(source_path))
        if not os.path.isfile(source_path):
            raise FileNotFoundError(source_path)
        asset_dir = self._theme_asset_dir(package_dir)
        os.makedirs(asset_dir, exist_ok=True)
        stem = os.path.basename(source_path) or prefix
        base, ext = os.path.splitext(stem)
        if not base:
            base = prefix
        safe_base = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base)[:80] or prefix
        safe_ext = "".join(ch for ch in ext if ch.isalnum() or ch == ".")[:12]
        candidate = os.path.join(asset_dir, safe_base + safe_ext)
        index = 1
        while os.path.exists(candidate) and not os.path.samefile(source_path, candidate):
            candidate = os.path.join(asset_dir, f"{safe_base}_{index}{safe_ext}")
            index += 1
        if not os.path.exists(candidate):
            import shutil
            shutil.copy2(source_path, candidate)
        return os.path.realpath(candidate)

    def _prepare_data_for_package(self, name, package_dir):
        os.makedirs(package_dir, exist_ok=True)
        os.makedirs(self._theme_asset_dir(package_dir), exist_ok=True)
        data = self._theme_data_from_current(name)
        data["version"] = THEME_VERSION
        data["name"] = name
        for key in ("background_image_path",):
            source = data.get(key, "")
            if source:
                target = self._copy_asset_into_package(source, package_dir, "background")
                data[key] = os.path.relpath(target, package_dir).replace(os.sep, "/")
            else:
                data[key] = ""
        for item in data.get("images", []):
            source = item.get("path", "")
            if source:
                target = self._copy_asset_into_package(source, package_dir, "image")
                item["path"] = os.path.relpath(target, package_dir).replace(os.sep, "/")
        for clock in data.get("clocks", []):
            if not isinstance(clock, dict):
                continue
            digit_paths = clock.get("nixie_digit_paths", {})
            if not isinstance(digit_paths, dict):
                digit_paths = {}
                clock["nixie_digit_paths"] = {}
            stored = {}
            for digit, source in digit_paths.items():
                if not source:
                    continue
                target = self._copy_asset_into_package(source, package_dir, f"nixie_{digit}")
                stored[str(digit)] = os.path.relpath(target, package_dir).replace(os.sep, "/")
            clock["nixie_digit_paths"] = stored
            custom_paths = clock.get("custom_digit_paths", {})
            if not isinstance(custom_paths, dict):
                clock["custom_digit_paths"] = {}
                continue
            custom_stored = {}
            for digit, source in custom_paths.items():
                if str(digit) not in "0123456789" and str(digit) != "colon" or not source:
                    continue
                target = self._copy_asset_into_package(source, package_dir, f"digit_{digit}")
                custom_stored[str(digit)] = os.path.relpath(target, package_dir).replace(os.sep, "/")
            clock["custom_digit_paths"] = custom_stored
        return data

    def _load_pil_image_safely(self, path):
        if Image is None or ImageTk is None:
            raise RuntimeError("Pillow is required for image widgets.")
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        try:
            size_bytes = os.path.getsize(path)
        except OSError as exc:
            raise OSError(str(exc)) from exc
        if size_bytes > MAX_IMAGE_FILE_BYTES:
            raise ValueError(f"Image file is too large (limit {MAX_IMAGE_FILE_BYTES // (1024 * 1024)} MB).")
        try:
            with Image.open(path) as opened:
                width, height = opened.size
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image dimensions are too large.")
                opened.load()
                return opened.convert("RGBA").copy()
        except (OSError, ValueError):
            raise
        except Exception as exc:
            raise ValueError(f"Unsupported or invalid image: {exc}") from exc

    def _load_background_safely(self, path):
        if not path:
            return None
        return self._load_pil_image_safely(path)

    def _background_photo(self, w, h):
        source = self.background_image_source
        if source is None or ImageTk is None:
            return None
        # Fit-cover the background while keeping a cache keyed by viewport size.
        cache_key = (w, h)
        cached = self.background_image_cache.get(cache_key)
        if cached is not None:
            return cached
        scale = max(w / source.width, h / source.height)
        target_w = max(1, int(source.width * scale))
        target_h = max(1, int(source.height * scale))
        resized = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
        left = max(0, (target_w - w) // 2)
        top = max(0, (target_h - h) // 2)
        cropped = resized.crop((left, top, left + w, top + h))
        photo = ImageTk.PhotoImage(cropped)
        self.background_image_cache[cache_key] = photo
        return photo

    def _migrate_legacy_current_theme(self):
        legacy = os.path.join(LEGACY_THEME_DIR, "current.theme.json")
        if os.path.exists(CURRENT_THEME_FILE) or not os.path.isfile(legacy):
            return
        try:
            if os.path.getsize(legacy) > MAX_THEME_FILE_BYTES:
                return
            with open(legacy, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            version = self._bounded_int(data.get("version"), 1, 1, 99)
            if version > THEME_VERSION:
                return
            data = self._migrate_theme_data(data, version) if version < THEME_VERSION else dict(data)
            # Legacy formats stored external absolute asset paths. Do not read those
            # automatically; only the non-asset application state is migrated.
            data["background_image_path"] = ""
            data["images"] = []
            data["version"] = THEME_VERSION
            package = CURRENT_THEME_PACKAGE
            os.makedirs(package, exist_ok=True)
            self._apply_theme_data(data, package_dir=package, allow_legacy_absolute=False)
            self.current_theme_name = data.get("name") or "Current"
            self.current_theme_path = CURRENT_THEME_FILE
            self._autosave_theme_now()
        except (OSError, ValueError, json.JSONDecodeError, tk.TclError):
            pass

    def _parse_command_line_theme(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--theme", dest="theme", default="")
        parser.add_argument("--theme-file", dest="theme_file", default="")
        try:
            args, _ = parser.parse_known_args()
        except SystemExit:
            return ""
        return args.theme_file or args.theme

    def _ensure_theme_dir(self):
        try:
            os.makedirs(THEME_DIR, exist_ok=True)
        except OSError:
            pass

    def _theme_path_for_name(self, name):
        safe = "".join(ch for ch in name.strip() if ch.isalnum() or ch in " _-").strip()
        if not safe:
            return ""
        return os.path.join(THEME_DIR, safe + THEME_PACKAGE_SUFFIX)

    def _ensure_theme_defaults(self):
        if not self.current_theme_path:
            self.current_theme_name = self.current_theme_name or "Current"
            self.current_theme_path = CURRENT_THEME_FILE

    def list_themes(self):
        self._ensure_theme_dir()
        items = []
        try:
            for filename in sorted(os.listdir(THEME_DIR)):
                if filename.endswith(THEME_PACKAGE_SUFFIX) and os.path.isdir(os.path.join(THEME_DIR, filename)) and filename != os.path.basename(CURRENT_THEME_PACKAGE):
                    items.append(filename[:-len(THEME_PACKAGE_SUFFIX)])
        except OSError:
            pass
        return items

    def _refresh_theme_menu(self):
        if self.theme_menu is None:
            return
        try:
            end = self.theme_menu.index("end")
            for index in range(end, 2, -1):
                self.theme_menu.delete(index)
        except tk.TclError:
            return
        self.theme_menu.add_separator()
        themes = self.list_themes()
        if not themes:
            self.theme_menu.add_command(label="No saved themes", state="disabled")
        else:
            for name in themes:
                self.theme_menu.add_command(
                    label=name,
                    command=lambda n=name: self.load_theme(n, silent=False)
                )
        self.theme_menu.add_separator()
        self.theme_menu.add_command(label="Open Theme File...", command=self.open_theme_file)

    def _theme_data_from_current(self, name):
        return {
            "version": THEME_VERSION,
            "name": name,
            "background_color": self.background_color,
            "background_image_path": self.background_image_path,
            "image_label_color": self.image_label_color,
            "clocks": [asdict(c) for c in self.clocks],
            "images": [asdict(img) for img in self.images],
            "quotes": [asdict(q) for q in self.quotes],
            "ampm_widgets": [asdict(w) for w in self.ampm_widgets],
            "day_widgets": [asdict(w) for w in self.day_widgets],
            "date_widgets": [asdict(w) for w in self.date_widgets],
            "next_id": self.next_id,
            "next_image_id": self.next_image_id,
            "next_quote_id": self.next_quote_id,
            "next_ampm_id": self.next_ampm_id,
            "next_day_id": self.next_day_id,
            "next_date_id": self.next_date_id,
            "geometry": self.geometry(),
            "fullscreen": bool(self.fullscreen),
        }

    def _write_theme(self, path, data):
        directory = os.path.dirname(os.path.abspath(path)) or "."
        temp_path = None
        backup_tmp = None
        try:
            os.makedirs(directory, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".theme-", suffix=".tmp", dir=directory, text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(path):
                backup = path + ".bak"
                fd_b, backup_tmp = tempfile.mkstemp(prefix=".theme-backup-", suffix=".tmp", dir=directory)
                with os.fdopen(fd_b, "wb") as dst, open(path, "rb") as src:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                    dst.flush()
                    os.fsync(dst.fileno())
                os.replace(backup_tmp, backup)
                backup_tmp = None
            os.replace(temp_path, path)
            temp_path = None
            return True
        except (OSError, TypeError, ValueError) as exc:
            self._last_autosave_error = str(exc)
            return False
        finally:
            for candidate in (temp_path, backup_tmp):
                if candidate:
                    try:
                        os.unlink(candidate)
                    except OSError:
                        pass

    def _autosave_theme_now(self):
        package = self._package_dir_from_theme_path(self.current_theme_path or CURRENT_THEME_FILE)
        if not package:
            package = CURRENT_THEME_PACKAGE
        os.makedirs(package, exist_ok=True)
        data = self._prepare_data_for_package(self.current_theme_name or "Current", package)
        ok = self._write_theme(self._theme_json_path(package), data)
        if ok and os.path.abspath(package) != os.path.abspath(CURRENT_THEME_PACKAGE):
            current_data = self._prepare_data_for_package(self.current_theme_name or "Current", CURRENT_THEME_PACKAGE)
            ok = self._write_theme(self._theme_json_path(CURRENT_THEME_PACKAGE), current_data) and ok
        if ok:
            self.current_theme_path = self._theme_json_path(package)
            self._last_autosave_error = ""
        return ok

    def create_theme_from_current(self):
        name = simpledialog.askstring("New Theme", "Theme name:", parent=self)
        if not name or not name.strip():
            return
        package = self._theme_path_for_name(name)
        if not package or os.path.abspath(package) == os.path.abspath(CURRENT_THEME_PACKAGE):
            messagebox.showerror("Theme", "Please enter a valid theme name.")
            return
        if os.path.exists(package) and not messagebox.askyesno("Theme Exists", "That theme already exists. Replace it?", parent=self):
            return
        try:
            data = self._prepare_data_for_package(name.strip(), package)
            if self._write_theme(self._theme_json_path(package), data):
                self.current_theme_name = name.strip()
                self.current_theme_path = self._theme_json_path(package)
                self._autosave_theme_now()
                self._refresh_theme_menu()
            else:
                raise OSError(self._last_autosave_error or "Could not save the theme.")
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Theme", str(exc), parent=self)

    def save_current_theme(self):
        # Save the full app state to the active theme and to the startup snapshot.
        if not self.current_theme_path or os.path.abspath(self.current_theme_path) == os.path.abspath(CURRENT_THEME_FILE):
            self.current_theme_name = self.current_theme_name or "Current"
            self.current_theme_path = CURRENT_THEME_FILE
        if not self._autosave_theme_now():
            messagebox.showerror("Theme", self._last_autosave_error or "Could not save the theme.", parent=self)
            return
        self._refresh_theme_menu()

    def save_current_theme_as(self):
        initial = self.current_theme_name if self.current_theme_name and self.current_theme_name != "Default" else "My Theme"
        name = simpledialog.askstring("Save Theme As", "Theme name:", initialvalue=initial, parent=self)
        if not name or not name.strip():
            return
        package = self._theme_path_for_name(name)
        if not package or os.path.abspath(package) == os.path.abspath(CURRENT_THEME_PACKAGE):
            messagebox.showerror("Theme", "Please enter a valid theme name.")
            return
        if os.path.exists(package) and not messagebox.askyesno("Theme Exists", "That theme already exists. Replace it?", parent=self):
            return
        try:
            data = self._prepare_data_for_package(name.strip(), package)
            if self._write_theme(self._theme_json_path(package), data):
                self.current_theme_name = name.strip()
                self.current_theme_path = self._theme_json_path(package)
                self._autosave_theme_now()
                self._refresh_theme_menu()
            else:
                raise OSError(self._last_autosave_error or "Could not save the theme.")
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Theme", str(exc), parent=self)

    def open_theme_file(self):
        path = filedialog.askopenfilename(
            title="Open Theme",
            filetypes=[("Theme package file", "theme.json"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.load_theme(path, silent=False)

    def _resolve_theme_path(self, theme):
        if not theme:
            return ""
        if os.path.isfile(theme) and os.path.basename(theme) == "theme.json":
            return os.path.abspath(theme)
        candidates = [self._theme_path_for_name(theme)]
        if theme.endswith(THEME_PACKAGE_SUFFIX):
            candidates.append(os.path.join(THEME_DIR, theme))
        elif not os.path.basename(theme).endswith(THEME_EXT):
            candidates.append(os.path.join(THEME_DIR, theme + THEME_PACKAGE_SUFFIX))
        for candidate in candidates:
            if candidate and os.path.isdir(candidate):
                path = self._theme_json_path(candidate)
                if os.path.isfile(path):
                    return path
        return ""

    def load_theme(self, theme, silent=False):
        path = self._resolve_theme_path(theme)
        if not path:
            if not silent:
                messagebox.showerror("Theme", f"Theme not found: {theme}")
            return False
        try:
            if os.path.getsize(path) > MAX_THEME_FILE_BYTES:
                raise ValueError(f"Theme file is too large (limit {MAX_THEME_FILE_BYTES // (1024 * 1024)} MB).")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            if not silent:
                messagebox.showerror("Theme", str(exc))
            return False
        if not isinstance(data, dict):
            if not silent:
                messagebox.showerror("Theme", "Invalid theme file: the root value must be a JSON object.")
            return False
        version = self._bounded_int(data.get("version"), 1, 1, 99)
        if version > THEME_VERSION:
            if not silent:
                messagebox.showerror("Theme", f"This theme uses a newer format (version {version}).")
            return False
        if version < THEME_VERSION:
            data = self._migrate_theme_data(data, version)
        package_dir = self._package_dir_from_theme_path(path)
        try:
            self._apply_theme_data(data, package_dir=package_dir, allow_legacy_absolute=False)
        except (TypeError, ValueError, KeyError, tk.TclError, OSError) as exc:
            if not silent:
                messagebox.showerror("Theme", f"Invalid theme file.\n\n{exc}")
            return False
        self.current_theme_path = os.path.abspath(path)
        self.current_theme_name = data.get("name") or os.path.basename(os.path.dirname(path)).replace(THEME_PACKAGE_SUFFIX, "")
        self._refresh_theme_menu()
        self.draw()
        return True

    def _migrate_theme_data(self, data, version):
        migrated = dict(data)
        # Versions 1/2 used the same fields for the legacy style representation.
        # Preserve complete-state fields when present and translate legacy style-only themes.
        if version <= 2 and "clocks" not in migrated:
            clocks = []
            for kind_key, kind_name, x in (("digital", "digital", 0.35), ("analogue", "analogue", 0.72)):
                style = migrated.get(kind_key)
                if isinstance(style, dict):
                    clocks.append({
                        "clock_id": len(clocks) + 1,
                        "kind": kind_name,
                        "x": x,
                        "y": 0.45,
                        "size": 0.28 if kind_name == "digital" else 0.34,
                        "timezone": "local",
                        "label": "",
                        "font_family": style.get("font_family", "DejaVu Sans"),
                        "font_weight": style.get("font_weight", "normal"),
                        "text_color": style.get("text_color", "#FFFFFF"),
                        "accent_color": style.get("accent_color", "#FFFFFF"),
                        "face_color": style.get("face_color", "#111111"),
                        "face_transparent": style.get("face_transparent", False),
                        "show_seconds": style.get("show_seconds", True),
                        "use_24h": style.get("use_24h", True),
                    })
            migrated["clocks"] = clocks
            migrated.setdefault("images", [])
            migrated.setdefault("quotes", [])
            migrated.setdefault("next_id", len(clocks) + 1)
            migrated.setdefault("next_image_id", 1)
            migrated.setdefault("next_quote_id", 1)
            migrated.setdefault("ampm_widgets", [])
            migrated.setdefault("day_widgets", [])
            migrated.setdefault("date_widgets", [])
            migrated.setdefault("next_ampm_id", 1)
            migrated.setdefault("next_day_id", 1)
            migrated.setdefault("next_date_id", 1)
            migrated.setdefault("fullscreen", False)
            for clock in migrated.get("clocks", []):
                if isinstance(clock, dict):
                    clock.setdefault("segment_off_transparent", True)
                    clock.setdefault("nixie_digit_paths", {})
                clock.setdefault("custom_digit_paths", {})
        # Split the former combined Day widget into separate Day and Date widgets.
        legacy_days = migrated.get("day_widgets", [])
        if isinstance(legacy_days, list):
            converted_days = []
            converted_dates = list(migrated.get("date_widgets", [])) if isinstance(migrated.get("date_widgets", []), list) else []
            next_day = max([int(x.get("day_id", 0)) for x in legacy_days if isinstance(x, dict) and str(x.get("day_id", "")).isdigit()] + [0]) + 1
            next_date = 1
            for raw in legacy_days:
                if not isinstance(raw, dict):
                    continue
                mode = str(raw.get("format_type", "weekday_date"))
                day_raw = dict(raw)
                day_raw.pop("format_type", None)
                day_raw["day_format"] = "full"
                converted_days.append(day_raw)
                if mode in {"date", "weekday_date"}:
                    date_raw = dict(raw)
                    date_raw.pop("format_type", None)
                    date_raw["date_id"] = next_date
                    date_raw["date_format"] = "long"
                    if mode == "weekday_date":
                        date_raw["y"] = min(0.99, float(raw.get("y", 0.65)) + 0.08)
                    converted_dates.append(date_raw)
                    next_date += 1
            migrated["day_widgets"] = converted_days
            migrated["date_widgets"] = converted_dates
            migrated["next_date_id"] = max(migrated.get("next_date_id", 1), next_date)
        migrated.setdefault("ampm_widgets", [])
        migrated.setdefault("day_widgets", [])
        migrated.setdefault("date_widgets", [])
        for clock in migrated.get("clocks", []):
            if isinstance(clock, dict):
                clock.setdefault("segment_off_transparent", True)
                clock.setdefault("nixie_digit_paths", {})
                clock.setdefault("custom_digit_paths", {})
        migrated.setdefault("next_ampm_id", 1)
        migrated.setdefault("next_day_id", 1)
        migrated.setdefault("next_date_id", 1)
        migrated["version"] = THEME_VERSION
        return migrated

    def _apply_theme_data(self, data, package_dir=None, allow_legacy_absolute=False):
        self._restoring_settings = True
        try:
            self.background_color = self._safe_colour(data.get("background_color"), "#101010")
            self.image_label_color = self._safe_colour(data.get("image_label_color"), "#FFFFFF")
            raw_bg = self._safe_text(data.get("background_image_path"), "", 4096).strip()
            self.background_image_path = self._resolve_theme_asset_path(package_dir, raw_bg, allow_legacy_absolute) if raw_bg else ""
            self.background_image = None
            self.background_image_source = None
            self.background_image_signature = None
            self.background_image_cache.clear()
            if self.background_image_path:
                try:
                    self.background_image_source = self._load_background_safely(self.background_image_path)
                    self.background_image_signature = self._image_signature(self.background_image_path)
                except (OSError, ValueError, RuntimeError):
                    self.background_image_path = ""
            self.canvas.configure(bg=self.background_color)

            self.clocks = []
            raw_clocks = data.get("clocks", [])
            if isinstance(raw_clocks, list):
                used = set()
                for raw in raw_clocks[:64]:
                    c = self._normalise_clock(raw, len(used) + 1)
                    if c and c.clock_id not in used:
                        used.add(c.clock_id)
                        self.clocks.append(c)
            self.next_id = max(self._bounded_int(data.get("next_id"), 1, 1, 2_000_000_001),
                               max([c.clock_id for c in self.clocks], default=0) + 1)

            # Resolve Nixie digit assets relative to the active theme package and cache them per clock.
            self.nixie_digit_sources = {}
            self.nixie_digit_refs = {}
            self.nixie_digit_cache = {}
            self.custom_digit_sources = {}
            self.custom_digit_refs = {}
            self.custom_digit_cache = {}
            for c in self.clocks:
                valid_paths = {}
                for digit, rel_path in c.nixie_digit_paths.items():
                    resolved = self._resolve_theme_asset_path(package_dir, rel_path, allow_legacy_absolute=False)
                    if not resolved:
                        continue
                    try:
                        source = self._load_pil_image_safely(resolved)
                    except (OSError, ValueError, RuntimeError):
                        continue
                    valid_paths[digit] = resolved
                    self.nixie_digit_sources[(c.clock_id, digit)] = source
                c.nixie_digit_paths = valid_paths

                custom_valid = {}
                for digit, rel_path in c.custom_digit_paths.items():
                    resolved = self._resolve_theme_asset_path(package_dir, rel_path, allow_legacy_absolute=False)
                    if not resolved:
                        continue
                    try:
                        source = self._load_pil_image_safely(resolved)
                    except (OSError, ValueError, RuntimeError):
                        continue
                    custom_valid[digit] = resolved
                    self.custom_digit_sources[(c.clock_id, digit)] = source
                c.custom_digit_paths = custom_valid

            self.images = []
            self.image_sources.clear()
            self.image_refs.clear()
            self.image_cache.clear()
            self.image_source_signatures.clear()
            raw_images = data.get("images", [])
            if isinstance(raw_images, list):
                used = set()
                for raw in raw_images[:MAX_IMAGE_WIDGETS]:
                    img = self._normalise_image(raw, len(used) + 1, asset_root=package_dir, allow_legacy_absolute=allow_legacy_absolute)
                    if not img or img.image_id in used:
                        continue
                    try:
                        source = self._load_pil_image_safely(img.path)
                    except (OSError, ValueError, RuntimeError):
                        continue
                    used.add(img.image_id)
                    self.image_sources[img.image_id] = source
                    self.image_source_signatures[img.image_id] = self._image_signature(img.path)
                    self.images.append(img)
            self.next_image_id = max(self._bounded_int(data.get("next_image_id"), 1, 1, 2_000_000_001),
                                     max([i.image_id for i in self.images], default=0) + 1)

            self.quotes = []
            self.quote_font_cache.clear()
            raw_quotes = data.get("quotes", [])
            if isinstance(raw_quotes, list):
                used = set()
                for raw in raw_quotes[:32]:
                    q = self._normalise_quote(raw, len(used) + 1)
                    if q and q.quote_id not in used:
                        used.add(q.quote_id)
                        self.quotes.append(q)
            self.next_quote_id = max(self._bounded_int(data.get("next_quote_id"), 1, 1, 2_000_000_001),
                                     max([q.quote_id for q in self.quotes], default=0) + 1)

            self.ampm_widgets = []
            raw_ampm = data.get("ampm_widgets", [])
            if isinstance(raw_ampm, list):
                used = set()
                for raw in raw_ampm[:MAX_AUX_WIDGETS]:
                    item = self._normalise_ampm(raw, len(used) + 1)
                    if item and item.ampm_id not in used:
                        used.add(item.ampm_id)
                        self.ampm_widgets.append(item)
            self.next_ampm_id = max(self._bounded_int(data.get("next_ampm_id"), 1, 1, 2_000_000_001),
                                    max([w.ampm_id for w in self.ampm_widgets], default=0) + 1)

            self.day_widgets = []
            raw_days = data.get("day_widgets", [])
            if isinstance(raw_days, list):
                used = set()
                for raw in raw_days[:MAX_AUX_WIDGETS]:
                    item = self._normalise_day(raw, len(used) + 1)
                    if item and item.day_id not in used:
                        used.add(item.day_id)
                        self.day_widgets.append(item)
            self.next_day_id = max(self._bounded_int(data.get("next_day_id"), 1, 1, 2_000_000_001),
                                   max([w.day_id for w in self.day_widgets], default=0) + 1)

            self.date_widgets = []
            raw_dates = data.get("date_widgets", [])
            if isinstance(raw_dates, list):
                used = set()
                for raw in raw_dates[:MAX_AUX_WIDGETS]:
                    item = self._normalise_date(raw, len(used) + 1)
                    if item and item.date_id not in used:
                        used.add(item.date_id)
                        self.date_widgets.append(item)
            self.next_date_id = max(self._bounded_int(data.get("next_date_id"), 1, 1, 2_000_000_001),
                                    max([w.date_id for w in self.date_widgets], default=0) + 1)

            geometry = self._safe_text(data.get("geometry"), "", 100)
            if geometry:
                try:
                    self.geometry(geometry)
                except tk.TclError:
                    pass
            fullscreen = self._safe_bool(data.get("fullscreen"), False)
            self.fullscreen = fullscreen
            self.attributes("-fullscreen", fullscreen)
            if fullscreen:
                self.toolbar.place_forget()
            else:
                self.toolbar.place(relx=0, rely=0, relwidth=1, height=34)
            self.selected_id = self.clocks[0].clock_id if self.clocks else None
            self.selected_image_id = None
            self.selected_quote_id = None
            self.selected_ampm_id = None
            self.selected_day_id = None
            self.selected_date_id = None
        finally:
            self._restoring_settings = False

    @staticmethod
    def _image_signature(path):
        try:
            stat = os.stat(path)
            return (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None

    # -------------------------------------------------------------------
    # ---------------------------- clocks -------------------------------
    def add_clock(self, kind="digital", x=None, y=None, size=None):
        if x is None or y is None:
            # Stagger new clocks so they are visible instead of being stacked exactly.
            index = len(self.clocks)
            x = 0.20 + (index % 3) * 0.30
            y = 0.30 + ((index // 3) % 2) * 0.38
        if size is None:
            size = 0.28 if kind == "digital" else (0.30 if kind in {"segment", "nixie"} else 0.34)

        clock = ClockData(
            clock_id=self.next_id,
            kind=kind,
            x=max(0.02, min(0.98, x)),
            y=max(0.08, min(0.98, y)),
            size=size,
        )
        self.next_id += 1
        self.clocks.append(clock)
        self.selected_id = clock.clock_id
        self.selected_image_id = None
        self.selected_quote_id = None
        self.draw()
        self._schedule_autosave()

    def get_clock(self, clock_id):
        return next((c for c in self.clocks if c.clock_id == clock_id), None)

    def get_image(self, image_id):
        return next((img for img in self.images if img.image_id == image_id), None)

    def get_quote(self, quote_id):
        return next((q for q in self.quotes if q.quote_id == quote_id), None)

    def selected_clock(self):
        return self.get_clock(self.selected_id)

    def get_ampm(self, widget_id):
        return next((w for w in self.ampm_widgets if w.ampm_id == widget_id), None)

    def get_day(self, widget_id):
        return next((w for w in self.day_widgets if w.day_id == widget_id), None)

    def get_date(self, widget_id):
        return next((w for w in self.date_widgets if w.date_id == widget_id), None)

    def selected_ampm(self):
        return self.get_ampm(self.selected_ampm_id)

    def selected_day(self):
        return self.get_day(self.selected_day_id)

    def selected_date(self):
        return self.get_date(self.selected_date_id)

    def edit_selected_ampm(self):
        if self.selected_ampm():
            LinkedTextEditor(self, self.selected_ampm(), "ampm")

    def edit_selected_day(self):
        if self.selected_day():
            LinkedTextEditor(self, self.selected_day(), "day")

    def edit_selected_date(self):
        if self.selected_date():
            LinkedTextEditor(self, self.selected_date(), "date")

    def delete_selected_ampm(self):
        if self.selected_ampm_id is None:
            return
        self.ampm_widgets = [w for w in self.ampm_widgets if w.ampm_id != self.selected_ampm_id]
        self.selected_ampm_id = self.ampm_widgets[-1].ampm_id if self.ampm_widgets else None
        self.draw(); self._schedule_autosave()

    def delete_selected_day(self):
        if self.selected_day_id is None:
            return
        self.day_widgets = [w for w in self.day_widgets if w.day_id != self.selected_day_id]
        self.selected_day_id = self.day_widgets[-1].day_id if self.day_widgets else None
        self.draw(); self._schedule_autosave()

    def delete_selected_date(self):
        if self.selected_date_id is None:
            return
        self.date_widgets = [w for w in self.date_widgets if w.date_id != self.selected_date_id]
        self.selected_date_id = self.date_widgets[-1].date_id if self.date_widgets else None
        self.draw(); self._schedule_autosave()

    def add_ampm_dialog(self):
        LinkedTextEditor(self, None, "ampm", initial_position=(self.context_x, self.context_y))

    def add_day_dialog(self):
        LinkedTextEditor(self, None, "day", initial_position=(self.context_x, self.context_y))

    def add_date_dialog(self):
        LinkedTextEditor(self, None, "date", initial_position=(self.context_x, self.context_y))

    def add_ampm_widget(self, linked_clock_id=None, x=None, y=None, size=0.16, **kwargs):
        if len(self.ampm_widgets) >= MAX_AUX_WIDGETS:
            messagebox.showerror("AM/PM Widget", f"The maximum of {MAX_AUX_WIDGETS} AM/PM widgets has been reached.")
            return None
        clock = self.get_clock(linked_clock_id) if linked_clock_id is not None else (self.clocks[0] if self.clocks else None)
        if clock is None:
            return None
        if x is None or y is None:
            x, y = self.context_x, self.context_y
        item = AmpmData(
            ampm_id=self.next_ampm_id, linked_clock_id=clock.clock_id,
            x=max(0.02, min(0.98, x)), y=max(0.05, min(0.98, y)),
            size=max(0.08, min(0.80, size)),
            font_family=self._safe_font_family(kwargs.get("font_family")),
            font_weight=self._safe_font_weight(kwargs.get("font_weight"), "bold"),
            text_color=self._safe_colour(kwargs.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(kwargs.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(kwargs.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(kwargs.get("face_transparent"), True),
            label=self._safe_text(kwargs.get("label"), "", 200),
        )
        self.next_ampm_id += 1
        self.ampm_widgets.append(item)
        self.selected_ampm_id = item.ampm_id; self.selected_id = None; self.selected_image_id = None; self.selected_quote_id = None; self.selected_day_id = None; self.selected_date_id = None
        self.draw(); self._schedule_autosave()
        return item

    def add_day_widget(self, linked_clock_id=None, x=None, y=None, size=0.28, **kwargs):
        if len(self.day_widgets) >= MAX_AUX_WIDGETS:
            messagebox.showerror("Day Widget", f"The maximum of {MAX_AUX_WIDGETS} day widgets has been reached.")
            return None
        clock = self.get_clock(linked_clock_id) if linked_clock_id is not None else (self.clocks[0] if self.clocks else None)
        if clock is None:
            return None
        if x is None or y is None:
            x, y = self.context_x, self.context_y
        item = DayData(
            day_id=self.next_day_id, linked_clock_id=clock.clock_id,
            x=max(0.02, min(0.98, x)), y=max(0.05, min(0.98, y)),
            size=max(0.08, min(0.95, size)),
            day_format=self._safe_text(kwargs.get("day_format"), "full", 20).lower(),
            font_family=self._safe_font_family(kwargs.get("font_family")),
            font_weight=self._safe_font_weight(kwargs.get("font_weight")),
            text_color=self._safe_colour(kwargs.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(kwargs.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(kwargs.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(kwargs.get("face_transparent"), True),
            label=self._safe_text(kwargs.get("label"), "", 200),
        )
        if item.day_format not in {"full", "short", "upper"}:
            item.day_format = "full"
        self.next_day_id += 1
        self.day_widgets.append(item)
        self.selected_day_id = item.day_id; self.selected_id = None; self.selected_image_id = None; self.selected_quote_id = None; self.selected_ampm_id = None; self.selected_date_id = None
        self.draw(); self._schedule_autosave()
        return item

    def add_date_widget(self, linked_clock_id=None, x=None, y=None, size=0.30, **kwargs):
        if len(self.date_widgets) >= MAX_AUX_WIDGETS:
            messagebox.showerror("Date Widget", f"The maximum of {MAX_AUX_WIDGETS} date widgets has been reached.")
            return None
        clock = self.get_clock(linked_clock_id) if linked_clock_id is not None else (self.clocks[0] if self.clocks else None)
        if clock is None:
            return None
        if x is None or y is None:
            x, y = self.context_x, self.context_y
        item = DateData(
            date_id=self.next_date_id, linked_clock_id=clock.clock_id,
            x=max(0.02, min(0.98, x)), y=max(0.05, min(0.98, y)),
            size=max(0.08, min(0.95, size)),
            date_format=self._safe_text(kwargs.get("date_format"), "long", 40).lower(),
            font_family=self._safe_font_family(kwargs.get("font_family")),
            font_weight=self._safe_font_weight(kwargs.get("font_weight")),
            text_color=self._safe_colour(kwargs.get("text_color"), "#FFFFFF"),
            accent_color=self._safe_colour(kwargs.get("accent_color"), "#FFFFFF"),
            face_color=self._safe_colour(kwargs.get("face_color"), "#111111"),
            face_transparent=self._safe_bool(kwargs.get("face_transparent"), True),
            label=self._safe_text(kwargs.get("label"), "", 200),
        )
        if item.date_format not in {"long", "short", "numeric_eu", "numeric_us", "iso", "weekday_long"}:
            item.date_format = "long"
        self.next_date_id += 1
        self.date_widgets.append(item)
        self.selected_date_id = item.date_id; self.selected_id = None; self.selected_image_id = None; self.selected_quote_id = None; self.selected_ampm_id = None; self.selected_day_id = None
        self.draw(); self._schedule_autosave()
        return item

    def edit_selected_clock(self):
        c = self.selected_clock()
        if c:
            ClockEditor(self, c)

    def delete_selected_clock(self):
        if self.selected_id is None:
            return
        c = self.selected_clock()
        if c is None:
            return
        self.clocks = [item for item in self.clocks if item.clock_id != c.clock_id]
        self.selected_id = self.clocks[-1].clock_id if self.clocks else None
        self.selected_image_id = None
        self.draw()
        self._schedule_autosave()

    def delete_selected_image(self):
        if self.selected_image_id is None:
            return
        self.images = [img for img in self.images if img.image_id != self.selected_image_id]
        self.image_sources.pop(self.selected_image_id, None)
        self.image_refs.pop(self.selected_image_id, None)
        self.image_cache.pop(self.selected_image_id, None)
        self.image_source_signatures.pop(self.selected_image_id, None)
        self.selected_image_id = self.images[-1].image_id if self.images else None
        self.selected_quote_id = None
        self.draw()
        self._schedule_autosave()

    def edit_selected_image(self):
        img = self.get_image(self.selected_image_id)
        if img:
            ImageEditor(self, img)

    def edit_selected_quote(self):
        q = self.get_quote(self.selected_quote_id)
        if q:
            QuoteEditor(self, q)

    def edit_selected_any(self):
        if self.selected_id is not None:
            self.edit_selected_clock()
        elif self.selected_image_id is not None:
            self.edit_selected_image()
        elif self.selected_quote_id is not None:
            self.edit_selected_quote()
        elif self.selected_ampm_id is not None:
            self.edit_selected_ampm()
        elif self.selected_day_id is not None:
            self.edit_selected_day()
        elif self.selected_date_id is not None:
            self.edit_selected_date()

    def delete_selected_quote(self):
        if self.selected_quote_id is None:
            return
        self.quotes = [q for q in self.quotes if q.quote_id != self.selected_quote_id]
        self.selected_quote_id = self.quotes[-1].quote_id if self.quotes else None
        self.draw()
        self._schedule_autosave()

    def delete_selected_any(self):
        if self.selected_id is not None:
            self.delete_selected_clock()
        elif self.selected_image_id is not None:
            self.delete_selected_image()
        elif self.selected_quote_id is not None:
            self.delete_selected_quote()
        elif self.selected_ampm_id is not None:
            self.delete_selected_ampm()
        elif self.selected_day_id is not None:
            self.delete_selected_day()
        elif self.selected_date_id is not None:
            self.delete_selected_date()

    def change_selected_size(self, factor):
        c = self.selected_clock()
        if c:
            c.size = max(0.08, min(0.75, c.size * factor))
            self.draw()
            self._schedule_autosave()
            return
        img = self.get_image(self.selected_image_id)
        if img:
            img.size = max(0.04, min(0.95, img.size * factor))
            self.draw()
            self._schedule_autosave()
            return
        q = self.get_quote(self.selected_quote_id)
        if q:
            q.size = max(0.12, min(0.95, q.size * factor))
            self.draw()
            self._schedule_autosave()
            return
        a = self.selected_ampm()
        if a:
            a.size = max(0.08, min(0.80, a.size * factor))
            self.draw(); self._schedule_autosave(); return
        d = self.selected_day()
        if d:
            d.size = max(0.08, min(0.95, d.size * factor))
            self.draw(); self._schedule_autosave(); return
        dt = self.selected_date()
        if dt:
            dt.size = max(0.08, min(0.95, dt.size * factor))
            self.draw(); self._schedule_autosave(); return
        a = self.selected_ampm()
        if a:
            a.size = max(0.08, min(0.80, a.size * factor))
            self.draw(); self._schedule_autosave(); return
        d = self.selected_day()
        if d:
            d.size = max(0.08, min(0.95, d.size * factor))
            self.draw(); self._schedule_autosave()

    # --------------------------- drawing -------------------------------
    def update_clock(self):
        self.draw()
        self.after(200, self.update_clock)

    def _get_now(self, timezone_name):
        now = datetime.now().astimezone()
        if timezone_name == "local" or not timezone_name:
            return now
        if timezone_name.upper() == "UTC":
            return datetime.now(timezone.utc)
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except (ZoneInfoNotFoundError, ValueError):
            return now

    def _fit_font(self, text, family, weight, max_width, max_height, start_size):
        size = max(6, int(start_size))
        while size > 6:
            f = tkfont.Font(family=family, size=size, weight=weight)
            w = max(1, f.measure(text))
            h = max(1, f.metrics("linespace"))
            if w <= max_width and h <= max_height:
                return f
            size -= 1
        return tkfont.Font(family=family, size=6, weight=weight)

    def draw(self):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        if w < 20 or h < 20:
            return

        # Put the toolbar above the clock area by using its actual height.
        toolbar_h = 0 if self.fullscreen else 34
        available_top = toolbar_h

        self.canvas.delete("all")
        self._draw_background(w, h)

        # Draw clocks back-to-front; selected clock last for a clean highlight.
        ordered = [c for c in self.clocks if c.clock_id != self.selected_id]
        selected = self.selected_clock()
        if selected:
            ordered.append(selected)

        for img in self.images:
            self._draw_image(img, w, h, selected=(img.image_id == self.selected_image_id))

        for q in self.quotes:
            self._draw_quote(q, w, h, selected=(q.quote_id == self.selected_quote_id))
        for a in self.ampm_widgets:
            self._draw_ampm(a, w, h, selected=(a.ampm_id == self.selected_ampm_id))
        for d in self.day_widgets:
            self._draw_day(d, w, h, selected=(d.day_id == self.selected_day_id))
        for dt in self.date_widgets:
            self._draw_date(dt, w, h, selected=(dt.date_id == self.selected_date_id))

        for c in ordered:
            cy = available_top + c.y * max(1, h - available_top)
            cx = c.x * w
            if c.kind == "analogue":
                self._draw_analogue(c, cx, cy, w, h, selected=(c.clock_id == self.selected_id))
            elif c.kind == "segment":
                self._draw_segment(c, cx, cy, w, h, selected=(c.clock_id == self.selected_id))
            elif c.kind == "nixie":
                self._draw_nixie(c, cx, cy, w, h, selected=(c.clock_id == self.selected_id))
            elif c.kind == "custom_image":
                self._draw_custom_image_clock(c, cx, cy, w, h, selected=(c.clock_id == self.selected_id))
            else:
                self._draw_digital(c, cx, cy, w, h, selected=(c.clock_id == self.selected_id))

    def _draw_background(self, w, h):
        self.canvas.create_rectangle(0, 0, w, h, fill=self.background_color, outline="")
        if self.background_image_path:
            current_sig = self._image_signature(self.background_image_path)
            if current_sig != self.background_image_signature:
                try:
                    self.background_image_source = self._load_background_safely(self.background_image_path)
                    self.background_image_signature = current_sig
                    self.background_image_cache.clear()
                except (OSError, ValueError, RuntimeError):
                    self.background_image_source = None
                    self.background_image_path = ""
                    self.background_image_signature = None
                    self.background_image_cache.clear()
            photo = self._background_photo(w, h) if self.background_image_source is not None else None
            if photo is not None:
                self.background_image = photo
                self.canvas.create_image(w / 2, h / 2, image=photo, anchor="center")

    def _clock_bbox(self, c, cx, cy, w, h):
        radius = max(30, c.size * min(w, max(1, h - 34)) / 2)
        return cx - radius, cy - radius, cx + radius, cy + radius

    def _draw_digital(self, c, cx, cy, w, h, selected=False):
        now = self._get_now(c.timezone)
        if c.use_24h:
            fmt = "%H:%M:%S" if c.show_seconds else "%H:%M"
        else:
            fmt = "%I:%M:%S" if c.show_seconds else "%I:%M"
            if c.show_ampm:
                fmt += " %p"
        text = now.strftime(fmt)

        _, _, _, diameter = 0, 0, 0, max(1, c.size * min(w, max(1, h - 34)))
        max_width = max(40, diameter * 1.55)
        max_height = max(30, diameter * 0.55)
        font = self._fit_font(text, c.font_family, c.font_weight, max_width, max_height, diameter * 0.30)

        bbox = self._clock_bbox(c, cx, cy, w, h)
        x1, y1, x2, y2 = bbox
        if c.face_color and not c.face_transparent:
            pad = diameter * 0.03
            self.canvas.create_round_rect if False else None
            self.canvas.create_rectangle(x1 + pad, y1 + pad, x2 - pad, y2 - pad,
                                         fill=c.face_color, outline="", tags=(f"clock:{c.clock_id}",))

        if selected:
            tag = f"clock:{c.clock_id}"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=("#FFFFFF" if c.accent_transparent else c.accent_color), width=2,
                                         dash=(5, 3), tags=(tag,))
            self._draw_resize_handle(x2, y2, "#FFFFFF" if c.accent_transparent else c.accent_color, tag)

        self.canvas.create_text(cx, cy, text=text, font=font, fill="" if c.text_transparent else c.text_color,
                                anchor="center", tags=(f"clock:{c.clock_id}",))
        if c.label:
            lf = tkfont.Font(family=c.font_family, size=max(7, int(font.cget("size") * 0.26)))
            self.canvas.create_text(cx, y2 - max(8, font.metrics("linespace") * 0.15),
                                    text=c.label, font=lf, fill="" if c.accent_transparent else c.accent_color,
                                    anchor="s", tags=(f"clock:{c.clock_id}",))

    def _digital_text(self, c):
        now = self._get_now(c.timezone)
        if c.use_24h:
            fmt = "%H:%M:%S" if c.show_seconds else "%H:%M"
        else:
            fmt = "%I:%M:%S" if c.show_seconds else "%I:%M"
        return now.strftime(fmt), now

    @staticmethod
    def _dim_colour(value):
        try:
            value = value.lstrip("#")
            if len(value) == 6:
                r, g, b = (int(value[i:i+2], 16) for i in (0, 2, 4))
                return "#%02X%02X%02X" % (max(3, r // 5), max(3, g // 5), max(3, b // 5))
        except Exception:
            pass
        return "#181818"

    def _draw_segment(self, c, cx, cy, w, h, selected=False):
        text, now = self._digital_text(c)
        diameter = max(120.0, c.size * min(w, max(1, h - 34)))
        digit_h = diameter * 0.42
        digit_w = digit_h * 0.56
        gap = digit_w * 0.28
        seg_t = max(4.0, digit_h * 0.105)
        mapping = {
            "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg",
            "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc",
            "8": "abcdefg", "9": "abcdfg",
        }
        total_w = sum((digit_w if ch.isdigit() else digit_w * 0.40) + gap for ch in text) - gap
        x = cx - total_w / 2
        y = cy - digit_h / 2
        tag = f"clock:{c.clock_id}"

        # Draw the face FIRST. The previous implementation drew it after the segments,
        # which covered the lit segments and made the display appear completely black.
        x1, y1, x2, y2 = self._clock_bbox(c, cx, cy, w, h)
        if c.face_color and not c.face_transparent:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=c.face_color, outline="", tags=(tag,))

        on = "" if c.accent_transparent else c.accent_color
        if not on:
            on = "" if c.text_transparent else c.text_color
        if not on:
            on = "#FF2A2A"
        off = "" if c.segment_off_transparent else (self._dim_colour(c.face_color) if not c.face_transparent else "#171717")

        for ch in text:
            if ch == ":":
                r = max(2.5, seg_t * 0.42)
                dot_x = x + digit_w * 0.18
                for frac in (0.31, 0.69):
                    yy = y + digit_h * frac
                    self.canvas.create_oval(dot_x-r, yy-r, dot_x+r, yy+r, fill=on, outline="", tags=(tag,))
                x += digit_w * 0.40 + gap
                continue
            active = mapping.get(ch, "")
            segs = {
                "a": (x+seg_t, y, x+digit_w-seg_t, y+seg_t),
                "b": (x+digit_w-seg_t, y+seg_t, x+digit_w, y+digit_h/2-seg_t/2),
                "c": (x+digit_w-seg_t, y+digit_h/2+seg_t/2, x+digit_w, y+digit_h-seg_t),
                "d": (x+seg_t, y+digit_h-seg_t, x+digit_w-seg_t, y+digit_h),
                "e": (x, y+digit_h/2+seg_t/2, x+seg_t, y+digit_h-seg_t),
                "f": (x, y+seg_t, x+seg_t, y+digit_h/2-seg_t/2),
                "g": (x+seg_t, y+digit_h/2-seg_t/2, x+digit_w-seg_t, y+digit_h/2+seg_t/2),
            }
            for name, coords in segs.items():
                self.canvas.create_rectangle(*coords, fill=on if name in active else off, outline="", tags=(tag,))
            x += digit_w + gap

        if not c.use_24h and c.show_ampm:
            ampm_color = "" if c.accent_transparent else c.accent_color
            if not ampm_color:
                ampm_color = "" if c.text_transparent else c.text_color
            if ampm_color:
                af = tkfont.Font(family=c.font_family, size=max(8, int(diameter * 0.10)), weight="bold")
                self.canvas.create_text(cx, y + digit_h + diameter*0.12, text=now.strftime("%p"), font=af,
                                        fill=ampm_color, anchor="center", tags=(tag,))

        if selected:
            outline = "" if c.accent_transparent else c.accent_color
            if not outline:
                outline = "" if c.text_transparent else c.text_color
            if not outline:
                outline = "#FFFFFF"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=2, dash=(5,3), tags=(tag,))
            self._draw_resize_handle(x2, y2, outline, tag)
        if c.label:
            lf = tkfont.Font(family=c.font_family, size=max(7, int(diameter * 0.06)), weight=c.font_weight)
            label_color = "" if c.accent_transparent else c.accent_color
            if not label_color:
                label_color = "" if c.text_transparent else c.text_color
            if label_color:
                self.canvas.create_text(cx, y2-max(8, diameter*0.03), text=c.label, font=lf, fill=label_color,
                                        anchor="s", tags=(tag,))

    # -------------------------- photoreal Nixie ------------------------
    def _nixie_palette_key(self, palette):
        return tuple(palette.get(k, "") for k in ("digit", "glow", "tube", "glass", "grid", "metal", "off"))

    @staticmethod
    def _hex_rgb(value, fallback=(255, 255, 255)):
        try:
            value = str(value).strip().lstrip("#")
            if len(value) == 6:
                return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            pass
        return fallback

    @staticmethod
    def _blend_rgb(a, b, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))

    def _rounded_line(self, draw, points, fill, width):
        if len(points) < 2:
            return
        draw.line(points, fill=fill, width=max(1, int(width)), joint="curve")
        r = max(1, int(width / 2))
        for px, py in (points[0], points[-1]):
            draw.ellipse((px-r, py-r, px+r, py+r), fill=fill)

    def _nixie_digit_strokes(self, digit):
        # Curved, cathode-like vector glyphs. Coordinates are in a 0..1 box.
        glyphs = {
            "0": [[(0.20,0.15),(0.10,0.28),(0.10,0.72),(0.20,0.85),(0.50,0.90),(0.80,0.85),(0.90,0.72),(0.90,0.28),(0.80,0.15),(0.50,0.10),(0.20,0.15)]],
            "1": [[(0.28,0.28),(0.50,0.10),(0.50,0.90)],[(0.34,0.90),(0.66,0.90)]],
            "2": [[(0.18,0.25),(0.28,0.12),(0.68,0.12),(0.84,0.25),(0.82,0.40),(0.66,0.54),(0.28,0.84),(0.18,0.90),(0.84,0.90)]],
            "3": [[(0.18,0.18),(0.72,0.12),(0.84,0.25),(0.68,0.50),(0.82,0.52),(0.86,0.70),(0.72,0.88),(0.22,0.88)]],
            "4": [[(0.70,0.90),(0.70,0.10),(0.16,0.62),(0.84,0.62)]],
            "5": [[(0.82,0.12),(0.22,0.12),(0.16,0.50),(0.68,0.50),(0.82,0.62),(0.76,0.84),(0.60,0.90),(0.18,0.88)]],
            "6": [[(0.78,0.16),(0.60,0.10),(0.28,0.20),(0.16,0.44),(0.18,0.76),(0.34,0.90),(0.66,0.90),(0.82,0.74),(0.78,0.56),(0.62,0.48),(0.22,0.52)]],
            "7": [[(0.14,0.12),(0.84,0.12),(0.54,0.46),(0.54,0.90)]],
            "8": [[(0.28,0.10),(0.72,0.10),(0.84,0.24),(0.82,0.43),(0.66,0.50),(0.82,0.58),(0.84,0.76),(0.70,0.90),(0.30,0.90),(0.16,0.76),(0.18,0.58),(0.34,0.50),(0.18,0.43),(0.16,0.24),(0.28,0.10)]],
            "9": [[(0.78,0.48),(0.34,0.48),(0.18,0.34),(0.20,0.18),(0.36,0.10),(0.68,0.10),(0.82,0.24),(0.82,0.72),(0.68,0.88),(0.30,0.88)]],
        }
        return glyphs.get(str(digit), [])

    def _render_nixie_display(self, text, palette, pixel_w, pixel_h):
        """Render the Nixie display into a cached RGBA image using layered Pillow compositing."""
        pixel_w = max(220, min(2400, int(pixel_w)))
        pixel_h = max(120, min(1000, int(pixel_h)))
        cache_key = (text, pixel_w, pixel_h, self._nixie_palette_key(palette))
        cached = self.nixie_digit_cache.get(cache_key)
        if cached is not None:
            return cached

        img = Image.new("RGBA", (pixel_w, pixel_h), (0, 0, 0, 0))
        base_h = max(34, int(pixel_h * 0.20))
        tube_top = int(pixel_h * 0.05)
        tube_bottom = pixel_h - base_h - int(pixel_h * 0.035)
        tube_h = max(60, tube_bottom - tube_top)

        digit_rgb = self._hex_rgb(palette["digit"])
        glow_rgb = self._hex_rgb(palette["glow"], digit_rgb)
        tube_rgb = self._hex_rgb(palette["tube"], (18, 10, 6))
        glass_rgb = self._hex_rgb(palette["glass"], (110, 55, 25))
        grid_rgb = self._hex_rgb(palette["grid"], (90, 50, 25))
        metal_rgb = self._hex_rgb(palette["metal"], (160, 100, 40))

        # Continuous joined hardware base, built from metallic gradients.
        base = Image.new("RGBA", (pixel_w, pixel_h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(base)
        top_y = tube_bottom - int(pixel_h * 0.015)
        for yy in range(top_y, pixel_h):
            t = (yy - top_y) / max(1, pixel_h - top_y - 1)
            if t < 0.15:
                col = self._blend_rgb((245, 198, 110), metal_rgb, t / 0.15)
            elif t < 0.35:
                col = self._blend_rgb(metal_rgb, (48, 40, 32), (t - 0.15) / 0.20)
            elif t < 0.78:
                col = self._blend_rgb((48, 40, 32), (18, 18, 18), (t - 0.35) / 0.43)
            else:
                col = self._blend_rgb((18, 18, 18), metal_rgb, (t - 0.78) / 0.22)
            bd.line((0, yy, pixel_w, yy), fill=(*col, 255))
        radius = max(8, int(pixel_h * 0.025))
        bd.rounded_rectangle((2, top_y, pixel_w-3, pixel_h-3), radius=radius,
                             outline=(*self._blend_rgb(metal_rgb, (255,255,255), 0.35),255), width=max(2, int(pixel_h*0.012)))
        # Brass trim rails.
        trim = self._blend_rgb(metal_rgb, (255, 220, 150), 0.55)
        bd.rounded_rectangle((3, top_y, pixel_w-4, top_y + max(5, int(pixel_h*0.028))), radius=radius,
                             fill=(*trim,255))
        bd.rounded_rectangle((3, pixel_h-max(8,int(pixel_h*0.035)), pixel_w-4, pixel_h-3), radius=radius,
                             fill=(*self._blend_rgb(metal_rgb,(40,30,22),0.35),255))
        # Base studs/feet.
        stud_r = max(4, int(pixel_h*0.028))
        for sx in (int(pixel_w*0.07), int(pixel_w*0.93)):
            sy = pixel_h - int(pixel_h*0.045)
            bd.ellipse((sx-stud_r,sy-stud_r,sx+stud_r,sy+stud_r), fill=(*trim,255), outline=(20,14,10,255), width=2)
        img = Image.alpha_composite(img, base)

        # Work out tube slots from the display string.
        chars = list(text)
        units = []
        for ch in chars:
            units.append("digit" if ch.isdigit() else "colon")
        gap = max(5, int(pixel_w * 0.012))
        digit_w = int((pixel_w - gap * (len(chars)-1)) / max(1, sum(1 if u == "digit" else 0.43 for u in units)))
        digit_w = max(38, min(int(pixel_w*0.20), digit_w))
        colon_w = max(16, int(digit_w*0.43))
        total = sum(digit_w if u == "digit" else colon_w for u in units) + gap*(len(chars)-1)
        cursor_x = (pixel_w-total)/2
        tube_pad = max(2, int(digit_w*0.06))

        for ch, unit in zip(chars, units):
            if unit == "colon":
                cx = int(cursor_x + colon_w/2)
                for cy in (int(tube_top+tube_h*0.40), int(tube_top+tube_h*0.62)):
                    glow = Image.new("RGBA", img.size, (0,0,0,0))
                    gd = ImageDraw.Draw(glow)
                    rr = max(5, int(digit_w*0.055))
                    gd.ellipse((cx-rr,cy-rr,cx+rr,cy+rr), fill=(*glow_rgb,230))
                    glow = glow.filter(ImageFilter.GaussianBlur(max(3, rr*3)))
                    img = Image.alpha_composite(img, glow)
                    draw = ImageDraw.Draw(img)
                    draw.ellipse((cx-rr,cy-rr,cx+rr,cy+rr), fill=(*digit_rgb,255), outline=(255,240,190,170), width=1)
                cursor_x += colon_w + gap
                continue

            tx = int(cursor_x)
            tw = digit_w
            # Tube body: dark interior plus a translucent amber glass envelope.
            tube_layer = Image.new("RGBA", img.size, (0,0,0,0))
            td = ImageDraw.Draw(tube_layer)
            glass_outline = self._blend_rgb(glass_rgb,(255,190,100),0.28)
            td.rounded_rectangle((tx+tube_pad, tube_top, tx+tw-tube_pad, tube_bottom),
                                 radius=max(9,int(tw*0.13)), fill=(*tube_rgb,225), outline=(*glass_outline,235), width=max(2,int(tw*0.022)))
            # Glass vertical highlight.
            td.rounded_rectangle((tx+int(tw*0.12),tube_top+int(tube_h*0.04),tx+int(tw*0.23),tube_bottom-int(tube_h*0.05)),
                                 radius=max(4,int(tw*0.04)), fill=(255,200,150,48), outline=(255,245,230,100), width=max(1,int(tw*0.008)))
            td.arc((tx+int(tw*0.10),tube_top-int(tube_h*0.07),tx+int(tw*0.90),tube_top+int(tube_h*0.20)), 180, 165, fill=(255,255,255,105), width=max(1,int(tw*0.012)))
            img = Image.alpha_composite(img, tube_layer)

            # Internal grid.
            gd = ImageDraw.Draw(img)
            for frac in (0.20,0.30,0.40,0.50,0.60,0.70,0.80):
                yy=int(tube_top+tube_h*frac)
                gd.line((tx+tw*0.16,yy,tx+tw*0.84,yy), fill=(*grid_rgb,120), width=max(1,int(tw*0.006)))
            for frac in (0.22,0.78):
                gd.line((tx+tw*frac,tube_top+tube_h*0.10,tx+tw*frac,tube_bottom-tube_h*0.08), fill=(*grid_rgb,155), width=max(1,int(tw*0.009)))
            # Copper supports.
            for frac in (0.14,0.86):
                gd.line((tx+tw*frac,tube_top+tube_h*0.05,tx+tw*frac,tube_bottom-tube_h*0.05), fill=(*metal_rgb,210), width=max(1,int(tw*0.018)))

            # Cathode glow on separate blurred layers.
            strokes = self._nixie_digit_strokes(ch)
            if not strokes:
                strokes = [[(0.25,0.15),(0.75,0.85)]]
            glow_layer = Image.new("RGBA", img.size, (0,0,0,0))
            gdraw = ImageDraw.Draw(glow_layer)
            point_scale_x = tw * 0.72
            point_scale_y = tube_h * 0.70
            ox = tx + tw*0.14
            oy = tube_top + tube_h*0.14
            cathode_w = max(2, int(tw*0.055))
            for path in strokes:
                pts=[(int(ox+px*point_scale_x), int(oy+py*point_scale_y)) for px,py in path]
                self._rounded_line(gdraw, pts, (*glow_rgb,230), cathode_w*2)
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(4,int(tw*0.08))))
            img = Image.alpha_composite(img, glow_layer)
            bright = Image.new("RGBA", img.size, (0,0,0,0))
            bdraw = ImageDraw.Draw(bright)
            for path in strokes:
                pts=[(int(ox+px*point_scale_x), int(oy+py*point_scale_y)) for px,py in path]
                self._rounded_line(bdraw, pts, (*digit_rgb,255), cathode_w)
            img = Image.alpha_composite(img, bright)

            # Socket / collar.
            socket = ImageDraw.Draw(img)
            sy1 = tube_bottom-int(tube_h*0.015)
            sy2 = tube_bottom+int(pixel_h*0.065)
            socket.rounded_rectangle((tx+tube_pad, sy1, tx+tw-tube_pad, sy2), radius=max(3,int(tw*0.035)),
                                     fill=(*metal_rgb,255), outline=(*self._blend_rgb(metal_rgb,(255,230,170),0.45),255), width=max(2,int(tw*0.014)))
            socket.line((tx+tube_pad+3,sy1+int((sy2-sy1)*0.40),tx+tw-tube_pad-3,sy1+int((sy2-sy1)*0.40)),
                        fill=(255,220,150,180), width=max(1,int(tw*0.009)))
            cursor_x += digit_w + gap

        # Very subtle amber reflection under the tubes.
        refl = Image.new("RGBA", img.size, (0,0,0,0))
        rd = ImageDraw.Draw(refl)
        rd.rectangle((0, tube_bottom, pixel_w, tube_bottom+max(2,int(pixel_h*0.035))), fill=(*glow_rgb,40))
        refl = refl.filter(ImageFilter.GaussianBlur(max(2,int(pixel_h*0.012))))
        img = Image.alpha_composite(img, refl)

        # Trim transparent margins and keep a little breathing room.
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        if len(self.nixie_digit_cache) >= 64:
            self.nixie_digit_cache.pop(next(iter(self.nixie_digit_cache)))
        self.nixie_digit_cache[cache_key] = img
        return img

    def _draw_nixie(self, c, cx, cy, w, h, selected=False):
        text, now = self._digital_text(c)
        diameter = max(160.0, c.size * min(w, max(1, h - 34)))
        display_w = int(min(w * 0.96, diameter * 1.90))
        display_h = int(min(h * 0.92, diameter * 0.92))
        palette = self._nixie_palette(c)
        rendered = self._render_nixie_display(text, palette, display_w, display_h)
        # Pillow images are held by a Tk reference just like ordinary image widgets.
        ref = ImageTk.PhotoImage(rendered)
        tag = f"clock:{c.clock_id}"
        self.nixie_digit_refs[c.clock_id] = ref
        self.canvas.create_image(cx, cy, image=ref, anchor="center", tags=(tag,))

        x1, y1, x2, y2 = self._clock_bbox(c, cx, cy, w, h)
        outline = palette["digit"] if not c.accent_transparent else (c.text_color if not c.text_transparent else "#FFFFFF")
        if selected:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=2, dash=(5,3), tags=(tag,))
            self._draw_resize_handle(x2, y2, outline, tag)
        if c.label:
            label_color = palette["digit"] if not c.accent_transparent else (c.text_color if not c.text_transparent else "#FFFFFF")
            lf = tkfont.Font(family=c.font_family, size=max(7, int(diameter*0.055)), weight=c.font_weight)
            self.canvas.create_text(cx, y2-max(8,diameter*0.025), text=c.label, font=lf, fill=label_color,
                                    anchor="s", tags=(tag,))
    def _draw_custom_image_clock(self, c, cx, cy, w, h, selected=False):
        text, now = self._digital_text(c)
        if ImageTk is None:
            return self._draw_digital(c, cx, cy, w, h, selected)
        diameter = max(120.0, c.size * min(w, max(1, h - 34)))
        digit_h = max(40, int(diameter * 0.42))
        target_digit_w = max(24, int(digit_h * 0.58))
        gap = max(6, int(target_digit_w * 0.20))
        units = [(ch, ch.isdigit()) for ch in text]
        total_w = sum(target_digit_w if is_digit else int(target_digit_w * 0.42) for _, is_digit in units) + gap * max(0, len(units)-1)
        cursor = cx - total_w / 2
        fallback_color = "#FFFFFF" if c.text_transparent else c.text_color
        tag = f"clock:{c.clock_id}"
        for ch, is_digit in units:
            if not is_digit:
                separator_w = int(target_digit_w * 0.42)
                separator_source = self.custom_digit_sources.get((c.clock_id, "colon")) if ch == ":" else None
                if separator_source is not None:
                    scale = separator_w / max(1, separator_source.width)
                    separator_h = max(16, int(separator_source.height * scale))
                    key = ("colon", separator_w, separator_h)
                    cached = self.custom_digit_cache.get((c.clock_id, "colon"))
                    photo = cached[1] if cached and cached[0] == key else None
                    if photo is None:
                        resized = separator_source.resize((separator_w, separator_h), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(resized)
                        self.custom_digit_cache[(c.clock_id, "colon")] = (key, photo)
                    self.custom_digit_refs[(c.clock_id, "colon")] = photo
                    self.canvas.create_image(cursor + separator_w/2, cy, image=photo, anchor="center", tags=(tag,))
                else:
                    self.canvas.create_text(cursor + separator_w/2, cy, text=ch, font=tkfont.Font(family=c.font_family, size=max(20, int(digit_h*0.25)), weight=c.font_weight), fill=fallback_color, anchor="center", tags=(tag,))
                cursor += separator_w + gap
                continue
            source = self.custom_digit_sources.get((c.clock_id, ch))
            if source is None:
                self.canvas.create_text(cursor + target_digit_w/2, cy, text=ch, font=tkfont.Font(family=c.font_family, size=max(20, int(digit_h*0.48)), weight=c.font_weight), fill=fallback_color, anchor="center", tags=(tag,))
                cursor += target_digit_w + gap
                continue
            scale = target_digit_w / max(1, source.width)
            target_h = max(16, int(source.height * scale))
            key = (ch, target_digit_w, target_h)
            cached = self.custom_digit_cache.get((c.clock_id, ch))
            photo = cached[1] if cached and cached[0] == key else None
            if photo is None:
                resized = source.resize((target_digit_w, target_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
                self.custom_digit_cache[(c.clock_id, ch)] = (key, photo)
            self.custom_digit_refs[(c.clock_id, ch)] = photo
            self.canvas.create_image(cursor + target_digit_w/2, cy, image=photo, anchor="center", tags=(tag,))
            cursor += target_digit_w + gap

        x1, y1, x2, y2 = self._clock_bbox(c, cx, cy, w, h)
        outline = "#FFFFFF" if c.accent_transparent else c.accent_color
        if selected:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=2, dash=(5,3), tags=(tag,))
            self._draw_resize_handle(x2, y2, outline, tag)
        if c.label:
            lf = tkfont.Font(family=c.font_family, size=max(7, int(diameter * 0.06)), weight=c.font_weight)
            label_color = "" if c.accent_transparent else c.accent_color
            if label_color:
                self.canvas.create_text(cx, y2-max(8, diameter*0.03), text=c.label, font=lf, fill=label_color, anchor="s", tags=(tag,))

    def _draw_analogue(self, c, cx, cy, w, h, selected=False):
        now = self._get_now(c.timezone)
        radius = max(35, c.size * min(w, max(1, h - 34)) / 2)
        x1, y1, x2, y2 = cx - radius, cy - radius, cx + radius, cy + radius

        # Face and bezel.
        self.canvas.create_oval(x1, y1, x2, y2, fill="" if c.face_transparent else c.face_color, outline="" if c.accent_transparent else c.accent_color,
                                width=max(2, int(radius * 0.018)), tags=(f"clock:{c.clock_id}",))
        inner = radius * 0.94
        self.canvas.create_oval(cx - inner, cy - inner, cx + inner, cy + inner,
                                outline="" if c.accent_transparent else c.accent_color, width=1,
                                tags=(f"clock:{c.clock_id}",))

        # Tick marks and numbers.
        for i in range(60):
            angle = math.radians(i * 6 - 90)
            outer = radius * 0.88
            tick_len = radius * (0.085 if i % 5 == 0 else 0.035)
            x_outer = cx + math.cos(angle) * outer
            y_outer = cy + math.sin(angle) * outer
            x_inner = cx + math.cos(angle) * (outer - tick_len)
            y_inner = cy + math.sin(angle) * (outer - tick_len)
            self.canvas.create_line(x_inner, y_inner, x_outer, y_outer,
                                    fill="" if c.accent_transparent else c.accent_color,
                                    width=max(1, int(radius * (0.018 if i % 5 == 0 else 0.008))),
                                    tags=(f"clock:{c.clock_id}",))

        number_font = tkfont.Font(family=c.font_family, weight=c.font_weight,
                                  size=max(7, int(radius * 0.16)))
        for hour in range(1, 13):
            angle = math.radians(hour * 30 - 90)
            nr = radius * 0.70
            nx = cx + math.cos(angle) * nr
            ny = cy + math.sin(angle) * nr
            self.canvas.create_text(nx, ny, text=str(hour), font=number_font, fill="" if c.text_transparent else c.text_color,
                                    tags=(f"clock:{c.clock_id}",))

        sec = now.second + now.microsecond / 1_000_000
        minute = now.minute + sec / 60
        hour = (now.hour % 12) + minute / 60

        self._hand(c, cx, cy, radius * 0.47, hour * 30, max(3, int(radius * 0.035)), "" if c.text_transparent else c.text_color)
        self._hand(c, cx, cy, radius * 0.66, minute * 6, max(2, int(radius * 0.022)), "" if c.text_transparent else c.text_color)
        if c.show_seconds:
            self._hand(c, cx, cy, radius * 0.73, sec * 6, max(1, int(radius * 0.010)), "" if c.accent_transparent else c.accent_color)

        self.canvas.create_oval(cx - radius * 0.045, cy - radius * 0.045,
                                cx + radius * 0.045, cy + radius * 0.045,
                                fill="" if c.accent_transparent else c.accent_color, outline="", tags=(f"clock:{c.clock_id}",))

        if c.label:
            lf = tkfont.Font(family=c.font_family, size=max(7, int(radius * 0.09)), weight=c.font_weight)
            self.canvas.create_text(cx, cy + radius * 0.46, text=c.label, font=lf,
                                    fill="" if c.accent_transparent else c.accent_color, anchor="center", tags=(f"clock:{c.clock_id}",))

        if selected:
            tag = f"clock:{c.clock_id}"
            self.canvas.create_oval(x1 - 3, y1 - 3, x2 + 3, y2 + 3,
                                    outline=c.text_color, width=2, dash=(5, 3),
                                    tags=(tag,))
            self._draw_resize_handle(x2, y2, c.accent_color, tag)

    def _draw_resize_handle(self, x, y, color, tag):
        r = 7
        self.canvas.create_rectangle(x-r, y-r, x+r, y+r, fill=color, outline="#000000", width=1,
                                     tags=("resize-handle", tag))
        self.canvas.create_line(x-r+3, y, x+r-3, y, fill="#000000", width=1, tags=("resize-handle", tag))
        self.canvas.create_line(x, y-r+3, x, y+r-3, fill="#000000", width=1, tags=("resize-handle", tag))

    def _hand(self, c, cx, cy, length, degrees, width, color):
        angle = math.radians(degrees - 90)
        x2 = cx + math.cos(angle) * length
        y2 = cy + math.sin(angle) * length
        self.canvas.create_line(cx, cy, x2, y2, fill=color, width=width,
                                capstyle="round", tags=(f"clock:{c.clock_id}",))

    def _advance_quote_if_due(self, q):
        if not q.quotes:
            return
        now = time.time()
        if not q.last_changed:
            q.last_changed = now
            return
        if now - q.last_changed < max(1.0, q.interval):
            return
        interval = max(1.0, q.interval)
        elapsed = now - q.last_changed
        steps = max(1, int(elapsed // interval))
        if q.randomize and len(q.quotes) > 1:
            for _ in range(steps):
                choices = [i for i in range(len(q.quotes)) if i != q.current_index]
                q.current_index = random.choice(choices) if choices else 0
        else:
            q.current_index = (q.current_index + steps) % len(q.quotes)
        q.last_changed = q.last_changed + steps * interval
        if q.last_changed < now - interval:
            q.last_changed = now
        self._schedule_autosave()

    def _draw_quote(self, q, w, h, selected=False):
        if not q.quotes:
            return
        self._advance_quote_if_due(q)
        index = max(0, min(q.current_index, len(q.quotes) - 1))
        text = q.quotes[index]
        cx = q.x * w
        toolbar_h = 0 if self.fullscreen else 34
        cy = toolbar_h + q.y * max(1, h - toolbar_h)
        box_w = max(80, q.size * w)
        box_h = max(70, min(h * 0.45, box_w * 0.72))
        x1, y1 = cx - box_w / 2, cy - box_h / 2
        x2, y2 = cx + box_w / 2, cy + box_h / 2
        if q.face_color and not q.face_transparent:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=q.face_color, outline="", tags=(f"quote:{q.quote_id}",))
        if selected:
            tag = f"quote:{q.quote_id}"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=q.accent_color, width=2, dash=(5, 3), tags=(tag,))
            self._draw_resize_handle(x2, y2, q.accent_color, tag)
        font = self._fit_wrapped_font(text, q.font_family, q.font_weight, box_w * 0.88, box_h * 0.70, box_w * 0.09)
        self.canvas.create_text(cx, cy, text=text, width=box_w * 0.88, font=font, fill=q.text_color, justify="center", anchor="center", tags=(f"quote:{q.quote_id}",))
        if q.label:
            lf = tkfont.Font(family=q.font_family, size=max(7, int(font.cget("size") * 0.27)), weight=q.font_weight)
            self.canvas.create_text(cx, y2 - 8, text=q.label, font=lf, fill=q.accent_color, anchor="s", tags=(f"quote:{q.quote_id}",))

    def _fit_wrapped_font(self, text, family, weight, max_width, max_height, start_size):
        cache_key = (text, family, weight, int(max_width), int(max_height), int(start_size))
        cached = self.quote_font_cache.get(cache_key)
        if cached is not None:
            return cached
        size = max(6, int(start_size))
        while size > 6:
            f = tkfont.Font(family=family, size=size, weight=weight)
            words = text.split()
            lines = []
            current = ""
            for word in words:
                test = word if not current else current + " " + word
                if f.measure(test) <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            line_h = f.metrics("linespace")
            if lines and line_h * len(lines) <= max_height:
                if len(self.quote_font_cache) >= 512:
                    self.quote_font_cache.pop(next(iter(self.quote_font_cache)))
                self.quote_font_cache[cache_key] = f
                return f
            size -= 1
        f = tkfont.Font(family=family, size=6, weight=weight)
        if len(self.quote_font_cache) >= 512:
            self.quote_font_cache.pop(next(iter(self.quote_font_cache)))
        self.quote_font_cache[cache_key] = f
        return f

    def add_quotes_dialog(self):
        QuoteEditor(self, None, initial_position=(self.context_x, self.context_y))

    def add_quote_widget(self, quotes, x=None, y=None, size=0.45, quote_id=None, **kwargs):
        cleaned = [str(q).strip() for q in quotes if str(q).strip()]
        if not cleaned:
            return None
        if x is None or y is None:
            x, y = self.context_x, self.context_y
        q = QuoteData(
            quote_id=self.next_quote_id if quote_id is None else quote_id,
            quotes=cleaned, x=max(0.03, min(0.97, x)), y=max(0.08, min(0.96, y)),
            size=max(0.12, min(0.95, size)),
            font_family=kwargs.get("font_family", "DejaVu Sans"),
            font_weight=kwargs.get("font_weight", "normal"),
            text_color=kwargs.get("text_color", "#FFFFFF"),
            accent_color=kwargs.get("accent_color", "#FFFFFF"),
            face_color=kwargs.get("face_color", "#111111"),
            face_transparent=bool(kwargs.get("face_transparent", True)),
            interval=max(1.0, float(kwargs.get("interval", 20.0))),
            randomize=bool(kwargs.get("randomize", False)),
            current_index=max(0, int(kwargs.get("current_index", 0))),
            last_changed=float(kwargs.get("last_changed", 0.0)),
            label=kwargs.get("label", ""),
        )
        if quote_id is None:
            self.next_quote_id += 1
        if q.current_index >= len(q.quotes):
            q.current_index = 0
        if not q.last_changed:
            q.last_changed = time.time()
        self.quotes.append(q)
        self.selected_quote_id = q.quote_id
        self.selected_id = None
        self.selected_image_id = None
        self.draw()
        self._schedule_autosave()
        return q

    def add_image_dialog(self):
        path = filedialog.askopenfilename(
            title="Choose Image",
            filetypes=[("Images", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg *.webp"), ("All files", "*.*")],
        )
        if path:
            self.add_image(path)

    def add_image(self, path, x=None, y=None, size=0.25, image_id=None, label=""):
        if ImageTk is None:
            messagebox.showerror("Image Widget", "The image widget requires Pillow. Install it with: python -m pip install pillow")
            return
        try:
            pil_image = self._load_pil_image_safely(path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Image Widget", f"Could not open the image.\n\n{exc}")
            return
        if x is None or y is None:
            x = self.context_x
            y = self.context_y
        img = ImageData(
            image_id=self.next_image_id if image_id is None else image_id,
            path=os.path.abspath(os.path.expanduser(path)), x=max(0.02, min(0.98, x)), y=max(0.06, min(0.98, y)),
            size=max(0.04, min(0.95, size)), label=label
        )
        if image_id is None:
            self.next_image_id += 1
        self.images.append(img)
        self.image_sources[img.image_id] = pil_image
        self.image_source_signatures[img.image_id] = self._image_signature(path)
        self.image_cache.pop(img.image_id, None)
        self.selected_image_id = img.image_id
        self.selected_quote_id = None
        self.selected_id = None
        self.draw()

    def _draw_image(self, img, w, h, selected=False):
        source = self.image_sources.get(img.image_id)
        current_sig = self._image_signature(img.path)
        if source is not None and current_sig != self.image_source_signatures.get(img.image_id):
            source = None
            self.image_sources.pop(img.image_id, None)
            self.image_cache.pop(img.image_id, None)
        if source is None:
            try:
                source = self._load_pil_image_safely(img.path)
                self.image_sources[img.image_id] = source
                self.image_source_signatures[img.image_id] = current_sig
            except (OSError, ValueError, RuntimeError):
                return
        if source is None:
            return
        target_w = max(16, int(w * img.size))
        ratio = target_w / max(1, source.width)
        target_h = max(16, int(source.height * ratio))
        cache_key = (target_w, target_h)
        cached = self.image_cache.get(img.image_id)
        tk_image = cached[1] if cached and cached[0] == cache_key else None
        if tk_image is None:
            resized = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
            tk_image = ImageTk.PhotoImage(resized)
            self.image_cache[img.image_id] = (cache_key, tk_image)
        self.image_refs[img.image_id] = tk_image
        cx = img.x * w
        toolbar_h = 0 if self.fullscreen else 34
        cy = toolbar_h + img.y * max(1, h - toolbar_h)
        self.canvas.create_image(cx, cy, image=tk_image, anchor="center", tags=(f"image:{img.image_id}",))
        if selected:
            x1, y1 = cx - target_w / 2, cy - target_h / 2
            x2, y2 = cx + target_w / 2, cy + target_h / 2
            tag = f"image:{img.image_id}"
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#FFFFFF", width=2, dash=(5, 3), tags=(tag,))
            self._draw_resize_handle(x2, y2, img.accent_color if hasattr(img, "accent_color") else "#FFFFFF", tag)
        if img.label:
            self.canvas.create_text(cx, cy + target_h / 2 + 8, text=img.label, fill=getattr(self, "image_label_color", "#FFFFFF"), anchor="n", tags=(f"image:{img.image_id}",))

    def _linked_clock_now(self, clock_id):
        clock = self.get_clock(clock_id)
        if clock is None:
            return None
        return self._get_now(clock.timezone)

    def _aux_box(self, widget, w, h, default_height_ratio=0.45):
        toolbar_h = 0 if self.fullscreen else 34
        cx = widget.x * w
        cy = toolbar_h + widget.y * max(1, h - toolbar_h)
        box_w = max(70, widget.size * w)
        box_h = max(45, min(h * 0.30, box_w * default_height_ratio))
        return cx, cy, box_w, box_h

    def _draw_aux_base(self, widget, tag, w, h, selected=False, height_ratio=0.45):
        cx, cy, box_w, box_h = self._aux_box(widget, w, h, height_ratio)
        x1, y1, x2, y2 = cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2
        if widget.face_color and not widget.face_transparent:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=widget.face_color, outline="", tags=(tag,))
        if selected:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=widget.accent_color, width=2, dash=(5,3), tags=(tag,))
            self._draw_resize_handle(x2, y2, widget.accent_color, tag)
        return cx, cy, box_w, box_h, x1, y1, x2, y2

    def _draw_ampm(self, a, w, h, selected=False):
        now = self._linked_clock_now(a.linked_clock_id)
        text = now.strftime("%p") if now else "--"
        cx, cy, box_w, box_h, x1, y1, x2, y2 = self._draw_aux_base(a, f"ampm:{a.ampm_id}", w, h, selected, 0.55)
        font = self._fit_font(text, a.font_family, a.font_weight, box_w * 0.86, box_h * 0.72, box_h * 0.58)
        self.canvas.create_text(cx, cy, text=text, font=font, fill=a.text_color, anchor="center", tags=(f"ampm:{a.ampm_id}",))
        if a.label:
            lf = tkfont.Font(family=a.font_family, size=max(7, int(font.cget("size") * 0.28)), weight=a.font_weight)
            self.canvas.create_text(cx, y2 - 6, text=a.label, font=lf, fill=a.accent_color, anchor="s", tags=(f"ampm:{a.ampm_id}",))

    def _draw_day(self, d, w, h, selected=False):
        now = self._linked_clock_now(d.linked_clock_id)
        if now is None:
            text = "Unknown day"
        elif d.day_format == "short":
            text = now.strftime("%a")
        elif d.day_format == "upper":
            text = now.strftime("%A").upper()
        else:
            text = now.strftime("%A")
        cx, cy, box_w, box_h, x1, y1, x2, y2 = self._draw_aux_base(d, f"day:{d.day_id}", w, h, selected, 0.55)
        font = self._fit_font(text, d.font_family, d.font_weight, box_w * 0.90, box_h * 0.70, box_h * 0.32)
        self.canvas.create_text(cx, cy, text=text, font=font, fill=d.text_color, anchor="center", tags=(f"day:{d.day_id}",))
        if d.label:
            lf = tkfont.Font(family=d.font_family, size=max(7, int(font.cget("size") * 0.27)), weight=d.font_weight)
            self.canvas.create_text(cx, y2 - 6, text=d.label, font=lf, fill=d.accent_color, anchor="s", tags=(f"day:{d.day_id}",))

    def _draw_date(self, d, w, h, selected=False):
        now = self._linked_clock_now(d.linked_clock_id)
        if now is None:
            text = "Unknown date"
        elif d.date_format == "short":
            text = now.strftime("%d %b %Y")
        elif d.date_format == "numeric_eu":
            text = now.strftime("%d/%m/%Y")
        elif d.date_format == "numeric_us":
            text = now.strftime("%m/%d/%Y")
        elif d.date_format == "iso":
            text = now.strftime("%Y-%m-%d")
        elif d.date_format == "weekday_long":
            text = now.strftime("%A, %d %B %Y")
        else:
            text = now.strftime("%d %B %Y")
        cx, cy, box_w, box_h, x1, y1, x2, y2 = self._draw_aux_base(d, f"date:{d.date_id}", w, h, selected, 0.55)
        font = self._fit_font(text, d.font_family, d.font_weight, box_w * 0.92, box_h * 0.70, box_h * 0.30)
        self.canvas.create_text(cx, cy, text=text, font=font, fill=d.text_color, anchor="center", tags=(f"date:{d.date_id}",))
        if d.label:
            lf = tkfont.Font(family=d.font_family, size=max(7, int(font.cget("size") * 0.27)), weight=d.font_weight)
            self.canvas.create_text(cx, y2 - 6, text=d.label, font=lf, fill=d.accent_color, anchor="s", tags=(f"date:{d.date_id}",))

    # ------------------------- interaction ----------------------------
    def _ampm_at(self, x, y):
        w = max(1, self.canvas.winfo_width()); h = max(1, self.canvas.winfo_height())
        for a in reversed(self.ampm_widgets):
            cx, cy, box_w, box_h = self._aux_box(a, w, h, 0.55)
            if abs(x-cx) <= box_w/2 and abs(y-cy) <= box_h/2:
                return a
        return None

    def _day_at(self, x, y):
        w = max(1, self.canvas.winfo_width()); h = max(1, self.canvas.winfo_height())
        for d in reversed(self.day_widgets):
            cx, cy, box_w, box_h = self._aux_box(d, w, h, 0.55)
            if abs(x-cx) <= box_w/2 and abs(y-cy) <= box_h/2:
                return d
        return None

    def _date_at(self, x, y):
        w = max(1, self.canvas.winfo_width()); h = max(1, self.canvas.winfo_height())
        for d in reversed(self.date_widgets):
            cx, cy, box_w, box_h = self._aux_box(d, w, h, 0.55)
            if abs(x-cx) <= box_w/2 and abs(y-cy) <= box_h/2:
                return d
        return None

    def _clock_at(self, x, y):
        # Tags are not directly queryable by coordinate in a useful way after redraw;
        # approximate hit testing from each clock's centre/radius.
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        candidates = list(reversed(self.clocks))
        for c in candidates:
            cx = c.x * w
            cy = toolbar_h + c.y * max(1, h - toolbar_h)
            radius = max(30, c.size * min(w, max(1, h - toolbar_h)) / 2)
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                return c
        return None

    def _quote_at(self, x, y):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        for q in reversed(self.quotes):
            cx = q.x * w
            cy = toolbar_h + q.y * max(1, h - toolbar_h)
            box_w = max(80, q.size * w)
            box_h = max(70, min(h * 0.45, box_w * 0.72))
            if abs(x-cx) <= box_w/2 and abs(y-cy) <= box_h/2:
                return q
        return None

    def _image_at(self, x, y):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        for img in reversed(self.images):
            source = self.image_sources.get(img.image_id)
            if source is None or ImageTk is None:
                continue
            iw = max(16, int(w * img.size))
            ih = max(16, int(source.height * (iw / max(1, source.width))))
            cx = img.x * w
            cy = toolbar_h + img.y * max(1, h - toolbar_h)
            if abs(x-cx) <= iw/2 and abs(y-cy) <= ih/2:
                return img
        return None

    def _on_window_configure(self, event):
        self.after_idle(self.draw)
        if not self._restoring_settings:
            self._schedule_autosave()

    def _resize_target_at(self, x, y):
        """Return (kind, object) when the pointer is over a selected widget resize handle."""
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        usable_h = max(1, h - toolbar_h)
        handle_r = 11

        # Only the selected widget exposes its resize handle. Check in the
        # same order as the selection priority so the handle is unambiguous.
        c = self.selected_clock()
        if c is not None:
            cx = c.x * w
            cy = toolbar_h + c.y * usable_h
            radius = max(30, c.size * min(w, usable_h) / 2)
            hx, hy = cx + radius, cy + radius
            if abs(x - hx) <= handle_r and abs(y - hy) <= handle_r:
                return ("clock", c)

        img = self.get_image(self.selected_image_id)
        if img is not None:
            source = self.image_sources.get(img.image_id)
            if source is not None:
                target_w = max(16, int(w * img.size))
                ratio = target_w / max(1, source.width)
                target_h = max(16, int(source.height * ratio))
                cx = img.x * w
                cy = toolbar_h + img.y * usable_h
                hx, hy = cx + target_w / 2, cy + target_h / 2
                if abs(x - hx) <= handle_r and abs(y - hy) <= handle_r:
                    return ("image", img)

        q = self.get_quote(self.selected_quote_id)
        if q is not None:
            cx = q.x * w
            cy = toolbar_h + q.y * usable_h
            box_w = max(80, q.size * w)
            box_h = max(70, min(h * 0.45, box_w * 0.72))
            hx, hy = cx + box_w / 2, cy + box_h / 2
            if abs(x - hx) <= handle_r and abs(y - hy) <= handle_r:
                return ("quote", q)
        a = self.selected_ampm()
        if a is not None:
            cx, cy, box_w, box_h = self._aux_box(a, w, h, 0.55)
            if abs(x-(cx+box_w/2)) <= handle_r and abs(y-(cy+box_h/2)) <= handle_r:
                return ("ampm", a)
        d = self.selected_day()
        if d is not None:
            cx, cy, box_w, box_h = self._aux_box(d, w, h, 0.55)
            if abs(x-(cx+box_w/2)) <= handle_r and abs(y-(cy+box_h/2)) <= handle_r:
                return ("day", d)
        dt = self.selected_date()
        if dt is not None:
            cx, cy, box_w, box_h = self._aux_box(dt, w, h, 0.55)
            if abs(x-(cx+box_w/2)) <= handle_r and abs(y-(cy+box_h/2)) <= handle_r:
                return ("date", dt)
        return None

    def on_left_press(self, event):
        self.dragging_id = None
        self.dragging_image_id = None
        self.dragging_quote_id = None
        self.dragging_ampm_id = None
        self.dragging_day_id = None
        self.dragging_date_id = None
        self.resize_mode = None
        self.resize_start = None

        resize_target = self._resize_target_at(event.x, event.y)
        if resize_target:
            kind, obj = resize_target
            self.resize_mode = kind
            self.selected_id = None
            self.selected_image_id = None
            self.selected_quote_id = None
            self.selected_ampm_id = None
            self.selected_day_id = None
            self.selected_date_id = None
            if kind == "clock":
                self.selected_id = obj.clock_id
            elif kind == "image":
                self.selected_image_id = obj.image_id
            elif kind == "quote":
                self.selected_quote_id = obj.quote_id
            elif kind == "ampm":
                self.selected_ampm_id = obj.ampm_id
            elif kind == "day":
                self.selected_day_id = obj.day_id
            elif kind == "date":
                self.selected_date_id = obj.date_id
            self.resize_start = (event.x, event.y, obj.size)
            self.draw()
            return

        # Hit-test from front to back so the last-drawn widget wins.
        q = self._quote_at(event.x, event.y)
        if q:
            self.selected_quote_id = q.quote_id
            self.selected_id = self.selected_image_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.dragging_quote_id = q.quote_id
            self.drag_start = (event.x, event.y, q.x, q.y)
            self.draw(); return
        a = self._ampm_at(event.x, event.y)
        if a:
            self.selected_ampm_id = a.ampm_id
            self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_day_id = self.selected_date_id = None
            self.dragging_ampm_id = a.ampm_id
            self.drag_start = (event.x, event.y, a.x, a.y)
            self.draw(); return
        d = self._day_at(event.x, event.y)
        if d:
            self.selected_day_id = d.day_id
            self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_date_id = None
            self.dragging_day_id = d.day_id
            self.drag_start = (event.x, event.y, d.x, d.y)
            self.draw(); return
        dt = self._date_at(event.x, event.y)
        if dt:
            self.selected_date_id = dt.date_id
            self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = None
            self.dragging_date_id = dt.date_id
            self.drag_start = (event.x, event.y, dt.x, dt.y)
            self.draw(); return
        img = self._image_at(event.x, event.y)
        if img:
            self.selected_image_id = img.image_id
            self.selected_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.dragging_image_id = img.image_id
            self.drag_start = (event.x, event.y, img.x, img.y)
            self.draw(); return
        c = self._clock_at(event.x, event.y)
        if c:
            self.selected_id = c.clock_id
            self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.dragging_id = c.clock_id
            self.drag_start = (event.x, event.y, c.x, c.y)
        else:
            self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
        self.draw()

    def on_drag(self, event):
        if self.resize_mode is not None and self.resize_start is not None:
            sx, sy, original_size = self.resize_start
            w = max(1, self.canvas.winfo_width())
            dx = event.x - sx
            dy = event.y - sy
            # Diagonal drag from the lower-right handle changes width/diameter.
            delta = (dx + dy) / 2.0
            if self.resize_mode == "clock":
                c = self.selected_clock()
                if not c:
                    return
                scale = 1.0 + (delta / max(80.0, c.size * min(w, max(1, self.canvas.winfo_height())) * 0.5))
                c.size = max(0.08, min(0.75, original_size * scale))
            elif self.resize_mode == "image":
                img = self.get_image(self.selected_image_id)
                if not img:
                    return
                new_size = original_size + dx / w
                img.size = max(0.04, min(0.95, new_size))
            elif self.resize_mode == "quote":
                q = self.get_quote(self.selected_quote_id)
                if not q:
                    return
                q.size = max(0.12, min(0.95, original_size + dx / w))
            elif self.resize_mode == "ampm":
                a = self.selected_ampm()
                if not a: return
                a.size = max(0.08, min(0.80, original_size + dx / w))
            elif self.resize_mode == "day":
                d = self.selected_day()
                if not d: return
                d.size = max(0.08, min(0.95, original_size + dx / w))
            elif self.resize_mode == "date":
                dt = self.selected_date()
                if not dt: return
                dt.size = max(0.08, min(0.95, original_size + dx / w))
            self.draw()
            self._schedule_autosave()
            return

        if self.dragging_quote_id is not None and self.drag_start is not None:
            q = self.get_quote(self.dragging_quote_id)
            if not q:
                return
            sx, sy, orig_x, orig_y = self.drag_start
            w = max(1, self.canvas.winfo_width())
            h = max(1, self.canvas.winfo_height())
            toolbar_h = 0 if self.fullscreen else 34
            usable_h = max(1, h - toolbar_h)
            q.x = max(0.01, min(0.99, orig_x + (event.x - sx) / w))
            q.y = max(0.01, min(0.99, orig_y + (event.y - sy) / usable_h))
            self.draw()
            self._schedule_autosave()
            return
        if self.dragging_ampm_id is not None and self.drag_start is not None:
            a = self.get_ampm(self.dragging_ampm_id)
            if not a: return
            sx, sy, ox, oy = self.drag_start; w=max(1,self.canvas.winfo_width()); h=max(1,self.canvas.winfo_height()); th=0 if self.fullscreen else 34; uh=max(1,h-th)
            a.x=max(0.01,min(0.99,ox+(event.x-sx)/w)); a.y=max(0.01,min(0.99,oy+(event.y-sy)/uh))
            self.draw(); self._schedule_autosave(); return
        if self.dragging_day_id is not None and self.drag_start is not None:
            d = self.get_day(self.dragging_day_id)
            if not d: return
            sx, sy, ox, oy = self.drag_start; w=max(1,self.canvas.winfo_width()); h=max(1,self.canvas.winfo_height()); th=0 if self.fullscreen else 34; uh=max(1,h-th)
            d.x=max(0.01,min(0.99,ox+(event.x-sx)/w)); d.y=max(0.01,min(0.99,oy+(event.y-sy)/uh))
            self.draw(); self._schedule_autosave(); return
        if self.dragging_date_id is not None and self.drag_start is not None:
            dt = self.get_date(self.dragging_date_id)
            if not dt: return
            sx, sy, ox, oy = self.drag_start; w=max(1,self.canvas.winfo_width()); h=max(1,self.canvas.winfo_height()); th=0 if self.fullscreen else 34; uh=max(1,h-th)
            dt.x=max(0.01,min(0.99,ox+(event.x-sx)/w)); dt.y=max(0.01,min(0.99,oy+(event.y-sy)/uh))
            self.draw(); self._schedule_autosave(); return
        if self.dragging_image_id is not None and self.drag_start is not None:
            img = self.get_image(self.dragging_image_id)
            if not img:
                return
            sx, sy, orig_x, orig_y = self.drag_start
            w = max(1, self.canvas.winfo_width())
            h = max(1, self.canvas.winfo_height())
            toolbar_h = 0 if self.fullscreen else 34
            usable_h = max(1, h - toolbar_h)
            img.x = max(0.01, min(0.99, orig_x + (event.x - sx) / w))
            img.y = max(0.01, min(0.99, orig_y + (event.y - sy) / usable_h))
            self.draw()
            self._schedule_autosave()
            return
        if self.dragging_id is None or self.drag_start is None:
            return
        c = self.get_clock(self.dragging_id)
        if not c:
            return
        sx, sy, orig_x, orig_y = self.drag_start
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        usable_h = max(1, h - toolbar_h)
        c.x = max(0.01, min(0.99, orig_x + (event.x - sx) / w))
        c.y = max(0.01, min(0.99, orig_y + (event.y - sy) / usable_h))
        self.draw()
        self._schedule_autosave()

    def on_left_release(self, event):
        self.dragging_id = None
        self.dragging_image_id = None
        self.dragging_quote_id = None
        self.dragging_ampm_id = None
        self.dragging_day_id = None
        self.dragging_date_id = None
        self.drag_start = None
        self.resize_mode = None
        self.resize_start = None

    def _double_click(self, event):
        q = self._quote_at(event.x, event.y)
        if q:
            self.selected_quote_id = q.quote_id; self.selected_id = self.selected_image_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.edit_selected_quote(); return
        a = self._ampm_at(event.x, event.y)
        if a:
            self.selected_ampm_id = a.ampm_id; self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_day_id = self.selected_date_id = None
            self.edit_selected_ampm(); return
        d = self._day_at(event.x, event.y)
        if d:
            self.selected_day_id = d.day_id; self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_date_id = None
            self.edit_selected_day(); return
        dt = self._date_at(event.x, event.y)
        if dt:
            self.selected_date_id = dt.date_id; self.selected_id = self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = None
            self.edit_selected_date(); return
        img = self._image_at(event.x, event.y)
        if img:
            self.selected_image_id = img.image_id; self.selected_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.edit_selected_image(); return
        c = self._clock_at(event.x, event.y)
        if c:
            self.selected_id = c.clock_id; self.selected_image_id = self.selected_quote_id = self.selected_ampm_id = self.selected_day_id = self.selected_date_id = None
            self.edit_selected_clock()

    def on_right_click(self, event):
        self.context_x, self.context_y = self._canvas_relative_position(event.x, event.y)
        q = self._quote_at(event.x, event.y)
        a = self._ampm_at(event.x, event.y) if q is None else None
        d = self._day_at(event.x, event.y) if q is None and a is None else None
        dt = self._date_at(event.x, event.y) if q is None and a is None and d is None else None
        img = self._image_at(event.x, event.y) if q is None and a is None and d is None and dt is None else None
        c = self._clock_at(event.x, event.y) if (img is None and q is None and a is None and d is None and dt is None) else None
        self.selected_quote_id = q.quote_id if q else None
        self.selected_ampm_id = a.ampm_id if a else None
        self.selected_day_id = d.day_id if d else None
        self.selected_date_id = dt.date_id if dt else None
        self.selected_image_id = img.image_id if img else None
        self.selected_id = c.clock_id if c else None
        for label in ("Edit Clock", "Delete Clock", "Increase Size", "Decrease Size"):
            self.context_menu.entryconfigure(label, state="normal" if c else "disabled")
        for label in ("Edit Image", "Delete Image"):
            self.context_menu.entryconfigure(label, state="normal" if img else "disabled")
        for label in ("Edit Quotes", "Delete Quotes"):
            self.context_menu.entryconfigure(label, state="normal" if q else "disabled")
        for label in ("Edit AM/PM", "Delete AM/PM"):
            self.context_menu.entryconfigure(label, state="normal" if a else "disabled")
        for label in ("Edit Day", "Delete Day"):
            self.context_menu.entryconfigure(label, state="normal" if d else "disabled")
        for label in ("Edit Date", "Delete Date"):
            self.context_menu.entryconfigure(label, state="normal" if dt else "disabled")
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _canvas_relative_position(self, x, y):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        return max(0.02, min(0.98, x / w)), max(0.05, min(0.98, (y - toolbar_h) / max(1, h - toolbar_h)))

    def on_ctrl_wheel(self, event, direction=None):
        if direction is None:
            direction = 1 if event.delta > 0 else -1
        factor = 1.08 if direction > 0 else 1 / 1.08
        self.change_selected_size(factor)

    def _context_add_digital(self):
        x, y = self._context_last_pos()
        self.add_clock("digital", x=x, y=y)

    def _context_add_segment(self):
        x, y = self._context_last_pos()
        self.add_clock("segment", x=x, y=y, size=0.30)

    def _context_add_nixie(self):
        x, y = self._context_last_pos()
        self.add_clock("nixie", x=x, y=y, size=0.30)

    def _context_add_analogue(self):
        x, y = self._context_last_pos()
        self.add_clock("analogue", x=x, y=y, size=0.32)

    def _context_add_image(self):
        self.add_image_dialog()

    def _context_add_quotes(self):
        self.add_quotes_dialog()

    def _context_add_ampm(self):
        self.add_ampm_dialog()

    def _context_add_day(self):
        self.add_day_dialog()

    def _context_add_date(self):
        self.add_date_dialog()

    def _context_last_pos(self):
        # Popup selection occurs after Button-3; Tk's pointer position is available globally.
        px = self.winfo_pointerx() - self.winfo_rootx()
        py = self.winfo_pointery() - self.winfo_rooty()
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        toolbar_h = 0 if self.fullscreen else 34
        self.context_x = max(0.02, min(0.98, px / w))
        self.context_y = max(0.05, min(0.98, (py - toolbar_h) / max(1, h - toolbar_h)))
        return self.context_x, self.context_y

    # ------------------------- clock editor ----------------------------

    # ------------------------- appearance ------------------------------
    def choose_background_color(self):
        colour = colorchooser.askcolor(color=self.background_color, title="Background Colour")
        if colour and colour[1]:
            self.background_color = colour[1]
            self.clear_background_image()
            self.canvas.configure(bg=self.background_color)
            self.draw()
            self._schedule_autosave()

    def choose_background_image(self):
        path = filedialog.askopenfilename(
            title="Choose Background Image",
            filetypes=[
                ("Tk images", "*.png *.gif *.ppm *.pgm"),
                ("PNG", "*.png"),
                ("GIF", "*.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            image = self._load_background_safely(path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Background Image", f"Could not open the image.\n\n{exc}")
            return
        try:
            package = self._package_dir_from_theme_path(self.current_theme_path or CURRENT_THEME_FILE)
            target = self._copy_asset_into_package(path, package, "background")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Background Image", f"Could not copy the image into the theme.\n\n{exc}")
            return
        self.background_image_path = target
        self.background_image_source = image
        self.background_image_signature = self._image_signature(self.background_image_path)
        self.background_image_cache.clear()
        self.background_image = None
        self.draw()
        self._schedule_autosave()

    def clear_background_image(self):
        self.background_image_path = ""
        self.background_image = None
        self.background_image_source = None
        self.background_image_signature = None
        self.background_image_cache = {}
        self.draw()
        self._schedule_autosave()

    def reset_background(self):
        self.background_color = "#101010"
        self.clear_background_image()
        self.canvas.configure(bg=self.background_color)
        self.draw()
        self._schedule_autosave()

    # ---------------------------- layout -------------------------------
    def _settings_data(self):
        # Kept as an alias for compatibility with manual layout methods; themes now hold everything.
        return self._theme_data_from_current(self.current_theme_name or "Current")

    def _schedule_autosave(self):
        if self._restoring_settings:
            return
        if self._autosave_after_id is not None:
            try:
                self.after_cancel(self._autosave_after_id)
            except tk.TclError:
                pass
        self._autosave_after_id = self.after(500, self._autosave_theme_now)

    def load_settings(self, silent=False):
        # Legacy compatibility: settings are now loaded from the current theme only.
        if os.path.exists(CURRENT_THEME_FILE):
            return self.load_theme(CURRENT_THEME_FILE, silent=silent)
        return False

    def _on_close(self):
        if self._autosave_after_id is not None:
            try:
                self.after_cancel(self._autosave_after_id)
            except tk.TclError:
                pass
            self._autosave_after_id = None
        self._autosave_theme_now()
        self.destroy()

    def save_layout(self):
        name = simpledialog.askstring("Save Theme", "Theme name:", initialvalue=self.current_theme_name or "My Theme", parent=self)
        if not name or not name.strip():
            return
        package = self._theme_path_for_name(name)
        if os.path.exists(package) and not messagebox.askyesno("Theme Exists", "That theme already exists. Replace it?", parent=self):
            return
        try:
            data = self._prepare_data_for_package(name.strip(), package)
            if self._write_theme(self._theme_json_path(package), data):
                self.current_theme_name = name.strip()
                self.current_theme_path = self._theme_json_path(package)
                self._refresh_theme_menu()
            else:
                messagebox.showerror("Theme", self._last_autosave_error or "Could not save the theme.", parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Theme", str(exc), parent=self)

    def load_layout(self):
        path = filedialog.askopenfilename(
            title="Load Full Theme State",
            filetypes=[("Theme files", "*.theme.json"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.load_theme(path, silent=False)

    def reset_layout(self):
        self.clocks.clear()
        self.images.clear()
        self.image_sources.clear()
        self.image_refs.clear()
        self.image_cache.clear()
        self.nixie_digit_sources.clear()
        self.nixie_digit_refs.clear()
        self.nixie_digit_cache.clear()
        self.custom_digit_sources.clear()
        self.custom_digit_refs.clear()
        self.custom_digit_cache.clear()
        self.image_source_signatures.clear()
        self.quote_font_cache.clear()
        self.quotes.clear()
        self.ampm_widgets.clear()
        self.day_widgets.clear()
        self.date_widgets.clear()
        self.selected_id = None
        self.selected_image_id = None
        self.next_id = 1
        self.next_image_id = 1
        self.next_quote_id = 1
        self.next_ampm_id = 1
        self.next_day_id = 1
        self.next_date_id = 1
        self.selected_quote_id = None
        self.selected_ampm_id = None
        self.selected_day_id = None
        self.selected_date_id = None
        self.add_clock("digital")
        self.add_clock("analogue", x=0.75, y=0.5, size=0.34)
        self._schedule_autosave()

    # --------------------------- fullscreen ----------------------------
    def toggle_fullscreen(self):
        self.set_fullscreen(not self.fullscreen)

    def set_fullscreen(self, value):
        self.fullscreen = bool(value)
        self.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            self.toolbar.place_forget()
        else:
            self.toolbar.place(relx=0, rely=0, relwidth=1, height=34)
        self.draw()
        self._schedule_autosave()

    # ----------------------------- help -------------------------------
    def show_help(self):
        messagebox.showinfo(
            "Multi Clock Help",
            "Left-click and drag a widget to move it.\n\n"
            "Use the lower-right handle to resize the selected widget.\n"
            "Right-click a widget for editing and actions.\n"
            "Ctrl + mouse wheel changes the selected widget's size.\n"
            "Quotes rotate automatically; random mode avoids predictable order.\n"
            "AM/PM widgets link to a clock and update with its time zone.\n"
            "Day widgets show the weekday; Date widgets show the calendar date, both linked to a clock.\n"
            "F11 toggles fullscreen; Escape exits fullscreen."
        )

    def show_about(self):
        messagebox.showinfo(
            "About Multi Clock",
            "Multi Clock\n\nA configurable multi-clock desktop display built with Python and Tkinter.",
        )


class ClockEditor(tk.Toplevel):
    def __init__(self, app, clock):
        super().__init__(app)
        self.app = app
        self.clock = clock
        self.title(f"Edit Clock {clock.clock_id}")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.kind_var = tk.StringVar(value=clock.kind)
        self.tz_var = tk.StringVar(value=clock.timezone)
        self.label_var = tk.StringVar(value=clock.label)
        self.font_var = tk.StringVar(value=clock.font_family)
        self.weight_var = tk.StringVar(value=clock.font_weight)
        self.text_var = tk.StringVar(value=clock.text_color)
        self.accent_var = tk.StringVar(value=clock.accent_color)
        self.face_var = tk.StringVar(value=clock.face_color)
        self.text_transparent_var = tk.BooleanVar(value=clock.text_transparent)
        self.accent_transparent_var = tk.BooleanVar(value=clock.accent_transparent)
        self.face_transparent_var = tk.BooleanVar(value=clock.face_transparent)
        self.seconds_var = tk.BooleanVar(value=clock.show_seconds)
        self.h24_var = tk.BooleanVar(value=clock.use_24h)
        self.ampm_var = tk.BooleanVar(value=clock.show_ampm)
        self.segment_off_transparent_var = tk.BooleanVar(value=clock.segment_off_transparent)
        self.nixie_skin_var = tk.StringVar(value=clock.nixie_skin if clock.nixie_skin in NIXIE_SKINS else "classic_orange")
        self.nixie_custom_vars = {
            key: tk.StringVar(value=clock.nixie_custom.get(key, NIXIE_SKINS["custom"][key]))
            for key in ("digit", "glow", "tube", "glass", "grid", "metal", "off")
        }
        self.size_var = tk.DoubleVar(value=round(clock.size * 100, 1))
        self.custom_digit_vars = {}

        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Type").grid(row=0, column=0, sticky="w", **pad)
        self.kind_combo = ttk.Combobox(frame, textvariable=self.kind_var, values=("digital", "segment", "nixie", "custom_image", "analogue"), state="readonly", width=18)
        self.kind_combo.grid(row=0, column=1, **pad)

        ttk.Label(frame, text="Time zone").grid(row=1, column=0, sticky="w", **pad)
        timezone_values = self.app.timezone_choices
        if self.tz_var.get() not in timezone_values:
            self.tz_var.set("local")
        ttk.Combobox(
            frame,
            textvariable=self.tz_var,
            values=timezone_values,
            state="readonly",
            width=36,
        ).grid(row=1, column=1, **pad)
        ttk.Label(frame, text="Choose an IANA time zone").grid(row=2, column=1, sticky="w", padx=8)

        ttk.Label(frame, text="Label").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.label_var, width=22).grid(row=3, column=1, **pad)

        ttk.Label(frame, text="Font family").grid(row=4, column=0, sticky="w", **pad)
        ttk.Combobox(frame, textvariable=self.font_var, values=self.app.font_families, width=30).grid(row=4, column=1, **pad)

        ttk.Label(frame, text="Weight").grid(row=5, column=0, sticky="w", **pad)
        ttk.Combobox(frame, textvariable=self.weight_var, values=("normal", "bold"), state="readonly", width=18).grid(row=5, column=1, **pad)

        ttk.Label(frame, text="Clock size (%)").grid(row=6, column=0, sticky="w", **pad)
        tk.Scale(frame, from_=8, to=75, resolution=1, orient="horizontal", variable=self.size_var, length=220).grid(row=6, column=1, **pad)

        ttk.Checkbutton(frame, text="Show seconds", variable=self.seconds_var).grid(row=7, column=1, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(frame, text="24-hour digital time", variable=self.h24_var).grid(row=8, column=1, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(frame, text="Show AM/PM on digital clock", variable=self.ampm_var).grid(row=9, column=1, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(frame, text="Transparent unlit segments (Segment)", variable=self.segment_off_transparent_var).grid(row=10, column=1, sticky="w", padx=8, pady=4)

        self.nixie_frame = ttk.LabelFrame(frame, text="Nixie Skin", padding=6)
        self.nixie_frame.grid(row=11, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        ttk.Label(self.nixie_frame, text="Built-in vector skins; no digit image files required.").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(self.nixie_frame, text="Skin").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        skin_values = list(NIXIE_SKINS.keys())
        skin_display = [NIXIE_SKINS[k]["label"] for k in skin_values]
        self.nixie_skin_map = dict(zip(skin_display, skin_values))
        current_label = NIXIE_SKINS[self.nixie_skin_var.get()]["label"]
        self.nixie_skin_display = tk.StringVar(value=current_label)
        ttk.Combobox(self.nixie_frame, textvariable=self.nixie_skin_display, values=skin_display, state="readonly", width=22).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(self.nixie_frame, text="Custom colours are used when Skin = Custom").grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=(6, 4))
        for idx, key in enumerate(("digit", "glow", "tube", "glass", "grid", "metal", "off"), start=3):
            self._color_row(self.nixie_frame, idx, key.replace("_", " ").title(), self.nixie_custom_vars[key], lambda v=self.nixie_custom_vars[key]: self.pick_color(v))

        self.custom_image_frame = ttk.LabelFrame(frame, text="Custom Image Digits", padding=6)
        self.custom_image_frame.grid(row=11, column=0, columnspan=3, sticky="ew", padx=8, pady=6)
        ttk.Label(self.custom_image_frame, text="Choose images for digits 0-9 and an optional colon separator. Images are copied into the theme.").grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 4))
        existing_custom = getattr(clock, "custom_digit_paths", {}) or {}
        # Use a compact 2-column grid so the separator control remains visible without scrolling.
        for pos, digit in enumerate("0123456789"):
            grid_row = 1 + pos // 2
            col = (pos % 2) * 4
            var = tk.StringVar(value=existing_custom.get(digit, ""))
            self.custom_digit_vars[digit] = var
            ttk.Label(self.custom_image_frame, text=f"Digit {digit}").grid(row=grid_row, column=col, sticky="w", padx=4, pady=2)
            ttk.Entry(self.custom_image_frame, textvariable=var, width=18, state="readonly").grid(row=grid_row, column=col + 1, sticky="ew", padx=4, pady=2)
            ttk.Button(self.custom_image_frame, text="Browse...", command=lambda d=digit: self.browse_custom_digit(d)).grid(row=grid_row, column=col + 2, padx=2, pady=2)
            ttk.Button(self.custom_image_frame, text="Clear", command=lambda d=digit: self.custom_digit_vars[d].set("")).grid(row=grid_row, column=col + 3, padx=2, pady=2)
        sep_row = 6
        digit = "colon"
        var = tk.StringVar(value=existing_custom.get(digit, ""))
        self.custom_digit_vars[digit] = var
        ttk.Label(self.custom_image_frame, text="Separator (:)").grid(row=sep_row, column=0, sticky="w", padx=4, pady=(6, 2))
        ttk.Entry(self.custom_image_frame, textvariable=var, width=28, state="readonly").grid(row=sep_row, column=1, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        ttk.Button(self.custom_image_frame, text="Browse...", command=lambda d="colon": self.browse_custom_digit(d)).grid(row=sep_row, column=3, padx=2, pady=(6, 2))
        ttk.Button(self.custom_image_frame, text="Clear", command=lambda d="colon": self.custom_digit_vars[d].set("")).grid(row=sep_row, column=4, padx=2, pady=(6, 2))
        for col in range(8):
            self.custom_image_frame.columnconfigure(col, weight=1 if col in (1, 5) else 0)

        self.kind_var.trace_add("write", lambda *_: self._update_type_sections())
        self._update_type_sections()

        # Colour controls
        self._color_row(frame, 22, "Text colour", self.text_var, lambda: self.pick_color(self.text_var))
        ttk.Checkbutton(frame, text="Transparent", variable=self.text_transparent_var).grid(row=22, column=2, sticky="w", padx=4)
        self._color_row(frame, 23, "Accent / hands", self.accent_var, lambda: self.pick_color(self.accent_var))
        ttk.Checkbutton(frame, text="Transparent", variable=self.accent_transparent_var).grid(row=23, column=2, sticky="w", padx=4)
        self._color_row(frame, 24, "Face / panel", self.face_var, lambda: self.pick_color(self.face_var))
        ttk.Checkbutton(frame, text="Transparent", variable=self.face_transparent_var).grid(row=24, column=2, sticky="w", padx=4)

        buttons = ttk.Frame(frame)
        buttons.grid(row=25, column=0, columnspan=3, pady=(10, 0), sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Apply", command=self.apply).pack(side="right", padx=4)

    def _update_type_sections(self):
        kind = self.kind_var.get()
        if kind == "nixie":
            self.nixie_frame.grid()
        else:
            self.nixie_frame.grid_remove()
        if kind == "custom_image":
            self.custom_image_frame.grid()
        else:
            self.custom_image_frame.grid_remove()

    def browse_custom_digit(self, digit):
        path = filedialog.askopenfilename(
            parent=self, title=(f"Choose image for digit {digit}" if digit != "colon" else "Choose image for separator (:)"),
            filetypes=[("Images", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg *.webp"), ("All files", "*.*")],
        )
        if path:
            try:
                self.app._load_pil_image_safely(path)
            except (OSError, ValueError, RuntimeError) as exc:
                messagebox.showerror("Custom Digit", f"Could not open the image.\n\n{exc}", parent=self)
                return
            self.custom_digit_vars[digit].set(os.path.abspath(os.path.expanduser(path)))

    def _color_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        f = ttk.Frame(parent)
        f.grid(row=row, column=1, sticky="w", padx=8, pady=4)
        ttk.Entry(f, textvariable=variable, width=13).pack(side="left")
        ttk.Button(f, text="Choose...", command=command).pack(side="left", padx=5)

    def pick_color(self, variable):
        chosen = colorchooser.askcolor(color=variable.get(), parent=self, title="Choose Colour")
        if chosen and chosen[1]:
            variable.set(chosen[1])

    def apply(self):
        c = self.clock
        c.kind = self.kind_var.get()
        c.timezone = self.tz_var.get().strip() or "local"
        c.label = self.label_var.get()
        c.font_family = self.font_var.get() or tkfont.nametofont("TkDefaultFont").actual("family")
        c.font_weight = self.weight_var.get()
        c.size = max(0.08, min(0.75, self.size_var.get() / 100.0))
        c.show_seconds = bool(self.seconds_var.get())
        c.use_24h = bool(self.h24_var.get())
        c.show_ampm = bool(self.ampm_var.get())
        c.text_color = self.app._safe_colour(self.text_var.get(), "#FFFFFF")
        c.accent_color = self.app._safe_colour(self.accent_var.get(), "#FFFFFF")
        c.face_color = self.app._safe_colour(self.face_var.get(), "#111111")
        c.text_transparent = bool(self.text_transparent_var.get())
        c.accent_transparent = bool(self.accent_transparent_var.get())
        c.face_transparent = bool(self.face_transparent_var.get())
        c.segment_off_transparent = bool(self.segment_off_transparent_var.get())
        skin_label = self.nixie_skin_display.get()
        c.nixie_skin = self.nixie_skin_map.get(skin_label, "classic_orange")
        c.nixie_custom = {key: self.app._safe_colour(var.get(), NIXIE_SKINS["custom"][key])
                          for key, var in self.nixie_custom_vars.items()}
        c.custom_digit_paths = {}
        if c.kind == "custom_image":
            for digit, var in self.custom_digit_vars.items():
                path = var.get().strip()
                if path:
                    try:
                        self.app._load_pil_image_safely(path)
                    except (OSError, ValueError, RuntimeError) as exc:
                        messagebox.showerror("Custom Digit", f"Digit {digit}: could not open the image.\n\n{exc}", parent=self)
                        return
                    c.custom_digit_paths[digit] = path
        # Legacy image assignments are no longer used by the vector Nixie renderer.
        c.nixie_digit_paths = {}
        self.app.nixie_digit_sources = {}
        self.app.nixie_digit_refs = {}
        self.app.nixie_digit_cache = {}
        self.app.custom_digit_sources = {}
        self.app.custom_digit_refs = {}
        self.app.custom_digit_cache = {}
        if c.kind == "custom_image":
            for digit, path in c.custom_digit_paths.items():
                try:
                    self.app.custom_digit_sources[(c.clock_id, digit)] = self.app._load_pil_image_safely(path)
                except (OSError, ValueError, RuntimeError):
                    pass
        self.app.selected_id = c.clock_id
        self.app.draw()
        self.app._schedule_autosave()
        self.destroy()


class LinkedTextEditor(tk.Toplevel):
    def __init__(self, app, data=None, kind="ampm", initial_position=None):
        super().__init__(app)
        self.app = app
        self.data = data
        self.kind = kind
        names = {"ampm": "AM/PM Widget", "day": "Day Widget", "date": "Date Widget"}
        self.title(("Edit " if data else "Add ") + names.get(kind, "Widget"))
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        defaults = {"ampm": (0.16, 0.50), "day": (0.28, 0.65), "date": (0.30, 0.73)}
        default_size, default_y = defaults.get(kind, (0.28, 0.65))
        self.initial_position = initial_position or (0.5, default_y)
        clocks = [(str(c.clock_id), f"{c.label or ('Clock ' + str(c.clock_id))} ({c.timezone})") for c in app.clocks]
        self.clock_ids = [cid for cid, _ in clocks]
        linked_id = data.linked_clock_id if data else (self.clock_ids[0] if self.clock_ids else "")
        self.clock_var = tk.StringVar(value=str(linked_id))
        self.font_var = tk.StringVar(value=data.font_family if data else "DejaVu Sans")
        self.weight_var = tk.StringVar(value=data.font_weight if data else ("bold" if kind == "ampm" else "normal"))
        self.text_var = tk.StringVar(value=data.text_color if data else "#FFFFFF")
        self.accent_var = tk.StringVar(value=data.accent_color if data else "#FFFFFF")
        self.face_var = tk.StringVar(value=data.face_color if data else "#111111")
        self.transparent_var = tk.BooleanVar(value=data.face_transparent if data else True)
        self.size_var = tk.DoubleVar(value=round((data.size if data else default_size) * 100, 1))
        self.label_var = tk.StringVar(value=data.label if data else "")
        self.day_format_var = tk.StringVar(value=(data.day_format if (data is not None and kind == "day") else "full"))
        self.date_format_var = tk.StringVar(value=(data.date_format if (data is not None and kind == "date") else "long"))

        frame = ttk.Frame(self, padding=10); frame.grid(row=0,column=0,sticky="nsew")
        pad={"padx":8,"pady":4}
        ttk.Label(frame,text="Link to clock").grid(row=0,column=0,sticky="w",**pad)
        ttk.Combobox(frame,textvariable=self.clock_var,values=self.clock_ids,state="readonly",width=42).grid(row=0,column=1,**pad)
        ttk.Label(frame,text="Label").grid(row=1,column=0,sticky="w",**pad)
        ttk.Entry(frame,textvariable=self.label_var,width=28).grid(row=1,column=1,**pad)
        row=2
        if kind == "day":
            ttk.Label(frame,text="Weekday format").grid(row=row,column=0,sticky="w",**pad)
            ttk.Combobox(frame,textvariable=self.day_format_var,values=("full","short","upper"),state="readonly",width=28).grid(row=row,column=1,**pad)
            row += 1
        elif kind == "date":
            ttk.Label(frame,text="Date format").grid(row=row,column=0,sticky="w",**pad)
            ttk.Combobox(frame,textvariable=self.date_format_var,values=("long","short","numeric_eu","numeric_us","iso","weekday_long"),state="readonly",width=28).grid(row=row,column=1,**pad)
            row += 1
        ttk.Label(frame,text="Size (%)").grid(row=row,column=0,sticky="w",**pad)
        tk.Scale(frame,from_=8,to=(80 if kind=="ampm" else 95),resolution=1,orient="horizontal",variable=self.size_var,length=230).grid(row=row,column=1,**pad); row+=1
        ttk.Label(frame,text="Font family").grid(row=row,column=0,sticky="w",**pad)
        ttk.Combobox(frame,textvariable=self.font_var,values=app.font_families,width=28).grid(row=row,column=1,**pad); row+=1
        ttk.Label(frame,text="Weight").grid(row=row,column=0,sticky="w",**pad)
        ttk.Combobox(frame,textvariable=self.weight_var,values=("normal","bold"),state="readonly",width=18).grid(row=row,column=1,**pad); row+=1
        for label,var in (("Text colour",self.text_var),("Accent colour",self.accent_var),("Face colour",self.face_var)):
            self._color_row(frame,row,label,var); row+=1
        ttk.Checkbutton(frame,text="Transparent widget face",variable=self.transparent_var).grid(row=row,column=1,sticky="w",padx=8,pady=4); row+=1
        buttons=ttk.Frame(frame); buttons.grid(row=row,column=0,columnspan=2,sticky="e",pady=(10,0))
        ttk.Button(buttons,text="Cancel",command=self.destroy).pack(side="right",padx=4)
        ttk.Button(buttons,text="Apply",command=self.apply).pack(side="right",padx=4)
    def _color_row(self,parent,row,label,var):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",padx=8,pady=4)
        f=ttk.Frame(parent); f.grid(row=row,column=1,sticky="w",padx=8,pady=4)
        ttk.Entry(f,textvariable=var,width=13).pack(side="left")
        ttk.Button(f,text="Choose...",command=lambda:self.pick_color(var)).pack(side="left",padx=5)
    def pick_color(self,var):
        chosen=colorchooser.askcolor(color=var.get(),parent=self,title="Choose Colour")
        if chosen and chosen[1]: var.set(chosen[1])
    def apply(self):
        try:
            linked=int(self.clock_var.get())
        except (TypeError,ValueError):
            messagebox.showerror("Widget","Select a clock to link to.",parent=self); return
        if not self.app.get_clock(linked):
            messagebox.showerror("Widget","The selected clock no longer exists.",parent=self); return
        common=dict(linked_clock_id=linked,size=max(0.08,min(0.80 if self.kind=="ampm" else 0.95,self.size_var.get()/100.0)),font_family=self.app._safe_font_family(self.font_var.get()),
                    font_weight=self.app._safe_font_weight(self.weight_var.get()),text_color=self.app._safe_colour(self.text_var.get(),"#FFFFFF"),
                    accent_color=self.app._safe_colour(self.accent_var.get(),"#FFFFFF"),face_color=self.app._safe_colour(self.face_var.get(),"#111111"),
                    face_transparent=bool(self.transparent_var.get()),label=self.app._safe_text(self.label_var.get(),"",200))
        if self.data is None:
            x,y=self.initial_position
            if self.kind == "ampm":
                self.app.add_ampm_widget(x=x,y=y,**common)
            elif self.kind == "day":
                self.app.add_day_widget(x=x,y=y,day_format=self.day_format_var.get(),**common)
            else:
                self.app.add_date_widget(x=x,y=y,date_format=self.date_format_var.get(),**common)
        else:
            d=self.data
            d.linked_clock_id=linked; d.size=common["size"]; d.font_family=common["font_family"]; d.font_weight=common["font_weight"]; d.text_color=common["text_color"]; d.accent_color=common["accent_color"]; d.face_color=common["face_color"]; d.face_transparent=common["face_transparent"]; d.label=common["label"]
            if self.kind == "ampm":
                self.app.selected_ampm_id=d.ampm_id
            elif self.kind == "day":
                d.day_format=self.day_format_var.get(); self.app.selected_day_id=d.day_id
            else:
                d.date_format=self.date_format_var.get(); self.app.selected_date_id=d.date_id
            self.app.selected_id=None; self.app.selected_image_id=None; self.app.selected_quote_id=None; self.app.selected_ampm_id=(d.ampm_id if self.kind=="ampm" else None); self.app.selected_day_id=(d.day_id if self.kind=="day" else None); self.app.selected_date_id=(d.date_id if self.kind=="date" else None)
            self.app.draw(); self.app._schedule_autosave()
        self.destroy()


class QuoteEditor(tk.Toplevel):
    def __init__(self, app, quote_data=None, initial_position=None):
        super().__init__(app)
        self.app = app
        self.quote_data = quote_data
        self.title("Edit Quotes Widget" if quote_data else "Add Quotes Widget")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        existing = quote_data.quotes if quote_data else ["Write your first quote here."]
        self.quote_items = list(existing)
        self.font_var = tk.StringVar(value=quote_data.font_family if quote_data else "DejaVu Sans")
        self.weight_var = tk.StringVar(value=quote_data.font_weight if quote_data else "normal")
        self.text_var = tk.StringVar(value=quote_data.text_color if quote_data else "#FFFFFF")
        self.accent_var = tk.StringVar(value=quote_data.accent_color if quote_data else "#FFFFFF")
        self.face_var = tk.StringVar(value=quote_data.face_color if quote_data else "#111111")
        self.transparent_var = tk.BooleanVar(value=quote_data.face_transparent if quote_data else True)
        self.random_var = tk.BooleanVar(value=quote_data.randomize if quote_data else False)
        self.interval_var = tk.DoubleVar(value=quote_data.interval if quote_data else 20.0)
        self.size_var = tk.DoubleVar(value=round((quote_data.size if quote_data else 0.45) * 100, 1))
        self.label_var = tk.StringVar(value=quote_data.label if quote_data else "")

        frame = ttk.Frame(self, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        pad = {"padx": 8, "pady": 4}

        ttk.Label(frame, text="Quotes").grid(row=0, column=0, sticky="nw", **pad)
        list_frame = ttk.Frame(frame)
        list_frame.grid(row=0, column=1, columnspan=2, sticky="nsew", **pad)
        self.listbox = tk.Listbox(list_frame, width=55, height=10, selectmode="browse")
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        for item in self.quote_items:
            self.listbox.insert("end", item)

        button_col = ttk.Frame(frame)
        button_col.grid(row=0, column=3, sticky="ns", padx=(0, 8), pady=4)
        ttk.Button(button_col, text="Add", command=self.add_item).pack(fill="x", pady=2)
        ttk.Button(button_col, text="Edit", command=self.edit_item).pack(fill="x", pady=2)
        ttk.Button(button_col, text="Remove", command=self.remove_item).pack(fill="x", pady=2)

        ttk.Label(frame, text="Rotation interval (seconds)").grid(row=1, column=0, sticky="w", **pad)
        tk.Spinbox(frame, from_=1, to=3600, increment=1, textvariable=self.interval_var, width=10).grid(row=1, column=1, sticky="w", **pad)
        ttk.Checkbutton(frame, text="Randomise next quote", variable=self.random_var).grid(row=2, column=1, sticky="w", padx=8, pady=2)
        ttk.Label(frame, text="Widget label").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.label_var, width=26).grid(row=3, column=1, **pad)
        ttk.Label(frame, text="Widget width (%)").grid(row=4, column=0, sticky="w", **pad)
        tk.Scale(frame, from_=12, to=95, resolution=1, orient="horizontal", variable=self.size_var, length=240).grid(row=4, column=1, **pad)
        ttk.Label(frame, text="Font family").grid(row=5, column=0, sticky="w", **pad)
        ttk.Combobox(frame, textvariable=self.font_var, values=app.font_families, width=30).grid(row=5, column=1, **pad)
        ttk.Label(frame, text="Weight").grid(row=6, column=0, sticky="w", **pad)
        ttk.Combobox(frame, textvariable=self.weight_var, values=("normal", "bold"), state="readonly", width=18).grid(row=6, column=1, **pad)
        self._color_row(frame, 7, "Text colour", self.text_var)
        self._color_row(frame, 8, "Accent colour", self.accent_var)
        self._color_row(frame, 9, "Face colour", self.face_var)
        ttk.Checkbutton(frame, text="Transparent quote face", variable=self.transparent_var).grid(row=10, column=1, sticky="w", padx=8, pady=4)

        buttons = ttk.Frame(frame)
        buttons.grid(row=11, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Apply", command=self.apply).pack(side="right", padx=4)

        if initial_position and not quote_data:
            self.initial_position = initial_position
        else:
            self.initial_position = (0.5, 0.75)

    def _color_row(self, parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        f = ttk.Frame(parent)
        f.grid(row=row, column=1, sticky="w", padx=8, pady=4)
        ttk.Entry(f, textvariable=variable, width=13).pack(side="left")
        ttk.Button(f, text="Choose...", command=lambda: self.pick_color(variable)).pack(side="left", padx=5)

    def pick_color(self, variable):
        chosen = colorchooser.askcolor(color=variable.get(), parent=self, title="Choose Colour")
        if chosen and chosen[1]:
            variable.set(chosen[1])

    def add_item(self):
        text = simpledialog.askstring("Add Quote", "Quote text:", parent=self)
        if text and text.strip():
            self.quote_items.append(text.strip())
            self.listbox.insert("end", text.strip())

    def edit_item(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        index = sel[0]
        text = simpledialog.askstring("Edit Quote", "Quote text:", initialvalue=self.quote_items[index], parent=self)
        if text is not None and text.strip():
            self.quote_items[index] = text.strip()
            self.listbox.delete(index)
            self.listbox.insert(index, text.strip())
            self.listbox.selection_set(index)

    def remove_item(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        index = sel[0]
        del self.quote_items[index]
        self.listbox.delete(index)

    def apply(self):
        quotes = [self.app._safe_text(q, "", MAX_QUOTE_LENGTH).strip() for q in self.quote_items if self.app._safe_text(q, "", MAX_QUOTE_LENGTH).strip()]
        quotes = quotes[:MAX_QUOTES_PER_WIDGET]
        if not quotes:
            messagebox.showerror("Quotes", "Add at least one quote.", parent=self)
            return
        try:
            interval = max(1.0, float(self.interval_var.get()))
        except (TypeError, ValueError):
            messagebox.showerror("Quotes", "Rotation interval must be a number.", parent=self)
            return
        if self.quote_data is None:
            x, y = self.initial_position
            self.app.add_quote_widget(
                quotes, x=x, y=y, size=self.size_var.get()/100.0,
                font_family=self.font_var.get() or tkfont.nametofont("TkDefaultFont").actual("family"),
                font_weight=self.weight_var.get(), text_color=self.text_var.get() or "#FFFFFF",
                accent_color=self.accent_var.get() or "#FFFFFF", face_color=self.face_var.get() or "#111111",
                face_transparent=bool(self.transparent_var.get()), interval=interval,
                randomize=bool(self.random_var.get()), label=self.label_var.get(),
            )
        else:
            q = self.quote_data
            q.quotes = quotes
            q.interval = interval
            q.randomize = bool(self.random_var.get())
            q.font_family = self.font_var.get() or tkfont.nametofont("TkDefaultFont").actual("family")
            q.font_weight = self.weight_var.get()
            q.text_color = self.text_var.get() or "#FFFFFF"
            q.accent_color = self.accent_var.get() or "#FFFFFF"
            q.face_color = self.face_var.get() or "#111111"
            q.face_transparent = bool(self.transparent_var.get())
            q.size = max(0.12, min(0.95, self.size_var.get()/100.0))
            q.label = self.label_var.get()
            q.current_index = min(q.current_index, len(q.quotes) - 1)
            q.last_changed = time.time()
            self.app.selected_quote_id = q.quote_id
            self.app.selected_id = None
            self.app.selected_image_id = None
            self.app.draw()
            self.app._schedule_autosave()
        self.destroy()


class ImageEditor(tk.Toplevel):
    def __init__(self, app, image_data):
        super().__init__(app)
        self.app = app
        self.image_data = image_data
        self.title(f"Edit Image {image_data.image_id}")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.path_var = tk.StringVar(value=image_data.path)
        self.label_var = tk.StringVar(value=image_data.label)
        self.size_var = tk.DoubleVar(value=round(image_data.size * 100, 1))

        frame = ttk.Frame(self, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        pad = {"padx": 8, "pady": 4}

        ttk.Label(frame, text="Image file").grid(row=0, column=0, sticky="w", **pad)
        file_row = ttk.Frame(frame)
        file_row.grid(row=0, column=1, sticky="w", **pad)
        ttk.Entry(file_row, textvariable=self.path_var, width=34).pack(side="left")
        ttk.Button(file_row, text="Browse...", command=self.browse).pack(side="left", padx=5)

        ttk.Label(frame, text="Label").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.label_var, width=25).grid(row=1, column=1, **pad)

        ttk.Label(frame, text="Width (% of window)").grid(row=2, column=0, sticky="w", **pad)
        tk.Scale(frame, from_=4, to=95, resolution=1, orient="horizontal", variable=self.size_var, length=240).grid(row=2, column=1, **pad)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Apply", command=self.apply).pack(side="right", padx=4)

    def browse(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose Image",
            filetypes=[("Images", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg *.webp"), ("All files", "*.*")],
        )
        if path:
            self.path_var.set(path)

    def apply(self):
        new_path = self.path_var.get().strip()
        if not new_path or not os.path.exists(new_path):
            messagebox.showerror("Image Widget", "Please choose an existing image file.", parent=self)
            return
        if Image is None or ImageTk is None:
            messagebox.showerror("Image Widget", "This feature requires Pillow.", parent=self)
            return
        try:
            source = self.app._load_pil_image_safely(new_path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Image Widget", f"Could not open the image.\n\n{exc}", parent=self)
            return
        try:
            package = self.app._package_dir_from_theme_path(self.app.current_theme_path or CURRENT_THEME_FILE)
            stored_path = self.app._copy_asset_into_package(new_path, package, "image")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Image Widget", f"Could not copy the image into the theme.\n\n{exc}", parent=self)
            return
        img = self.image_data
        img.path = stored_path
        img.label = self.app._safe_text(self.label_var.get(), "", 200)
        img.size = max(0.04, min(0.95, self.size_var.get() / 100.0))
        self.app.image_sources[img.image_id] = source
        self.app.image_source_signatures[img.image_id] = self.app._image_signature(new_path)
        self.app.image_cache.pop(img.image_id, None)
        self.app.selected_image_id = img.image_id
        self.app.selected_id = None
        self.app.draw()
        self.app._schedule_autosave()
        self.destroy()


def main():
    app = ClockApp()
    app.mainloop()


if __name__ == "__main__":
    main()
