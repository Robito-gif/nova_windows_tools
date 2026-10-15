# -*- coding: utf-8 -*-
"""Nova Windows Tools - UI and Terminal Formatting."""

from __future__ import annotations

import os
import sys
from typing import Any

from nova.core.constants import APP_NAME, APP_VERSION, CLAUDE_THEME

# Rich detection
HAS_RICH = False
try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class TerminalUI:
    """Handles terminal rendering, banners, status panels, and categorized help."""

    def __init__(self, low_resource: bool = False):
        self.low_resource = low_resource
        if HAS_RICH and not low_resource:
            custom_theme = Theme({
                "nova.primary": CLAUDE_THEME["primary"],
                "nova.secondary": CLAUDE_THEME["secondary"],
                "nova.accent": CLAUDE_THEME["accent"],
                "nova.success": CLAUDE_THEME["success"],
                "nova.warning": CLAUDE_THEME["warning"],
                "nova.error": CLAUDE_THEME["error"],
                "nova.dim": CLAUDE_THEME["dim"],
                "nova.bright": CLAUDE_THEME["bright"],
            })
            self.console = Console(theme=custom_theme)
        else:
            self.console = None

    def print(self, message: str = "") -> None:
        """Render text with optional rich formatting."""
        if self.console and HAS_RICH and not self.low_resource:
            self.console.print(message)
        else:
            # Strip simple rich tags if any
            import re
            clean = re.sub(r"\[/?(?:bold|dim|cyan|white|green|yellow|red|#[0-9A-Fa-f]{6}|nova\.[a-z]+)\]", "", message)
            print(clean)

    def print_error(self, message: str) -> None:
        """Render error message."""
        if self.console and HAS_RICH and not self.low_resource:
            self.console.print(f"  [bold #F87171]✕ {message}[/]")
        else:
            print(f"  ✕ {message}")

    def print_success(self, message: str) -> None:
        """Render success message."""
        if self.console and HAS_RICH and not self.low_resource:
            self.console.print(f"  [bold #34D399]✓ {message}[/]")
        else:
            print(f"  ✓ {message}")

    def print_warning(self, message: str) -> None:
        """Render warning message."""
        if self.console and HAS_RICH and not self.low_resource:
            self.console.print(f"  [bold #FBBF24]⚠ {message}[/]")
        else:
            print(f"  ⚠ {message}")

    def clear(self) -> None:
        """Clear terminal screen."""
        if self.console and HAS_RICH and not self.low_resource:
            try:
                self.console.clear()
                return
            except Exception:
                pass
        os.system("cls" if os.name == "nt" else "clear")

    def print_banner(self) -> None:
        """Display the modern Nova Windows Tools header banner."""
        if not self.console or not HAS_RICH or self.low_resource:
            print("\n" + "=" * 65)
            print(f"   ✦ {APP_NAME.upper()}  v{APP_VERSION}")
            print("   Yeni Nesil Windows Komut ve Ekosistem Yönetim Platformu")
            print("=" * 65)
            print("   Yardım için: ' help' (normal) veya '/help' (sistem)")
            print("   Ayarlar için: '>'  │  Güncellemeler için: '#'")
            print("=" * 65 + "\n")
            return

        logo_text = (
            f"[bold #E07A5F] ▟█▙ [/][bold #38BDF8]{APP_NAME.upper()}[/] "
            f"[dim #64748B]v{APP_VERSION} │ Windows Power, MCP & Ecosystem Platform[/]"
        )

        header_panel = Panel(
            logo_text,
            box=ROUNDED,
            border_style=CLAUDE_THEME["primary"],
            padding=(0, 2),
            subtitle="[dim]Komut kategorileri: ' help' (Normal) │ '/system' │ '>' (Ayarlar) │ '#' (Güncelleme)[/dim]",
            subtitle_align="right",
        )
        self.console.print()
        self.console.print(header_panel)

    def show_help_menu(self) -> None:
        """Render categorized help menu separating the 5 command types."""
        if not self.console or not HAS_RICH or self.low_resource:
            self._show_plain_help()
            return

        table = Table(box=ROUNDED, border_style=CLAUDE_THEME["secondary"], padding=(0, 1))
        table.add_column("Kategori", style="bold #E07A5F", width=18)
        table.add_column("Ön Ek & Örnek Komut", style="bold #38BDF8", width=30)
        table.add_column("Açıklama", style="white")

        # Category A: Normal Commands
        table.add_row(
            "A. Normal Komutlar\n(Başında 1 Boşluk)",
            " help\n version\n status\n clear\n apps\n exit",
            "Yardım kılavuzunu açar\nSürüm ve çalışma ortamını gösterir\nUyanıklık ve sistem durumunu gösterir\nTerminal ekranını temizler\nAlgılanan uygulamaları listeler\nProgramdan güvenle çıkar",
        )
        table.add_row(
            "",
            " start [süre]\n stop\n display on/off\n pomodoro\n record [süre]\n studio",
            "Uyanık modunu başlatır (örn: ' start 30dk')\nUyanık modunu durdurur\nEkranın kararmasını önler veya serbest bırakır\n25 dk odak oturumu başlatır\nEkran kaydını başlatır (Ctrl+C ile durur)\nCanlı kayıt ve sahne stüdyosunu açar",
        )
        table.add_section()

        # Category B: Important Commands
        table.add_row(
            "B. Önemli Komutlar\n(Başında '/')",
            "/system\n/diagnostics\n/processes\n/mcp\n/ecosystem\n/security\n/update",
            "Ayrıntılı Windows sistem ve donanım bilgisi\nSistem bileşenleri ve API tanılaması\nÇalışan süreçleri inceleme ve izleme\nMCP sunucularını yönetme (list/create/start/stop)\nNova ekosistemi ve kurulu araçların genel durumu\nGüvenlik durumu, yetkiler ve denetim günlüğü\nUygulama güncelleme işlemlerini yönetir",
        )
        table.add_section()

        # Category C: Settings
        table.add_row(
            "C. Ayarlar Merkezi\n(Başında '>')",
            ">\n> apps\n> ai\n> mcp\n> development\n> system\n> updates\n> network\n> security",
            "Etkileşimli hiyerarşik Nova Ayarlar Merkezi'ni açar\nKurulu ve algılanan uygulamaların ayarları\nYapay zekâ ve model entegrasyonu ayarları\nMCP sunucusu ve izin ayarları\nPython, Git ve paket yöneticisi ayarları\nWindows güç ve sistem optimizasyonu ayarları\nGüncelleme kanalları ve otomatik kontrol ayarları\nWebSocket ve yerel ağ ayarları\nGüvenlik, onaylar ve denetim günlüğü ayarları",
        )
        table.add_section()

        # Category D: Settings Exit
        table.add_row(
            "D. Ayarlardan Çıkış\n(Başında '<')",
            "<",
            "Ayarlar merkezinde bir üst menüye döner.\nAna ayarlar ekranındayken terminale döner.\nKaydedilmemiş değişiklik varsa onay sorar.",
        )
        table.add_section()

        # Category E: Full Update System
        table.add_row(
            "E. Güncelleme Sistemi\n(Başında '#')",
            "#\n# check\n# preview\n# download\n# install\n# full\n# history\n# rollback",
            "Tam güncelleme merkezini açar\nMevcut güncellemeleri kontrol eder\nYapılacak değişiklikleri ve changelog'u önizler\nDoğrulanmış güncellemeleri indirir (SHA256 kontrolü)\nYedek alarak onaylı güncellemeleri kurar\nTam güncelleme iş akışını baştan sona yürütür\nÖnceki güncelleme işlemlerinin geçmişini gösterir\nSorun durumunda önceki sürüme geri döner",
        )

        panel = Panel(
            table,
            title="[bold #E07A5F]✦ NOVA WINDOWS TOOLS — KOMUT REFERANS REHBERİ[/]",
            subtitle="[dim]Komutların başındaki ön ek sembolü (boşluk, /, >, <, #) kategori yönlendirmesini belirler[/dim]",
            box=ROUNDED,
            border_style=CLAUDE_THEME["secondary"],
        )
        self.console.print(panel)

    def _show_plain_help(self) -> None:
        """Plain text fallback help."""
        print("""
================================================================================
✦ NOVA WINDOWS TOOLS — KOMUT REFERANS REHBERİ
================================================================================
A. NORMAL KOMUTLAR (Başında 1 adet boşluk):
   help                  : Bu yardım kılavuzunu açar
   version               : Sürüm ve çalışma ortamını gösterir
   status                : Güç ve ekran uyanıklık durumunu gösterir
   clear                 : Terminal ekranını temizler
   apps                  : Algılanan uygulamaları listeler
   exit                  : Programdan güvenle çıkar
   start [süre]          : Uyanık modunu başlatır (örn: ' start 30dk')
   stop                  : Uyanık modunu durdurur
   record [süre]         : Ekran kaydı başlatır
   studio                : Canlı stüdyoyu açar

B. ÖNEMLİ SİSTEM KOMUTLARI (Başında '/'):
  /system                : Ayrıntılı Windows sistem ve donanım bilgisi
  /diagnostics           : Sistem bileşenleri ve API tanılaması
  /processes             : Çalışan süreçleri inceleme ve arama
  /mcp                   : MCP sunucularını yönetme (list/create/start/stop)
  /ecosystem             : Nova ekosistemi ve araç durumları
  /security              : Güvenlik, yetkiler ve denetim günlüğü
  /update                : Güncelleme merkezini açar

C. NOVA AYARLAR MERKEZİ (Başında '>'):
  >                      : Hiyerarşik etkileşimli ayarlar merkezini açar
  > apps                 : Algılanan uygulamaların ayarları
  > ai                   : Yapay zekâ ve model entegrasyonu ayarları
  > mcp                  : MCP sunucusu varsayılanları ve izinleri
  > development          : Python, Git ve paket yöneticisi ayarları
  > system               : Güç planı ve düşük donanım ayarları
  > updates              : Güncelleme kanalları ve otomatik kontrol
  > network              : WebSocket ve yerel ağ ayarları
  > security             : Güvenlik onayları ve günlük ayarları

D. AYARLARDAN ÇIKIŞ (Başında '<'):
  <                      : Bir üst seviyeye döner veya ayarları kapatır

E. TAM GÜNCELLEME SİSTEMİ (Başında '#'):
  #                      : Güncelleme merkezini açar
  # check                : Güncellemeleri kontrol eder
  # preview              : Değişiklikleri ve changelog'u önizler
  # download             : Güncellemeleri indirir ve SHA256 doğrular
  # install              : Yedek alarak güncellemeyi kurar
  # full                 : Tam güncelleme iş akışını yürütür
  # history              : Güncelleme geçmişini gösterir
  # rollback             : Önceki yedekten geri yükler
================================================================================
""")
