"""Lightweight local scene composition and studio UI for Easy Windows Tools.

# Copyright (C) 2026 Robin Güneş
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 3 only.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for details.
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import tkinter as tk
from contextlib import contextmanager
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Generator

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageTk

APP_DATA_DIRECTORY = Path(
    os.environ.get("APPDATA", Path.home() / ".config")
) / "EasyWindowsTools"
DEFAULT_PROJECT_PATH = APP_DATA_DIRECTORY / "studio_project.json"
PROJECT_SCHEMA = 1
SUPPORTED_SOURCE_TYPES = {"screen", "image", "text", "color"}
MAX_CANVAS_PIXELS = 3840 * 2160
MAX_SOURCE_DIMENSION = 7680
MAX_IMAGE_CACHE_PIXELS = 3840 * 2160


def _new_scene(name: str, width: int, height: int) -> dict[str, Any]:
    return {
        "id": os.urandom(8).hex(),
        "name": name,
        "sources": [
            {
                "id": os.urandom(8).hex(),
                "name": "Masaüstü",
                "type": "screen",
                "x": 0,
                "y": 0,
                "width": width,
                "height": height,
                "visible": True,
                "locked": True,
                "opacity": 1.0,
                "rotation": 0,
                "crop": [0, 0, 0, 0],
                "monitor": 1,
            },
        ],
    }


class StudioProject:
    """Own a small, validated scene collection and persist it as JSON."""

    def __init__(
        self,
        path: str | Path | None = None,
        width: int = 1280,
        height: int = 720,
    ):
        if not 320 <= width <= 7680 or not 240 <= height <= 4320:
            raise ValueError("Stüdyo çözünürlüğü desteklenen sınırların dışında.")
        if width * height > MAX_CANVAS_PIXELS:
            raise ValueError("İlk stüdyo sürümü en fazla 4K sahne çözünürlüğünü destekler.")
        self.path = Path(path) if path else DEFAULT_PROJECT_PATH
        self.width = width
        self.height = height
        self.transition = {"type": "cut", "duration_ms": 300}
        self.scenes: list[dict[str, Any]] = []
        self.active_scene_id = ""
        if self.path.is_file():
            self.load(self.path)
        else:
            self.scenes = [_new_scene("Sahne 1", width, height)]
            self.active_scene_id = self.scenes[0]["id"]

    @staticmethod
    def _validate_source(source: Any) -> dict[str, Any]:
        if not isinstance(source, dict):
            raise ValueError("Kaynak kaydı hatalı.")
        kind = source.get("type")
        if kind not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(f"Desteklenmeyen kaynak türü: {kind!r}")
        name = source.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Kaynak adı 1-120 karakter olmalıdır.")
        cleaned = {
            "id": str(source.get("id") or os.urandom(8).hex()),
            "name": name.strip(),
            "type": kind,
            "x": int(source.get("x", 0)),
            "y": int(source.get("y", 0)),
            "width": int(source.get("width", 640)),
            "height": int(source.get("height", 360)),
            "visible": source.get("visible", True),
            "locked": source.get("locked", False),
            "opacity": float(source.get("opacity", 1.0)),
            "rotation": int(source.get("rotation", 0)) % 360,
            "crop": list(source.get("crop", [0, 0, 0, 0])),
        }
        if not 1 <= cleaned["width"] <= MAX_SOURCE_DIMENSION:
            raise ValueError("Kaynak genişliği 1-7680 piksel olmalıdır.")
        if not 1 <= cleaned["height"] <= MAX_SOURCE_DIMENSION:
            raise ValueError("Kaynak yüksekliği 1-7680 piksel olmalıdır.")
        if type(cleaned["visible"]) is not bool or type(cleaned["locked"]) is not bool:
            raise ValueError("Kaynak görünürlük ve kilit değerleri boolean olmalıdır.")
        cleaned["x"] = int(cleaned["x"])
        cleaned["y"] = int(cleaned["y"])
        if not -MAX_SOURCE_DIMENSION <= cleaned["x"] <= MAX_SOURCE_DIMENSION:
            raise ValueError("Kaynak X konumu desteklenen sınırların dışında.")
        if not -MAX_SOURCE_DIMENSION <= cleaned["y"] <= MAX_SOURCE_DIMENSION:
            raise ValueError("Kaynak Y konumu desteklenen sınırların dışında.")
        if not 0 <= cleaned["opacity"] <= 1:
            raise ValueError("Kaynak saydamlığı 0 ile 1 arasında olmalıdır.")
        if len(cleaned["crop"]) != 4:
            raise ValueError("Kırpma dört kenar değeri içermelidir.")
        cleaned["crop"] = [max(0, int(value)) for value in cleaned["crop"]]
        if kind == "image":
            image_path = Path(str(source.get("path", ""))).expanduser()
            if not image_path.is_file():
                raise ValueError(f"Görsel kaynağı bulunamadı: {image_path}")
            cleaned["path"] = str(image_path.resolve())
        elif kind == "text":
            text = source.get("text", "")
            if not isinstance(text, str) or len(text) > 4000:
                raise ValueError("Metin kaynağı en fazla 4000 karakter olabilir.")
            cleaned["text"] = text
            cleaned["color"] = str(source.get("color", "#FFFFFF"))
            ImageColor.getrgb(cleaned["color"])
            cleaned["font_size"] = min(256, max(8, int(source.get("font_size", 42))))
        elif kind == "color":
            cleaned["color"] = str(source.get("color", "#202020"))
            ImageColor.getrgb(cleaned["color"])
        elif kind == "screen":
            cleaned["monitor"] = max(1, int(source.get("monitor", 1)))
        return cleaned

    def _validate(self) -> None:
        if not self.scenes:
            raise ValueError("Proje en az bir sahne içermelidir.")
        scene_ids: set[str] = set()
        for scene in self.scenes:
            if not isinstance(scene, dict):
                raise ValueError("Sahne kaydı hatalı.")
            scene_id = str(scene.get("id", ""))
            scene_name = scene.get("name")
            if not scene_id or scene_id in scene_ids:
                raise ValueError("Sahne kimlikleri eksik veya yinelenmiş.")
            scene["id"] = scene_id
            if not isinstance(scene_name, str) or not scene_name.strip() or len(scene_name) > 120:
                raise ValueError("Sahne adı 1-120 karakter olmalıdır.")
            scene_ids.add(scene_id)
            raw_sources = scene.get("sources", [])
            if not isinstance(raw_sources, list) or len(raw_sources) > 100:
                raise ValueError("Bir sahne en fazla 100 kaynak içerebilir.")
            scene["sources"] = [self._validate_source(source) for source in raw_sources]
        if self.active_scene_id not in scene_ids:
            self.active_scene_id = self.scenes[0]["id"]
        transition_type = self.transition.get("type", "cut")
        if transition_type not in {"cut", "fade", "dissolve"}:
            raise ValueError("Geçiş cut, fade veya dissolve olmalıdır.")
        duration = int(self.transition.get("duration_ms", 300))
        if not 0 <= duration <= 5000:
            raise ValueError("Geçiş süresi 0-5000 ms arasında olmalıdır.")
        self.transition = {"type": transition_type, "duration_ms": duration}

    @property
    def active_scene(self) -> dict[str, Any]:
        return next(scene for scene in self.scenes if scene["id"] == self.active_scene_id)

    def save(self, path: str | Path | None = None) -> Path:
        self._validate()
        target = Path(path) if path else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema": PROJECT_SCHEMA,
            "canvas": {"width": self.width, "height": self.height},
            "transition": self.transition,
            "active_scene_id": self.active_scene_id,
            "scenes": self.scenes,
        }
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        self.path = target
        return target

    def load(self, path: str | Path) -> None:
        source = Path(path)
        document = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema") != PROJECT_SCHEMA:
            raise ValueError("Bu stüdyo proje sürümü desteklenmiyor.")
        canvas = document.get("canvas", {})
        if not isinstance(canvas, dict):
            raise ValueError("Proje sahne boyutu kaydı hatalı.")
        width, height = int(canvas.get("width", 1280)), int(canvas.get("height", 720))
        if not 320 <= width <= 7680 or not 240 <= height <= 4320:
            raise ValueError("Proje çözünürlüğü desteklenen sınırların dışında.")
        if width * height > MAX_CANVAS_PIXELS:
            raise ValueError("Proje 4K üzeri bir sahne içeriyor.")
        scenes = document.get("scenes")
        if not isinstance(scenes, list) or len(scenes) > 100:
            raise ValueError("Proje sahne listesi hatalı veya 100 sahneyi aşıyor.")
        old_state = (self.width, self.height, self.scenes, self.active_scene_id, self.transition)
        self.width = width
        self.height = height
        self.scenes = scenes
        self.active_scene_id = str(document.get("active_scene_id", ""))
        self.transition = document.get("transition", {"type": "cut", "duration_ms": 300})
        try:
            self._validate()
        except (TypeError, ValueError, AttributeError) as error:
            self.width, self.height, self.scenes, self.active_scene_id, self.transition = old_state
            raise ValueError(f"Stüdyo projesi geçersiz: {error}") from error
        self.path = source

    def create_scene(self, name: str) -> dict[str, Any]:
        if not name.strip() or len(name) > 120:
            raise ValueError("Sahne adı 1-120 karakter olmalıdır.")
        scene = {"id": os.urandom(8).hex(), "name": name.strip(), "sources": []}
        self.scenes.append(scene)
        self.active_scene_id = scene["id"]
        return scene

    def duplicate_scene(self, scene_id: str) -> dict[str, Any]:
        import copy

        scene = next((item for item in self.scenes if item["id"] == scene_id), None)
        if scene is None:
            raise ValueError("Kopyalanacak sahne bulunamadı.")
        duplicate = copy.deepcopy(scene)
        duplicate["id"] = os.urandom(8).hex()
        duplicate["name"] = f"{scene['name']} kopyası"
        for source in duplicate["sources"]:
            source["id"] = os.urandom(8).hex()
        self.scenes.insert(self.scenes.index(scene) + 1, duplicate)
        self.active_scene_id = duplicate["id"]
        return duplicate

    def delete_scene(self, scene_id: str) -> None:
        if len(self.scenes) <= 1:
            raise ValueError("Son sahne silinemez.")
        index = next(
            (i for i, scene in enumerate(self.scenes) if scene["id"] == scene_id),
            None,
        )
        if index is None:
            raise ValueError("Silinecek sahne bulunamadı.")
        del self.scenes[index]
        if self.active_scene_id == scene_id:
            self.active_scene_id = self.scenes[max(0, index - 1)]["id"]

    def add_source(self, scene_id: str, source: dict[str, Any]) -> dict[str, Any]:
        scene = next((item for item in self.scenes if item["id"] == scene_id), None)
        if scene is None:
            raise ValueError("Kaynak eklenecek sahne bulunamadı.")
        validated = self._validate_source(source)
        scene["sources"].append(validated)
        return validated


class SceneCompositor:
    """Compose one scene into BGRA frames shared by preview and recording."""

    def __init__(self, project: StudioProject):
        self.project = project
        self._lock = threading.RLock()
        self._cache_lock = threading.RLock()
        self._image_cache: dict[str, tuple[int, Image.Image]] = {}
        self._previous_scene_id: str | None = None
        self._transition_started = 0.0

    def switch_scene(self, scene_id: str) -> None:
        with self._lock:
            if not any(scene["id"] == scene_id for scene in self.project.scenes):
                raise ValueError("Geçilecek sahne bulunamadı.")
            if scene_id == self.project.active_scene_id:
                return
            self._previous_scene_id = self.project.active_scene_id
            self.project.active_scene_id = scene_id
            self._transition_started = time.monotonic()

    def _screen_image(self, screen_frame: Image.Image | None) -> Image.Image:
        if screen_frame is not None:
            return screen_frame.convert("RGBA")
        try:
            import mss
        except ImportError as error:
            raise RuntimeError("Masaüstü yakalama için mss paketi gereklidir.") from error
        with mss.MSS() as capture:
            monitor = capture.monitors[1]
            frame = capture.grab(monitor)
            return Image.frombytes(
                "RGBA",
                (frame.width, frame.height),
                frame.bgra,
                "raw",
                "BGRA",
            )

    def _load_image(self, source: dict[str, Any]) -> Image.Image:
        path = source["path"]
        with self._cache_lock:
            modified_at = Path(path).stat().st_mtime_ns
            cached = self._image_cache.get(path)
            if cached and cached[0] == modified_at:
                return cached[1]
            with Image.open(path) as opened:
                if opened.width * opened.height > MAX_CANVAS_PIXELS:
                    raise ValueError(f"Görsel 4K sınırını aşıyor: {path}")
                image = opened.convert("RGBA")
            if image.width * image.height <= MAX_IMAGE_CACHE_PIXELS:
                while self._image_cache and (
                    sum(
                        cached_image.width * cached_image.height
                        for _, cached_image in self._image_cache.values()
                    )
                    + image.width * image.height
                    > MAX_IMAGE_CACHE_PIXELS
                ):
                    self._image_cache.pop(next(iter(self._image_cache)))
                self._image_cache[path] = (modified_at, image)
            return image

    @staticmethod
    def _crop(image: Image.Image, crop: list[int]) -> Image.Image:
        left, top, right, bottom = crop
        x1, y1 = min(left, image.width - 1), min(top, image.height - 1)
        x2, y2 = max(x1 + 1, image.width - right), max(y1 + 1, image.height - bottom)
        return image.crop((x1, y1, x2, y2))

    def _render_scene(
        self,
        scene: dict[str, Any],
        screen_frame: Image.Image | None,
    ) -> Image.Image:
        canvas = Image.new("RGBA", (self.project.width, self.project.height), "#101319")
        screen_image: Image.Image | None = None
        sources = [dict(source) for source in scene["sources"]]
        for source in sources:
            if not source["visible"]:
                continue
            kind = source["type"]
            if kind == "screen":
                if screen_image is None:
                    screen_image = self._screen_image(screen_frame)
                layer = screen_image.copy()
            elif kind == "image":
                layer = self._load_image(source)
            elif kind == "color":
                layer = Image.new(
                    "RGBA",
                    (source["width"], source["height"]),
                    source["color"],
                )
            else:
                layer = Image.new(
                    "RGBA",
                    (source["width"], source["height"]),
                    (0, 0, 0, 0),
                )
                draw = ImageDraw.Draw(layer)
                try:
                    font = ImageFont.truetype(
                        "arial.ttf",
                        source["font_size"],
                    )
                except OSError:
                    font = ImageFont.load_default()
                draw.multiline_text(
                    (4, 4),
                    source["text"],
                    fill=source["color"],
                    font=font,
                    stroke_width=max(0, source["font_size"] // 18),
                    stroke_fill="#000000",
                )
            layer = self._crop(layer, source["crop"])
            layer = layer.resize(
                (source["width"], source["height"]),
                Image.Resampling.BILINEAR,
            )
            rotation = source["rotation"] % 360
            if rotation:
                layer = layer.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
            if source["opacity"] < 1:
                alpha = layer.getchannel("A").point(
                    lambda value: round(value * source["opacity"])
                )
                layer.putalpha(alpha)
            canvas.alpha_composite(layer, (source["x"], source["y"]))
        return canvas.convert("RGB")

    def render(
        self,
        screen_frame: Image.Image | None = None,
        now: float | None = None,
    ) -> Image.Image:
        with self._lock:
            active = self.project.active_scene
            previous_id = self._previous_scene_id
            transition = dict(self.project.transition)
            started = self._transition_started
            scenes = list(self.project.scenes)
        current = self._render_scene(active, screen_frame)
        duration = transition["duration_ms"] / 1000
        if (
            previous_id is None
            or transition["type"] == "cut"
            or duration <= 0
        ):
            return current
        elapsed = (time.monotonic() if now is None else now) - started
        progress = min(1.0, max(0.0, elapsed / duration))
        if progress >= 1:
            with self._lock:
                if self._previous_scene_id == previous_id:
                    self._previous_scene_id = None
            return current
        previous = next((scene for scene in scenes if scene["id"] == previous_id), None)
        if previous is None:
            return current
        before = self._render_scene(previous, screen_frame)
        if transition["type"] == "fade":
            if progress < 0.5:
                return Image.blend(before, Image.new("RGB", before.size, "black"), progress * 2)
            return Image.blend(
                Image.new("RGB", current.size, "black"),
                current,
                (progress - 0.5) * 2,
            )
        return Image.blend(before, current, progress)

    def render_bgra(self, screen_frame: Image.Image | None = None) -> bytes:
        image = self.render(screen_frame)
        rgba = image.convert("RGBA")
        return rgba.tobytes("raw", "BGRA")


class StudioWindow:
    """A small, real-time desktop studio with persistent scenes and sources."""

    def __init__(self, root: tk.Tk, recorder_class: Any, settings: dict[str, Any]):
        self.root = root
        self.recorder_class = recorder_class
        self.settings = settings
        self.project = StudioProject()
        self.compositor = SceneCompositor(self.project)
        self._photo: ImageTk.PhotoImage | None = None
        self._record_thread: threading.Thread | None = None
        self._record_stop = threading.Event()
        self._record_started_at: float | None = None
        self._selected_source_id: str | None = None
        self._drag_offset: tuple[int, int] | None = None
        self._preview_offset = (0, 0)
        self._preview_scale = 1.0
        self._preview_fps = 0.0
        self._preview_queue: queue.Queue[tuple[Image.Image | Exception, float]] = queue.Queue(maxsize=1)
        self._preview_stop = threading.Event()
        self._last_recording: Path | None = None
        self._build_ui()
        self._refresh_scenes()
        self._refresh_sources()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._preview_thread = threading.Thread(
            target=self._preview_worker,
            name="ewt-studio-preview",
            daemon=True,
        )
        self._preview_thread.start()
        self.root.after(50, self._update_preview)
        self.root.after(250, self._poll_recording)

    def _build_ui(self) -> None:
        self.root.title("Easy Windows Tools · Canlı Stüdyo")
        self.root.geometry("1280x820")
        self.root.minsize(980, 650)
        self.root.configure(bg="#111820")
        self.style = ttk.Style(self.root)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self.style.configure("Studio.TFrame", background="#18222d")
        self.style.configure(
            "Studio.TLabel",
            background="#18222d",
            foreground="#e7edf4",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Studio.TButton",
            background="#243241",
            foreground="#f2f5f8",
            padding=(8, 5),
        )
        self.style.configure(
            "Studio.TLabelFrame",
            background="#18222d",
            foreground="#e7edf4",
        )
        header = ttk.Frame(self.root, style="Studio.TFrame", padding=10)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="EWT  /  CANLI STÜDYO",
            style="Studio.TLabel",
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left")
        self.status_var = tk.StringVar(value="Hazır · Önizleme ve sahne kompozisyonu")
        ttk.Label(header, textvariable=self.status_var, style="Studio.TLabel").pack(
            side="right",
        )

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        left = ttk.Frame(body, style="Studio.TFrame", padding=8)
        center = ttk.Frame(body, style="Studio.TFrame", padding=8)
        right = ttk.Frame(body, style="Studio.TFrame", padding=8)
        body.add(left, weight=1)
        body.add(center, weight=4)
        body.add(right, weight=1)

        scenes_box = ttk.LabelFrame(left, text="Sahneler", style="Studio.TLabelFrame", padding=6)
        scenes_box.pack(fill="both", expand=True)
        self.scene_list = tk.Listbox(
            scenes_box,
            height=10,
            bg="#101820",
            fg="#e7edf4",
            selectbackground="#2563a6",
            relief="flat",
            exportselection=False,
        )
        self.scene_list.pack(fill="both", expand=True)
        self.scene_list.bind("<<ListboxSelect>>", self._on_scene_selected)
        for text, command in (
            ("Yeni", self._new_scene),
            ("Kopyala", self._duplicate_scene),
            ("Adlandır", self._rename_scene),
            ("Sil", self._delete_scene),
        ):
            ttk.Button(scenes_box, text=text, command=command, style="Studio.TButton").pack(
                fill="x",
                pady=(5, 0),
            )
        ttk.Label(scenes_box, text="Sahne geçişi", style="Studio.TLabel").pack(
            anchor="w",
            pady=(12, 3),
        )
        self.transition_var = tk.StringVar(value=self.project.transition["type"])
        ttk.Combobox(
            scenes_box,
            textvariable=self.transition_var,
            values=("cut", "fade", "dissolve"),
            state="readonly",
        ).pack(fill="x")
        self.transition_var.trace_add("write", self._save_transition)
        self.transition_ms_var = tk.IntVar(value=self.project.transition["duration_ms"])
        ttk.Scale(
            scenes_box,
            from_=0,
            to=2000,
            variable=self.transition_ms_var,
            command=lambda _value: self._save_transition(),
        ).pack(fill="x", pady=5)

        preview_box = ttk.LabelFrame(
            center,
            text=f"Birleşik önizleme · {self.project.width} × {self.project.height}",
            style="Studio.TLabelFrame",
            padding=6,
        )
        preview_box.pack(fill="both", expand=True)
        self.preview = tk.Canvas(
            preview_box,
            bg="#080c10",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<ButtonPress-1>", self._begin_drag)
        self.preview.bind("<B1-Motion>", self._drag_source)
        self.preview.bind("<ButtonRelease-1>", self._end_drag)

        transport = ttk.Frame(center, style="Studio.TFrame", padding=(0, 8))
        transport.pack(fill="x")
        ttk.Button(
            transport,
            text="● Kaydı başlat",
            command=self._start_recording,
            style="Studio.TButton",
        ).pack(side="left")
        ttk.Button(
            transport,
            text="■ Kaydı durdur",
            command=self._stop_recording,
            style="Studio.TButton",
        ).pack(side="left", padx=6)
        ttk.Button(
            transport,
            text="Projeyi kaydet",
            command=self._save_project,
            style="Studio.TButton",
        ).pack(side="left")
        ttk.Button(
            transport,
            text="Dışa aktar",
            command=self._export_project,
            style="Studio.TButton",
        ).pack(side="left", padx=6)
        ttk.Button(
            transport,
            text="İçe aktar",
            command=self._import_project,
            style="Studio.TButton",
        ).pack(side="left")

        source_box = ttk.LabelFrame(right, text="Kaynaklar", style="Studio.TLabelFrame", padding=6)
        source_box.pack(fill="both", expand=True)
        self.source_list = tk.Listbox(
            source_box,
            height=12,
            bg="#101820",
            fg="#e7edf4",
            selectbackground="#2563a6",
            relief="flat",
            exportselection=False,
        )
        self.source_list.pack(fill="both", expand=True)
        self.source_list.bind("<<ListboxSelect>>", self._on_source_selected)
        for text, command in (
            ("Ekran ekle", self._add_screen),
            ("Görsel ekle", self._add_image),
            ("Metin ekle", self._add_text),
            ("Renk katmanı", self._add_color),
            ("Kaynağı sil", self._delete_source),
            ("Yukarı taşı", lambda: self._move_source(-1)),
            ("Aşağı taşı", lambda: self._move_source(1)),
        ):
            ttk.Button(source_box, text=text, command=command, style="Studio.TButton").pack(
                fill="x",
                pady=(5, 0),
            )
        ttk.Label(
            source_box,
            text="Özellikler · konum / boyut / opaklık",
            style="Studio.TLabel",
            wraplength=200,
        ).pack(anchor="w", pady=(12, 5))
        props = ttk.Frame(source_box, style="Studio.TFrame")
        props.pack(fill="x")
        self.property_vars: dict[str, tk.StringVar] = {}
        for key, title in (
            ("x", "X"),
            ("y", "Y"),
            ("width", "Genişlik"),
            ("height", "Yükseklik"),
            ("opacity", "Opaklık (0-1)"),
        ):
            row = ttk.Frame(props, style="Studio.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=title, style="Studio.TLabel", width=13).pack(side="left")
            variable = tk.StringVar()
            self.property_vars[key] = variable
            ttk.Entry(row, textvariable=variable, width=9).pack(side="right", fill="x", expand=True)
        self.visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            source_box,
            text="Kaynak görünür",
            variable=self.visible_var,
            command=self._apply_properties,
        ).pack(anchor="w", pady=4)
        ttk.Button(
            source_box,
            text="Özellikleri uygula",
            command=self._apply_properties,
            style="Studio.TButton",
        ).pack(fill="x", pady=(4, 0))
        self.stats_var = tk.StringVar(value="Önizleme: -- FPS")
        ttk.Label(
            self.root,
            textvariable=self.stats_var,
            style="Studio.TLabel",
            anchor="w",
            padding=(12, 5),
        ).pack(fill="x")

    def _refresh_scenes(self) -> None:
        self.scene_list.delete(0, tk.END)
        for scene in self.project.scenes:
            self.scene_list.insert(tk.END, scene["name"])
        active_index = next(
            (i for i, scene in enumerate(self.project.scenes)
             if scene["id"] == self.project.active_scene_id),
            0,
        )
        self.scene_list.selection_clear(0, tk.END)
        self.scene_list.selection_set(active_index)
        self.scene_list.activate(active_index)

    def _refresh_sources(self) -> None:
        self.source_list.delete(0, tk.END)
        scene = self.project.active_scene
        for source in reversed(scene["sources"]):
            mark = "●" if source["visible"] else "○"
            self.source_list.insert(tk.END, f"{mark} {source['name']} · {source['type']}")
        self._selected_source_id = None
        self._clear_properties()

    def _selected_source(self) -> dict[str, Any] | None:
        if self._selected_source_id is None:
            return None
        return next(
            (source for source in self.project.active_scene["sources"]
             if source["id"] == self._selected_source_id),
            None,
        )

    def _clear_properties(self) -> None:
        for variable in self.property_vars.values():
            variable.set("")

    def _on_scene_selected(self, _event: Any = None) -> None:
        selection = self.scene_list.curselection()
        if not selection:
            return
        scene = self.project.scenes[selection[0]]
        self.compositor.switch_scene(scene["id"])
        self.project.active_scene_id = scene["id"]
        self._refresh_sources()
        self._autosave()

    def _on_source_selected(self, _event: Any = None) -> None:
        selection = self.source_list.curselection()
        if not selection:
            return
        sources = list(reversed(self.project.active_scene["sources"]))
        source = sources[selection[0]]
        self._selected_source_id = source["id"]
        for key, variable in self.property_vars.items():
            variable.set(str(source[key]))
        self.visible_var.set(source["visible"])

    def _add_source(self, source: dict[str, Any]) -> None:
        added = self.project.add_source(self.project.active_scene_id, source)
        self._selected_source_id = added["id"]
        self._refresh_sources()
        self.source_list.selection_set(0)
        self._on_source_selected()
        self._autosave()

    def _add_screen(self) -> None:
        self._add_source({
            "name": f"Masaüstü {sum(s['type'] == 'screen' for s in self.project.active_scene['sources']) + 1}",
            "type": "screen",
            "width": self.project.width,
            "height": self.project.height,
        })

    def _add_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Görsel kaynağı ekle",
            filetypes=[("Görseller", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Tüm dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            with Image.open(path) as image:
                width, height = image.size
            if width * height > MAX_CANVAS_PIXELS:
                raise ValueError("Görsel 4K piksel sınırını aşıyor.")
            self._add_source({
                "name": Path(path).name,
                "type": "image",
                "path": path,
                "x": 60,
                "y": 60,
                "width": min(width, self.project.width),
                "height": min(height, self.project.height),
            })
        except (OSError, ValueError) as error:
            messagebox.showerror("Görsel açılamadı", str(error), parent=self.root)

    def _add_text(self) -> None:
        text = simpledialog.askstring("Metin katmanı", "Gösterilecek metin:", parent=self.root)
        if not text:
            return
        self._add_source({
            "name": text.splitlines()[0][:40],
            "type": "text",
            "text": text,
            "x": 40,
            "y": 40,
            "width": min(900, self.project.width),
            "height": min(180, self.project.height),
        })

    def _add_color(self) -> None:
        from tkinter.colorchooser import askcolor

        color = askcolor("#202020", parent=self.root)[1]
        if color:
            self._add_source({
                "name": "Renk",
                "type": "color",
                "color": color,
                "width": self.project.width,
                "height": self.project.height,
            })

    def _apply_properties(self) -> None:
        source = self._selected_source()
        if source is None:
            return
        try:
            for key, variable in self.property_vars.items():
                value = float(variable.get()) if key == "opacity" else int(variable.get())
                if key in {"width", "height"} and not 1 <= value <= MAX_SOURCE_DIMENSION:
                    raise ValueError("Kaynak boyutu 1-7680 arasında olmalıdır.")
                if key == "opacity" and not 0 <= value <= 1:
                    raise ValueError("Opaklık 0 ile 1 arasında olmalıdır.")
                source[key] = value
            source["visible"] = self.visible_var.get()
            self._autosave()
            self._refresh_sources()
            self._selected_source_id = source["id"]
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Geçersiz özellik", str(error), parent=self.root)

    def _delete_source(self) -> None:
        source = self._selected_source()
        if source is None:
            return
        self.project.active_scene["sources"].remove(source)
        self._refresh_sources()
        self._autosave()

    def _move_source(self, delta: int) -> None:
        source = self._selected_source()
        if source is None:
            return
        sources = self.project.active_scene["sources"]
        index = sources.index(source)
        target = max(0, min(len(sources) - 1, index + delta))
        if target != index:
            sources[index], sources[target] = sources[target], sources[index]
            self._refresh_sources()
            self._selected_source_id = source["id"]
            display_index = len(sources) - 1 - target
            self.source_list.selection_set(display_index)
            self._on_source_selected()
            self._autosave()

    def _begin_drag(self, event: tk.Event) -> None:
        source = self._selected_source()
        if source is None or source["locked"]:
            return
        offset_x, offset_y = self._preview_offset
        self._drag_offset = (
            int((event.x - offset_x) / self._preview_scale) - source["x"],
            int((event.y - offset_y) / self._preview_scale) - source["y"],
        )

    def _drag_source(self, event: tk.Event) -> None:
        source = self._selected_source()
        if source is None or source["locked"] or self._drag_offset is None:
            return
        offset_x, offset_y = self._preview_offset
        source["x"] = max(
            0,
            int((event.x - offset_x) / self._preview_scale) - self._drag_offset[0],
        )
        source["y"] = max(
            0,
            int((event.y - offset_y) / self._preview_scale) - self._drag_offset[1],
        )
        for key in ("x", "y"):
            self.property_vars[key].set(str(source[key]))

    def _end_drag(self, _event: tk.Event) -> None:
        self._drag_offset = None
        self._autosave()

    def _preview_worker(self) -> None:
        try:
            import mss
        except ImportError as error:
            self._queue_preview_error(
                RuntimeError(f"Masaüstü önizlemesi için mss paketi gerekli: {error}")
            )
            return

        try:
            with mss.MSS() as capture:
                if len(capture.monitors) < 2:
                    self._queue_preview_error(RuntimeError("Masaüstü ekranı bulunamadı."))
                    return
                monitor = capture.monitors[1]
                while not self._preview_stop.is_set():
                    started = time.perf_counter()
                    try:
                        scene = self.project.active_scene
                        has_screen = any(
                            source["visible"] and source["type"] == "screen"
                            for source in scene["sources"]
                        )
                        screen_frame = None
                        if has_screen:
                            shot = capture.grab(monitor)
                            screen_frame = Image.frombytes(
                                "RGBA",
                                (shot.width, shot.height),
                                shot.bgra,
                                "raw",
                                "BGRA",
                            )
                        image = self.compositor.render(screen_frame)
                        payload: Image.Image | Exception = image
                    except (
                        mss.exception.ScreenShotError,
                        OSError,
                        RuntimeError,
                        ValueError,
                    ) as error:
                        payload = error
                    elapsed = max(0.0001, time.perf_counter() - started)
                    self._preview_fps = min(60.0, 1 / elapsed)
                    self._queue_preview_frame(payload, self._preview_fps)
                    self._preview_stop.wait(max(0, 0.1 - elapsed))
        except (mss.exception.ScreenShotError, OSError, RuntimeError) as error:
            self._queue_preview_error(error)

    def _queue_preview_error(self, error: Exception) -> None:
        self._queue_preview_frame(error, 0.0)

    def _queue_preview_frame(
        self,
        payload: Image.Image | Exception,
        fps: float,
    ) -> None:
        try:
            self._preview_queue.put_nowait((payload, fps))
        except queue.Full:
            try:
                self._preview_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._preview_queue.put_nowait((payload, fps))
            except queue.Full:
                pass

    def _update_preview(self) -> None:
        if not self.root.winfo_exists():
            return
        try:
            payload, fps = self._preview_queue.get_nowait()
        except queue.Empty:
            payload = None
            fps = self._preview_fps
        if isinstance(payload, Exception):
            self.status_var.set(f"Önizleme hatası: {payload}")
        elif isinstance(payload, Image.Image):
            self._draw_preview(payload, fps)
        self.root.after(50, self._update_preview)

    def _draw_preview(self, frame: Image.Image, fps: float) -> None:
        width = max(1, self.preview.winfo_width())
        height = max(1, self.preview.winfo_height())
        if width <= 1 or height <= 1:
            return
        scale = min(width / self.project.width, height / self.project.height)
        target_size = (
            max(1, int(self.project.width * scale)),
            max(1, int(self.project.height * scale)),
        )
        preview_image = frame.resize(target_size, Image.Resampling.BILINEAR)
        self._preview_scale = scale
        self._photo = ImageTk.PhotoImage(preview_image, master=self.preview)
        self.preview.delete("all")
        x = (width - preview_image.width) // 2
        y = (height - preview_image.height) // 2
        self._preview_offset = (x, y)
        self.preview.create_image(x, y, anchor="nw", image=self._photo)
        source = self._selected_source()
        if source is not None:
            box = (
                x + int(source["x"] * scale),
                y + int(source["y"] * scale),
                x + int((source["x"] + source["width"]) * scale),
                y + int((source["y"] + source["height"]) * scale),
            )
            self.preview.create_rectangle(*box, outline="#35b8ff", width=2)
        self.stats_var.set(
            f"Önizleme üretimi: {fps:.1f} FPS · "
            f"Çıkış: {self.project.width}×{self.project.height} · "
            f"Ortak kompozit: kayıt/önizleme"
        )

    def _new_scene(self) -> None:
        name = simpledialog.askstring("Yeni sahne", "Sahne adı:", parent=self.root)
        if name:
            previous_id = self.project.active_scene_id
            scene = self.project.create_scene(name)
            self.project.active_scene_id = previous_id
            self.compositor.switch_scene(scene["id"])
            self._refresh_scenes()
            self._refresh_sources()
            self._autosave()

    def _duplicate_scene(self) -> None:
        try:
            previous_id = self.project.active_scene_id
            scene = self.project.duplicate_scene(self.project.active_scene_id)
            self.project.active_scene_id = previous_id
            self.compositor.switch_scene(scene["id"])
            self._refresh_scenes()
            self._refresh_sources()
            self._autosave()
        except ValueError as error:
            messagebox.showerror("Sahne kopyalanamadı", str(error), parent=self.root)

    def _rename_scene(self) -> None:
        name = simpledialog.askstring(
            "Sahneyi adlandır",
            "Yeni ad:",
            initialvalue=self.project.active_scene["name"],
            parent=self.root,
        )
        if name and name.strip():
            self.project.active_scene["name"] = name.strip()
            self._refresh_scenes()
            self._autosave()

    def _delete_scene(self) -> None:
        try:
            self.project.delete_scene(self.project.active_scene_id)
            self.compositor = SceneCompositor(self.project)
            self._refresh_scenes()
            self._refresh_sources()
            self._autosave()
        except ValueError as error:
            messagebox.showerror("Sahne silinemedi", str(error), parent=self.root)

    def _save_transition(self, *_args: Any) -> None:
        self.project.transition = {
            "type": self.transition_var.get(),
            "duration_ms": int(float(self.transition_ms_var.get())),
        }
        self._autosave()

    def _save_project(self) -> bool:
        try:
            path = self.project.save()
            self.status_var.set(f"Proje kaydedildi · {path}")
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror("Proje kaydedilemedi", str(error), parent=self.root)
            return False

    def _autosave(self) -> None:
        try:
            self.project.save()
        except (OSError, ValueError) as error:
            self.status_var.set(f"Otomatik kayıt hatası: {error}")

    def _export_project(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".ewtstudio.json",
            filetypes=[("EWT stüdyo profili", "*.json")],
        )
        if path:
            try:
                project_path = self.project.path
                self.project.save(path)
                self.project.path = project_path
                self.status_var.set(f"Profil dışa aktarıldı · {path}")
            except (OSError, ValueError) as error:
                messagebox.showerror("Dışa aktarma başarısız", str(error), parent=self.root)

    def _import_project(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Stüdyo profili içe aktar",
            filetypes=[("JSON profili", "*.json"), ("Tüm dosyalar", "*.*")],
        )
        if not path:
            return
        try:
            project_path = self.project.path
            self.project.load(path)
            self.project.path = project_path
            self.compositor = SceneCompositor(self.project)
            self._refresh_scenes()
            self._refresh_sources()
            self._autosave()
        except (OSError, json.JSONDecodeError, ValueError) as error:
            messagebox.showerror("Profil içe aktarılamadı", str(error), parent=self.root)

    def _start_recording(self) -> None:
        if self._record_thread and self._record_thread.is_alive():
            return
        if not self._save_project():
            return
        self._record_stop.clear()
        fps = int(self.settings["fps"])
        output_size = (self.project.width, self.project.height)

        def record_job() -> None:
            try:
                manager = self.recorder_class(
                    fps=fps,
                    resolution=output_size,
                    microphone=self.settings.get("microphone"),
                    system_audio=self.settings.get("system_audio"),
                )

                @contextmanager
                def frame_provider() -> Generator[Any, None, None]:
                    import mss

                    with mss.MSS() as capture:
                        monitor = capture.monitors[1]

                        def next_frame() -> bytes:
                            shot = capture.grab(monitor)
                            image = Image.frombytes(
                                "RGBA",
                                (shot.width, shot.height),
                                shot.bgra,
                                "raw",
                                "BGRA",
                            )
                            image = self.compositor.render(image)
                            image = image.resize(output_size, Image.Resampling.BILINEAR)
                            return image.convert("RGBA").tobytes("raw", "BGRA")

                        yield next_frame

                with frame_provider() as next_frame:
                    self._record_started_at = time.monotonic()
                    result = manager.record(
                        duration=None,
                        frame_provider=next_frame,
                        frame_size=output_size,
                        stop_event=self._record_stop,
                    )
                self._last_recording = result[0]
                self.root.after(
                    0,
                    lambda path=result[0]: self.status_var.set(f"Kayıt tamamlandı · {path}"),
                )
            except Exception as error:
                self.root.after(0, lambda message=str(error): self._record_failed(message))
            finally:
                self._record_started_at = None

        self._record_thread = threading.Thread(
            target=record_job,
            name="ewt-studio-recorder",
            daemon=True,
        )
        self._record_thread.start()
        self.status_var.set("Kayıt başlatılıyor…")

    def _record_failed(self, message: str) -> None:
        self.status_var.set(f"Kayıt hatası · {message}")
        messagebox.showerror("Stüdyo kaydı başarısız", message, parent=self.root)

    def _stop_recording(self) -> None:
        if self._record_thread and self._record_thread.is_alive():
            self._record_stop.set()
            self.status_var.set("Kayıt durduruluyor…")

    def _poll_recording(self) -> None:
        if not self.root.winfo_exists():
            return
        thread = self._record_thread
        if thread and thread.is_alive():
            elapsed = (
                time.monotonic() - self._record_started_at
                if self._record_started_at is not None else 0
            )
            self.status_var.set(f"Kayıt sürüyor · {elapsed:.1f} sn")
        self.root.after(250, self._poll_recording)

    def close(self) -> None:
        if self._record_thread and self._record_thread.is_alive():
            if not messagebox.askyesno(
                "Kayıt sürüyor",
                "Kayıt durdurulsun ve stüdyo kapatılsın mı?",
                parent=self.root,
            ):
                return
            self._record_stop.set()
            self.root.after(100, self._wait_for_recording)
            return
        self._preview_stop.set()
        self._autosave()
        self.root.destroy()

    def _wait_for_recording(self) -> None:
        if self._record_thread and self._record_thread.is_alive():
            self.root.after(100, self._wait_for_recording)
            return
        self._preview_stop.set()
        self._autosave()
        self.root.destroy()


def open_studio(recorder_class: Any, settings: dict[str, Any]) -> None:
    root = tk.Tk()
    StudioWindow(root, recorder_class, settings)
    root.mainloop()
