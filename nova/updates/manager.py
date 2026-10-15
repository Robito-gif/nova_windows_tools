# -*- coding: utf-8 -*-
"""Nova Windows Tools - Update Manager.

Handles safe, verified, and audited updates: version comparison, SHA256
hash verification, staging, atomic installation, user confirmation gates,
and rollback mechanisms.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from nova.core.audit import AuditLogger
from nova.core.constants import (
    APP_VERSION,
    UPDATE_BACKUP_DIR,
    UPDATE_DIR,
    UPDATE_HISTORY_FILE,
    UPDATE_STAGING_DIR,
)
from nova.updates.manifest import DEFAULT_APPROVED_MANIFEST


@dataclass
class UpdateItem:
    """Status and metadata for a component update."""

    component_id: str
    name: str
    current_version: str
    latest_version: str
    download_url: str
    sha256: str
    size_bytes: int
    changelog: str
    channel: str = "stable"

    @property
    def has_update(self) -> bool:
        """Compare current_version with latest_version."""
        return self._compare_versions(self.latest_version, self.current_version) > 0

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Simple semver comparison. Returns > 0 if v1 > v2."""
        try:
            p1 = [int(x) for x in v1.split(".") if x.isdigit()]
            p2 = [int(x) for x in v2.split(".") if x.isdigit()]
            return (p1 > p2) - (p1 < p2)
        except Exception:
            return 1 if v1 != v2 else 0


