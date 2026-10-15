# -*- coding: utf-8 -*-
"""Nova Windows Tools - Built-in Settings Providers.

Provides rich, dynamically registered settings nodes for all ecosystem categories.
"""

from __future__ import annotations

from typing import Protocol

from nova.settings.model import SettingItem


class SettingsProvider(Protocol):
    """Protocol for modular settings registration."""

    category: str
    name: str
    description: str

    def get_settings(self) -> list[SettingItem]:
        """Return collection of configurable items for this provider."""
        ...


class AISettingsProvider:
    """Configures AI, LLM and agent parameters."""

    category = "ai"
    name = "Yapay Zekâ ve Model Entegrasyonu"
    description = "Model seçimi, yerel Ollama/FastMCP bağlantıları ve çıkarım parametreleri."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="ai.default_model",
                name="Varsayılan Yapay Zekâ Modeli",
                current_value="gemini-2.0-flash",
                default_value="gemini-2.0-flash",
                value_type=str,
                description="Nova araçları ve asistanlar için varsayılan model.",
                choices=["gemini-2.0-flash", "gemini-1.5-pro", "claude-3-5-sonnet", "local-ollama", "custom"],
                category=self.category,
            ),
            SettingItem(
                key="ai.ollama_endpoint",
                name="Yerel Ollama Uç Noktası",
                current_value="http://127.0.0.1:11434",
                default_value="http://127.0.0.1:11434",
                value_type=str,
                description="Yerel Ollama servisinin HTTP adresi.",
                category=self.category,
            ),
            SettingItem(
                key="ai.temperature",
                name="Model Sıcaklığı (Temperature)",
                current_value=0.7,
                default_value=0.7,
                value_type=float,
                min_value=0.0,
                max_value=2.0,
                description="Yanıtlardaki rastgelelik ve yaratıcılık seviyesi (0.0 - 2.0).",
                category=self.category,
            ),
            SettingItem(
                key="ai.stream_responses",
                name="Akışlı Yanıtlar (Streaming)",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Yanıtlarda kelime kelime akış gösterilsin mi?",
                category=self.category,
            ),
        ]


class MCPSettingsProvider:
    """Configures default MCP server options and permissions."""

    category = "mcp"
    name = "Model Context Protocol (MCP) Sunucuları"
    description = "Varsayılan portlar, aktarım protokolleri ve genel güvenlik izinleri."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="mcp.default_transport",
                name="Varsayılan Aktarım Protokolü",
                current_value="stdio",
                default_value="stdio",
                value_type=str,
                choices=["stdio", "streamable-http"],
                description="Yeni MCP sunucuları için varsayılan iletişim yöntemi.",
                category=self.category,
            ),
            SettingItem(
                key="mcp.base_port",
                name="Başlangıç Portu",
                current_value=8800,
                default_value=8800,
                value_type=int,
                min_value=1024,
                max_value=65535,
                description="HTTP tabanlı MCP sunucuları için başlangıç port numarası.",
                category=self.category,
            ),
            SettingItem(
                key="mcp.default_allow_screen_capture",
                name="Varsayılan Ekran Yakalama İzni",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Yeni MCP sunucularında ekran görüntüsü alma varsayılan olarak açık olsun mu?",
                category=self.category,
            ),
            SettingItem(
                key="mcp.default_allow_input_control",
                name="Varsayılan Fare/Klavye Kontrol İzni",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Yeni MCP sunucularında giriş kontrolü varsayılan olarak açık olsun mu?",
                category=self.category,
            ),
            SettingItem(
                key="mcp.default_allow_close_application",
                name="Varsayılan Uygulama Kapatma İzni",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Yeni MCP sunucularının başlattıkları süreçleri sonlandırma izni.",
                category=self.category,
            ),
        ]


class DevelopmentSettingsProvider:
    """Configures development tools and environments."""

    category = "development"
    name = "Geliştirme Araçları ve Ortamları"
    description = "Python sanal ortamları, Git entegrasyonu ve paket yöneticisi tercihleri."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="development.preferred_package_manager",
                name="Tercih Edilen Paket Yöneticisi",
                current_value="winget",
                default_value="winget",
                value_type=str,
                choices=["winget", "choco", "scoop", "pip"],
                description="Uygulama kurulumlarında öncelikli kullanılacak araç.",
                category=self.category,
            ),
            SettingItem(
                key="development.auto_detect_venv",
                name="Sanal Ortamları Otomatik Algıla",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Proje dizinindeki .venv ortamını otomatik kullan.",
                category=self.category,
            ),
            SettingItem(
                key="development.git_timeout_seconds",
                name="Git Komut Zaman Aşımı (sn)",
                current_value=30,
                default_value=30,
                value_type=int,
                min_value=5,
                max_value=300,
                description="Git işlemleri için maksimum bekleme süresi.",
                category=self.category,
            ),
        ]


