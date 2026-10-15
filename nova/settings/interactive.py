# -*- coding: utf-8 -*-
"""Nova Windows Tools - Interactive Settings REPL.

Implements hierarchical navigation for '>' and back/exit navigation for '<',
including change validation and unsaved modifications guard.
"""

from __future__ import annotations

import shlex
from typing import Any, Callable

from nova.discovery.ecosystem import EcosystemDiscovery
from nova.settings.manager import SettingsManager
from nova.settings.model import SettingItem


class InteractiveSettingsREPL:
    """Manages the interactive settings center navigation state machine."""

    def __init__(
        self,
        settings_manager: SettingsManager,
        discovery: EcosystemDiscovery | None = None,
        print_func: Callable[[str], None] = print,
        confirm_func: Callable[[str], str] | None = None,
    ):
        self.settings = settings_manager
        self.discovery = discovery or EcosystemDiscovery()
        self.print = print_func
        # confirm_func returns "e", "h", or "d"
        self._confirm_func = confirm_func or self._default_unsaved_confirm
        self.current_category: str | None = None
        self.is_active: bool = False

    def enter(self, category: str | None = None) -> None:
        """Activate the settings mode and optionally enter a category."""
        self.is_active = True
        if category:
            cat_clean = category.lower().strip()
            available = {c["category"] for c in self.settings.list_categories()}
            if cat_clean in available:
                self.current_category = cat_clean
            else:
                self.print(f"[Uyarı] '{category}' kategorisi bulunamadı. Ana ayarlar ekranı açılıyor.")
                self.current_category = None
        else:
            self.current_category = None

        self._show_banner()
        self.show_current_view()

    def get_prompt_text(self) -> str:
        """Return the hierarchical breadcrumb prompt string."""
        if self.current_category:
            return f"[Nova Ayarlar > {self.current_category}] ❯ "
        return "[Nova Ayarlar] ❯ "

    def handle_input(self, raw_input: str) -> bool:
        """Handle an input line while in settings mode.

        Returns False if the user exited settings mode, True if remaining.
        """
        raw = raw_input.strip()
        if not raw:
            return True

        # 1. Exit / Back via '<' or 'back'
        if raw == "<" or raw.startswith("<") or raw in ("back", "geri"):
            return self._handle_back()

        # 2. Direct jump via '> <category>'
        if raw.startswith(">"):
            target = raw[1:].strip()
            if not target:
                self.current_category = None
                self.show_current_view()
                return True
            tokens = target.split(maxsplit=1)
            target_cat = tokens[0].lower()
            available = {c["category"] for c in self.settings.list_categories()}
            if target_cat in available:
                self.current_category = target_cat
                self.show_current_view()
            else:
                self.print(f"Bilinmeyen kategori: '{target_cat}'")
            return True

        try:
            tokens = shlex.split(raw, posix=False)
        except ValueError:
            tokens = raw.split()

        cmd = tokens[0].lower()

        if cmd in ("ls", "list", "dir", "göster", "goster"):
            self.show_current_view()
        elif cmd == "cd":
            if len(tokens) < 2:
                self.current_category = None
                self.show_current_view()
            elif tokens[1] in ("..", "<"):
                return self._handle_back()
            else:
                target = tokens[1].lower()
                available = {c["category"] for c in self.settings.list_categories()}
                if target in available:
                    self.current_category = target
                    self.show_current_view()
                else:
                    self.print(f"Kategori bulunamadı: '{target}'")
        elif cmd == "set":
            if len(tokens) < 3:
                self.print("Kullanım: set <ayar_anahtarı> <yeni_değer>")
                self.print("Örnek: set ai.default_model gemini-1.5-pro")
            else:
                key = tokens[1]
                val = tokens[2]
                ok, err = self.settings.set_value(key, val)
                if ok:
                    self.print(f"✓ '{key}' güncellendi -> {val} (Kaydetmek için 'save' yazın).")
                else:
                    self.print(f"✕ Hata: {err}")
        elif cmd == "get":
            if len(tokens) < 2:
                self.print("Kullanım: get <ayar_anahtarı>")
            else:
                self._show_item_detail(tokens[1])
        elif cmd in ("save", "kaydet"):
            if self.settings.save():
                self.print("✓ Tüm ayarlar başarıyla kalıcı olarak kaydedildi.")
            else:
                self.print("✕ Ayarlar kaydedilirken hata oluştu.")
        elif cmd in ("revert", "iptal"):
            self.settings.revert_unsaved()
            self.print("✓ Kaydedilmemiş değişiklikler iptal edildi.")
        elif cmd == "reset":
            cat_to_reset = tokens[1] if len(tokens) > 1 else self.current_category
            reset_keys = self.settings.reset_defaults(cat_to_reset)
            if reset_keys:
                self.print(f"✓ {len(reset_keys)} ayar varsayılana sıfırlandı: {', '.join(reset_keys)}")
            else:
                self.print("Sıfırlanacak ayar bulunamadı veya değerler zaten varsayılanda.")
        elif cmd in ("search", "ara"):
            if len(tokens) < 2:
                self.print("Kullanım: search <arama_ifadesi>")
            else:
                self._show_search_results(tokens[1])
        elif cmd in ("status", "durum"):
            self._show_ecosystem_status()
        elif cmd in ("export", "dışaaktar", "disaaktar"):
            if len(tokens) < 2:
                self.print("Kullanım: export <dosya_yolu.json>")
            else:
                if self.settings.export_to_file(tokens[1]):
                    self.print(f"✓ Ayarlar başarıyla dışa aktarıldı: {tokens[1]}")
                else:
                    self.print("✕ Dışa aktarma başarısız oldu.")
        elif cmd in ("import", "içeaktar", "iceaktar"):
            if len(tokens) < 2:
                self.print("Kullanım: import <dosya_yolu.json>")
            else:
                ok, msg = self.settings.import_from_file(tokens[1])
                self.print(f"{'✓' if ok else '✕'} {msg}")
        elif cmd in ("help", "yardım", "yardim", "?"):
            self._show_help()
        elif cmd in ("exit", "quit", "çıkış", "cikis"):
            return self._handle_back(force_exit=True)
        else:
            self.print(f"Ayarlar merkezinde bilinmeyen komut: '{cmd}'. Yardım için 'help' yazın.")

        return True

    def _handle_back(self, force_exit: bool = False) -> bool:
        """Handle moving up or exiting with unsaved changes verification.

        Returns False if exited settings mode, True if still active.
        """
        # If in a subcategory and not forcing full exit, move up to root
        if self.current_category and not force_exit:
            self.current_category = None
            self.show_current_view()
            return True

        # At root level (or forcing exit): check for unsaved changes!
        if self.settings.has_unsaved_changes():
            dirty = self.settings.dirty_keys
            prompt = (
                f"\n[DİKKAT] Kaydedilmemiş {len(dirty)} ayar değişikliği var: {', '.join(dirty)}\n"
                f"Nasıl devam etmek istersiniz?\n"
                f"  [E] Kaydet ve Çık\n"
                f"  [H] Değişiklikleri İptal Et ve Çık\n"
                f"  [D] Düzenlemeye Devam Et"
            )
            choice = self._confirm_func(prompt).lower().strip()
            if choice in ("e", "evet", "save", "yes", "y"):
                self.settings.save()
                self.print("✓ Değişiklikler kaydedildi. Ayarlar merkezinden çıkılıyor...")
                self.is_active = False
                return False
            elif choice in ("h", "hayır", "hayir", "discard", "no", "n"):
                self.settings.revert_unsaved()
                self.print("✓ Değişiklikler iptal edildi. Ayarlar merkezinden çıkılıyor...")
                self.is_active = False
                return False
            else:
                self.print("Ayarlar düzenlemesine devam ediliyor.")
                return True

        # No unsaved changes: safe exit
        self.print("Ayarlar merkezinden çıkıldı. Ana terminale dönüldü.")
        self.is_active = False
        return False

    def _default_unsaved_confirm(self, prompt: str) -> str:
        """Console prompt for unsaved changes."""
        try:
            return input(f"{prompt}\nSeçiminiz [E/H/D]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "d"

    def show_current_view(self) -> None:
        """Render the current hierarchy view (categories or items)."""
        if self.current_category:
            self._show_category_items(self.current_category)
        else:
            self._show_categories()

    def _show_categories(self) -> None:
        """Render the top-level categories overview."""
        cats = self.settings.list_categories()
        dirty_count = len(self.settings.dirty_keys)
        status_notice = f" [bold #FBBF24]({dirty_count} kaydedilmemiş değişiklik)[/]" if dirty_count else ""

        self.print(f"\n[Nova Ekosistem Ayar Kategorileri]{status_notice}")
        self.print("─" * 60)
        for cat in cats:
            self.print(f"  > [bold cyan]{cat['category']:<14}[/] │ {cat['name']} [dim]({cat['item_count']} ayar)[/]")
            self.print(f"    [dim]{cat['description']}[/]")
        self.print("─" * 60)
        self.print("Gezinme: Bir kategoriye girmek için '> <kategori>' veya 'cd <kategori>' yazın.")
        self.print("Çıkış: Ana ekrana dönmek için '<' yazın.")

    def _show_category_items(self, category: str) -> None:
        """Render all settings within a chosen category."""
        items = self.settings.list_items(category)
        self.print(f"\n[Kategori: {category.upper()}] (Toplam {len(items)} ayar)")
        self.print("─" * 70)
        for item in items:
            is_dirty = item.key in self.settings.dirty_keys
            dirty_badge = " *[DEĞİŞTİ]" if is_dirty else ""
            self.print(f"  • [bold white]{item.key}[/]{dirty_badge}")
            self.print(f"    Adı: {item.name}")
            self.print(f"    Mevcut Değer: [bold green]{item.current_value}[/]  (Varsayılan: {item.default_value})")
            if item.choices:
                self.print(f"    Seçenekler: {', '.join(map(str, item.choices))}")
            if item.min_value is not None or item.max_value is not None:
                self.print(f"    Aralık: {item.min_value} - {item.max_value}")
            self.print(f"    [dim]{item.description}[/]\n")
        self.print("─" * 70)
        self.print("Ayar Değiştir: 'set <anahtar> <değer>'  │  Ayrıntı: 'get <anahtar>'")
        self.print("Kaydet: 'save'  │  Geri / Çık: '<'")

    def _show_item_detail(self, key: str) -> None:
        """Display thorough detail for a single setting."""
        item = self.settings.get_item(key)
        if not item:
            self.print(f"Ayar bulunamadı: '{key}'")
            return

        is_dirty = key in self.settings.dirty_keys
        self.print(f"\n[Ayar Ayrıntısı: {item.key}]")
        self.print(f"  Adı: {item.name}")
        self.print(f"  Kategori: {item.category}")
        self.print(f"  Tür: {item.value_type.__name__}")
        self.print(f"  Mevcut Değer: {item.current_value} {'(Kaydedilmemiş değişiklik)' if is_dirty else ''}")
        self.print(f"  Varsayılan Değer: {item.default_value}")
        if item.choices:
            self.print(f"  İzin Verilen Değerler: {', '.join(map(str, item.choices))}")
        if item.min_value is not None or item.max_value is not None:
            self.print(f"  Geçerli Değer Aralığı: {item.min_value} - {item.max_value}")
        if item.dependencies:
            self.print(f"  Bağımlılıklar: {', '.join(item.dependencies)}")
        self.print(f"  Açıklama: {item.description}")
        self.print(f"  Yeniden Başlatma Gerekir: {'Evet' if item.requires_restart else 'Hayır'}")

    def _show_search_results(self, query: str) -> None:
        """Display search results across all categories."""
        matches = self.settings.search(query)
        self.print(f"\n'{query}' için {len(matches)} arama sonucu bulundu:")
        self.print("─" * 60)
        for item in matches:
            self.print(f"  • {item.key} [{item.category}] -> {item.current_value}")
            self.print(f"    [dim]{item.description}[/]")
        self.print("─" * 60)

    def _show_ecosystem_status(self) -> None:
        """Display dynamic status information from EcosystemDiscovery."""
        components = self.discovery.discover_all(force_refresh=True)
        self.print("\n[Nova Ekosistem Bileşen Durumları]")
        self.print("─" * 65)
        for comp in components:
            status_text = comp.status.value.upper()
            color = "green" if comp.status.value in ("installed", "active") else "yellow" if comp.status.value == "disabled" else "red"
            self.print(f"  • [{color}]{status_text:<12}[/] {comp.name:<30} [dim]{comp.version or ''}[/]")
            if comp.path:
                self.print(f"    [dim]Yol: {comp.path}[/]")
        self.print("─" * 65)

    def _show_banner(self) -> None:
        """Display the welcome header for settings center."""
        self.print("\n" + "=" * 60)
        self.print("  ✦ NOVA WINDOWS TOOLS — AYARLAR MERKEZİ")
        self.print("  Hiyerarşik, modüler ve güvenli ekosistem yapılandırması")
        self.print("=" * 60)

    def _show_help(self) -> None:
        """Show settings center commands."""
        self.print("\nAyarlar Merkezi Komutları:")
        self.print("  ls / list               : Mevcut kategori veya ayarları listele")
        self.print("  cd <kategori>           : Belirtilen ayar kategorisine geç")
        self.print("  set <anahtar> <değer>   : Ayar değerini değiştir (staged)")
        self.print("  get <anahtar>           : Bir ayarın tüm ayrıntılarını görüntüle")
        self.print("  save                    : Değişiklikleri diske kaydet")
        self.print("  revert                  : Kaydedilmemiş değişiklikleri geri al")
        self.print("  reset [kategori]        : Varsayılan ayarlara geri dön")
        self.print("  search <ifade>          : Ayarlarda arama yap")
        self.print("  status                  : Algılanan sistem bileşenlerinin durumunu gör")
        self.print("  export <dosya.json>     : Ayarları dışa aktar")
        self.print("  import <dosya.json>     : Ayarları içe aktar")
        self.print("  <                       : Bir üst seviyeye dön veya ayarlardan çık")