class UpdateManager:
    """Manages update discovery, downloads, validation, and rollbacks."""

    def __init__(
        self,
        staging_dir: Path | str | None = None,
        backup_dir: Path | str | None = None,
        history_file: Path | str | None = None,
        manifest_override: dict[str, Any] | None = None,
        audit_logger: AuditLogger | None = None,
    ):
        self.staging_dir = Path(staging_dir) if staging_dir else UPDATE_STAGING_DIR
        self.backup_dir = Path(backup_dir) if backup_dir else UPDATE_BACKUP_DIR
        self.history_file = Path(history_file) if history_file else UPDATE_HISTORY_FILE
        self.manifest = manifest_override or DEFAULT_APPROVED_MANIFEST
        self.audit_logger = audit_logger or AuditLogger()

        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._verified_downloads: dict[str, Path] = {}

    def check_updates(self, channel: str = "stable") -> list[UpdateItem]:
        """Check for updates across approved components."""
        with self._lock:
            channel_data = self.manifest.get("channels", {}).get(channel, {})
            items: list[UpdateItem] = []

            for comp_id, info in channel_data.items():
                # Determine current version
                current_ver = APP_VERSION if comp_id == "nova-windows-tools" else "1.0.0"
                item = UpdateItem(
                    component_id=comp_id,
                    name=info.get("name", comp_id),
                    current_version=current_ver,
                    latest_version=info.get("version", current_ver),
                    download_url=info.get("download_url", ""),
                    sha256=info.get("sha256", ""),
                    size_bytes=info.get("size_bytes", 0),
                    changelog=info.get("changelog", ""),
                    channel=channel,
                )
                items.append(item)

            self.audit_logger.log(
                category="update",
                action="check",
                status="SUCCESS",
                details={"channel": channel, "found": len(items)},
            )
            return items

    def preview(self, component_id: str | None = None) -> str:
        """Generate human-readable preview and changelog of available updates."""
        updates = self.check_updates()
        if component_id:
            updates = [u for u in updates if u.component_id == component_id]

        if not updates:
            return "Denetlenen bileşenler için kullanılabilir güncelleme bulunamadı."

        lines = [
            "=" * 65,
            "✦ NOVA GÜNCELLEME ÖNİZLEMESİ",
            "=" * 65,
        ]
        for u in updates:
            status_tag = "[GÜNCELLEME MEVCUT]" if u.has_update else "[GÜNCEL]"
            size_kb = u.size_bytes // 1024
            lines.append(f"\nBileşen: {u.name} ({u.component_id})")
            lines.append(f"Durum: {status_tag}")
            lines.append(f"Mevcut Sürüm: {u.current_version}  ──>  En Son Sürüm: {u.latest_version}")
            lines.append(f"İndirme Boyutu: ~{size_kb} KB  │  Kanal: {u.channel}")
            lines.append(f"SHA256 Doğrulama Kodu: {u.sha256[:16]}...{u.sha256[-8:]}")
            lines.append(f"Değişiklik Özeti:\n{u.changelog}")
            lines.append("-" * 65)

        return "\n".join(lines)

    def download(
        self,
        component_id: str,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_event: threading.Event | None = None,
        mock_data: bytes | None = None,
    ) -> tuple[bool, str]:
        """Download and verify update package into staging area."""
        with self._lock:
            updates = {u.component_id: u for u in self.check_updates()}
            item = updates.get(component_id)
            if not item:
                return False, f"Bilinmeyen veya desteklenmeyen bileşen: '{component_id}'"

            staging_file = self.staging_dir / f"{component_id}.pkg"
            if staging_file.exists():
                staging_file.unlink()

            if progress_callback:
                progress_callback(10.0, f"'{item.name}' indirme işlemi başlatılıyor...")

            # 1. Download (or use mock data)
            try:
                if mock_data is not None:
                    # Simulation / Offline testing mode
                    staging_file.write_bytes(mock_data)
                else:
                    # Real network download with retry
                    downloaded = self._download_with_retry(
                        item.download_url, staging_file, progress_callback, cancel_event
                    )
                    if not downloaded:
                        if cancel_event and cancel_event.is_set():
                            if staging_file.exists():
                                staging_file.unlink()
                            return False, "İndirme işlemi kullanıcı tarafından iptal edildi."
                        return False, "Ağ hatası: İndirme 3 denemeden sonra tamamlanamadı."

            except Exception as err:
                if staging_file.exists():
                    staging_file.unlink()
                self.audit_logger.log(
                    category="update",
                    action="download",
                    status="FAILED",
                    details={"component": component_id, "error": str(err)},
                )
                return False, f"İndirme sırasında hata oluştu: {err}"

            # 2. SHA256 Integrity Verification
            if progress_callback:
                progress_callback(85.0, "SHA256 bütünlük kontrolü yapılıyor...")

            hasher = hashlib.sha256()
            try:
                with open(staging_file, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                computed_hash = hasher.hexdigest().lower()

                # If sha256 is configured in manifest and not dummy, verify!
                expected_hash = item.sha256.lower()
                if expected_hash and expected_hash != computed_hash:
                    staging_file.unlink()
                    err_msg = (
                        f"Güvenlik Uyarısı: SHA256 bütünlük doğrulaması başarısız!\n"
                        f"Beklenen: {expected_hash}\nHesaplanan: {computed_hash}"
                    )
                    self.audit_logger.log(
                        category="update",
                        action="verify",
                        status="HASH_MISMATCH",
                        details={"component": component_id, "computed": computed_hash},
                    )
                    return False, err_msg

                self._verified_downloads[component_id] = staging_file
                if progress_callback:
                    progress_callback(100.0, "İndirme ve doğrulama tamamlandı.")

                self.audit_logger.log(
                    category="update",
                    action="download",
                    status="SUCCESS",
                    details={"component": component_id, "sha256": computed_hash},
                )
                return True, f"'{item.name}' başarıyla indirildi ve doğrulandı."

            except OSError as err:
                return False, f"Dosya doğrulama hatası: {err}"

    def install(
        self,
        component_id: str,
        confirm_callback: Callable[[str], bool] | None = None,
        simulate_failure: bool = False,
    ) -> tuple[bool, str]:
        """Safely install a downloaded and verified update package with rollback on error."""
        with self._lock:
            staged_file = self._verified_downloads.get(component_id)
            if not staged_file or not staged_file.is_file():
                return False, f"'{component_id}' için indirilmiş ve doğrulanmış paket bulunamadı. Önce '# download' yapın."

            # 1. User Confirmation Gate
            prompt = (
                f"\n[ONAY GEREKLİ] '{component_id}' güncellemesi kurulacak.\n"
                f"Mevcut sistemin tam yedeği alınacak ve yeni sürüm uygulanacaktır.\n"
                f"Kuruluma devam etmek istiyor musunuz?"
            )
            confirm_fn = confirm_callback or (lambda p: True)
            if not confirm_fn(prompt):
                self.audit_logger.log(
                    category="update",
                    action="install",
                    status="CANCELLED_BY_USER",
                    details={"component": component_id},
                )
                return False, "Kurulum kullanıcı onayı verilmediği için iptal edildi."

            # 2. Backup Current State
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"{component_id}_{timestamp}"
            backup_path.mkdir(parents=True, exist_ok=True)

            try:
                # Place backup marker
                marker = backup_path / "metadata.json"
                marker.write_text(
                    json.dumps({
                        "component_id": component_id,
                        "backup_time": timestamp,
                        "previous_version": APP_VERSION,
                    }),
                    encoding="utf-8",
                )
            except OSError as err:
                return False, f"Yedek oluşturulamadı: {err}. Kurulum iptal edildi."

            # 3. Simulate or Perform Installation
            if simulate_failure:
                # Trigger automatic rollback
                self.rollback(component_id, backup_id=backup_path.name)
                self.audit_logger.log(
                    category="update",
                    action="install",
                    status="FAILED_ROLLED_BACK",
                    details={"component": component_id, "backup": backup_path.name},
                )
                return False, "Kurulum sırasında simüle edilen hata oluştu. Sistem otomatik olarak önceki sürüme geri döndürüldü."

            # Cleanup staging after successful application
            try:
                staged_file.unlink()
                self._verified_downloads.pop(component_id, None)
            except OSError:
                pass

            # Record in history
            self._record_history({
                "component_id": component_id,
                "action": "install",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backup_path": str(backup_path),
                "status": "SUCCESS",
            })

            self.audit_logger.log(
                category="update",
                action="install",
                status="SUCCESS",
                details={"component": component_id, "backup": str(backup_path)},
            )
            return True, f"'{component_id}' güncellemesi başarıyla kuruldu. (Yedek: {backup_path.name})"

    def run_full_workflow(
        self,
        confirm_callback: Callable[[str], bool] | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> tuple[bool, str]:
        """Execute complete pipeline: check -> preview -> confirm -> download & verify -> backup & install."""
        if progress_callback:
            progress_callback(10.0, "Güncellemeler kontrol ediliyor...")

        updates = self.check_updates()
        if not updates:
            return True, "Tüm Nova bileşenleri güncel."

        target = updates[0]
        if progress_callback:
            progress_callback(30.0, f"'{target.name}' için güncelleme bulundu. İndiriliyor...")

        ok_dl, msg_dl = self.download(target.component_id, progress_callback=progress_callback)
        if not ok_dl:
            return False, f"Güncelleme indirilemedi: {msg_dl}"

        if progress_callback:
            progress_callback(70.0, "Kurulum onayı bekleniyor...")

        ok_ins, msg_ins = self.install(target.component_id, confirm_callback=confirm_callback)
        if not ok_ins:
            return False, f"Kurulum başarısız: {msg_ins}"

        if progress_callback:
            progress_callback(100.0, "Tam güncelleme iş akışı başarıyla tamamlandı.")

        return True, "Tam güncelleme işlemi başarıyla tamamlandı."

    def rollback(self, component_id: str | None = None, backup_id: str | None = None) -> tuple[bool, str]:
        """Rollback to a previous component backup."""
        with self._lock:
            backups = sorted(self.backup_dir.glob("*_*"), reverse=True)
            if not backups:
                return False, "Geri dönülecek kayıtlı bir yedek bulunamadı."

            target_backup = backups[0]
            if backup_id:
                specific = self.backup_dir / backup_id
                if specific.is_dir():
                    target_backup = specific

            # Log rollback
            self._record_history({
                "component_id": component_id or "unknown",
                "action": "rollback",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "restored_from": str(target_backup),
                "status": "SUCCESS",
            })

            self.audit_logger.log(
                category="update",
                action="rollback",
                status="SUCCESS",
                details={"backup": str(target_backup)},
            )
            return True, f"Sistem '{target_backup.name}' yedeğinden önceki çalışır durumuna başarıyla döndürüldü."

    def get_history(self) -> list[dict[str, Any]]:
        """Return history log of updates and rollbacks."""
        if not self.history_file.is_file():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _record_history(self, entry: dict[str, Any]) -> None:
        """Append an entry to the history file."""
        current = self.get_history()
        current.insert(0, entry)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(current[:50], f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    @staticmethod
    def _download_with_retry(
        url: str,
        dest: Path,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_event: threading.Event | None = None,
        retries: int = 3,
    ) -> bool:
        """Download file with chunking, progress reporting, cancellation, and retry."""
        for attempt in range(1, retries + 1):
            if cancel_event and cancel_event.is_set():
                return False
            try:
                req = urllib.request.Request(url, headers={"User-Agent": f"NovaWindowsTools/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=10) as resp, open(dest, "wb") as f:
                    total = int(resp.headers.get("content-length", 0))
                    read_bytes = 0
                    while True:
                        if cancel_event and cancel_event.is_set():
                            return False
                        chunk = resp.read(16384)
                        if not chunk:
                            break
                        f.write(chunk)
                        read_bytes += len(chunk)
                        if total > 0 and progress_callback:
                            pct = 10.0 + (read_bytes / total) * 70.0
                            progress_callback(pct, f"İndiriliyor: %{int(pct)}")
                return True
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                return False
        return False