class SystemSettingsProvider:
    """Configures Windows power management and performance modes."""

    category = "system"
    name = "Windows Sistem ve Güç Yönetimi"
    description = "Uyanık tutma süreleri, ekran koruma ve düşük donanım optimizasyonları."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="system.default_duration_minutes",
                name="Varsayılan Uyanıklık Süresi (dk)",
                current_value=0,
                default_value=0,
                value_type=int,
                min_value=0,
                max_value=1440,
                description="Süre verilmediğinde geçerli dakika (0 = süresiz).",
                category=self.category,
            ),
            SettingItem(
                key="system.keep_display_on",
                name="Ekran Kararmasını Önle",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Uyanık modundayken monitörün kararmasını engelle.",
                category=self.category,
            ),
            SettingItem(
                key="system.low_resource_mode",
                name="Düşük Donanım / Pil Tasarrufu Modu",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Arka plan sorgularını ve animasyonları azaltarak CPU/RAM tasarrufu yap.",
                category=self.category,
            ),
            SettingItem(
                key="system.sound_notifications",
                name="Sesli Bildirimler",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Oturum tamamlandığında Windows sistem sesi çal.",
                category=self.category,
            ),
        ]


class UpdatesSettingsProvider:
    """Configures update channels and automation."""

    category = "updates"
    name = "Güncelleme ve Dağıtım Yönetimi"
    description = "Güncelleme kanalları, yedekleme politikası ve doğrulama ayarları."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="updates.channel",
                name="Güncelleme Kanalı",
                current_value="stable",
                default_value="stable",
                value_type=str,
                choices=["stable", "beta", "nightly"],
                description="Alınacak güncelleme kararlılık düzeyi.",
                category=self.category,
            ),
            SettingItem(
                key="updates.auto_check",
                name="Açılışta Güncellemeleri Denetle",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Program açıldığında yeni sürüm olup olmadığını kontrol et.",
                category=self.category,
            ),
            SettingItem(
                key="updates.backup_before_install",
                name="Kurulumdan Önce Yedek Al",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Her güncelleme öncesi mevcut dosyaların yedeğini al.",
                category=self.category,
            ),
            SettingItem(
                key="updates.verify_sha256",
                name="SHA256 Bütünlük Doğrulaması",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="İndirilen paketlerin hash değerini zorunlu kıl.",
                category=self.category,
            ),
        ]


class NetworkSettingsProvider:
    """Configures WebSocket and local network endpoints."""

    category = "network"
    name = "Ağ ve WebSocket Bağlantıları"
    description = "Yerel WebSocket sunucusu, port aralığı ve bağlantı limitleri."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="network.bind_host",
                name="Bağlama Adresi (Bind Host)",
                current_value="127.0.0.1",
                default_value="127.0.0.1",
                value_type=str,
                choices=["127.0.0.1", "localhost"],
                description="Güvenlik nedeniyle yalnızca yerel döngü adresleri kabul edilir.",
                category=self.category,
            ),
            SettingItem(
                key="network.default_ws_port",
                name="Varsayılan WebSocket Portu",
                current_value=8765,
                default_value=8765,
                value_type=int,
                min_value=1024,
                max_value=65535,
                description="Yeni WebSocket servisleri için önerilen port.",
                category=self.category,
            ),
            SettingItem(
                key="network.max_connections_per_service",
                name="Servis Başına Maksimum İstemci",
                current_value=10,
                default_value=10,
                value_type=int,
                min_value=1,
                max_value=100,
                description="Eşzamanlı kabul edilecek WebSocket bağlantısı.",
                category=self.category,
            ),
        ]


class SecuritySettingsProvider:
    """Configures security, authorization, and confirmation prompts."""

    category = "security"
    name = "Güvenlik, Yetkiler ve Denetim Günlüğü"
    description = "İşlem onayları, UAC yetkileri ve hassas veri maskeleme."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="security.confirm_critical_actions",
                name="Kritik İşlemlerde Onay İste",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Süreç kapatma, güncelleme ve sıfırlamada onay sor.",
                category=self.category,
            ),
            SettingItem(
                key="security.audit_logging_enabled",
                name="Denetim Günlüğü (Audit Log) Etkin",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Tüm komut ve güvenlik olaylarını diske kaydet.",
                category=self.category,
            ),
            SettingItem(
                key="security.mask_sensitive_logs",
                name="Günlükte Hassas Bilgileri Maskele",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Şifre, PIN ve token gibi verileri *** ile gizle.",
                category=self.category,
            ),
        ]


class AppsSettingsProvider:
    """Configures application management and external tools."""

    category = "apps"
    name = "Uygulama Entegrasyonları ve Yollar"
    description = "Algılanan masaüstü uygulamaları ve özel çalıştırma parametreleri."

    def get_settings(self) -> list[SettingItem]:
        return [
            SettingItem(
                key="apps.launch_in_background",
                name="Uygulamaları Arka Planda Başlat",
                current_value=False,
                default_value=False,
                value_type=bool,
                description="Masaüstü uygulamalarını simge durumunda veya arka planda aç.",
                category=self.category,
            ),
            SettingItem(
                key="apps.auto_track_launched_processes",
                name="Başlatılan Süreçleri Otomatik Takip Et",
                current_value=True,
                default_value=True,
                value_type=bool,
                description="Nova veya MCP tarafından başlatılan PID'leri veritabanına kaydet.",
                category=self.category,
            ),
        ]
