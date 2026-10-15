# -*- coding: utf-8 -*-
"""Nova Windows Tools - Ecosystem Discovery Service.

Performs on-demand discovery of tools, development runtimes, AI engines,
MCP servers, and installed Windows desktop applications. Caches results
to maintain low-spec PC efficiency.
"""

from __future__ import annotations

import enum
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ComponentStatus(str, enum.Enum):
    """Accurate lifecycle and availability status of a component."""

    INSTALLED = "installed"          # Present and functional
    ACTIVE = "active"                # Currently running process/service
    DISABLED = "disabled"            # Present but intentionally disabled
    MISSING = "missing"              # Not detected on system
    INCOMPATIBLE = "incompatible"    # Detected but version/OS incompatible
    INACCESSIBLE = "inaccessible"    # Permission or file lock restriction


@dataclass
class DiscoveredComponent:
    """Detailed record of a discovered system or ecosystem component."""

    id: str
    name: str
    category: str  # "development", "ai", "mcp", "system", "apps", "package_manager"
    status: ComponentStatus
    version: str | None = None
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class EcosystemDiscovery:
    """Thread-safe on-demand ecosystem discovery engine with caching."""

    CACHE_TTL_SECONDS = 300  # 5 minutes cache

    def __init__(self, mcp_manager: Any = None):
        self.mcp_manager = mcp_manager
        self._cached_components: dict[str, DiscoveredComponent] = {}
        self._last_scan_time: float = 0.0
        self._lock = threading.Lock()

    def discover_all(self, force_refresh: bool = False) -> list[DiscoveredComponent]:
        """Discover all supported system components with on-demand caching."""
        with self._lock:
            now = time.time()
            if not force_refresh and (now - self._last_scan_time < self.CACHE_TTL_SECONDS) and self._cached_components:
                return list(self._cached_components.values())

            components: dict[str, DiscoveredComponent] = {}

            # 1. Development Environment
            components.update(self._scan_development_tools())

            # 2. Package Managers
            components.update(self._scan_package_managers())

            # 3. AI and Local Inference Tools
            components.update(self._scan_ai_tools())

            # 4. System Capabilities (FFmpeg, Power, Monitors)
            components.update(self._scan_system_capabilities())

            # 5. MCP Services
            components.update(self._scan_mcp_servers())

            # 6. Installed Windows Applications (subset/sample from registry)
            components.update(self._scan_installed_applications())

            self._cached_components = components
            self._last_scan_time = time.time()
            return list(components.values())

    def get_component(self, component_id: str) -> DiscoveredComponent | None:
        """Retrieve a specific component by ID."""
        all_comps = {c.id: c for c in self.discover_all(force_refresh=False)}
        return all_comps.get(component_id)

    def _scan_development_tools(self) -> dict[str, DiscoveredComponent]:
        """Inspect Python, Git, Node, and VS Code."""
        results: dict[str, DiscoveredComponent] = {}

        # Python
        py_path = sys.executable
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        is_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        results["python"] = DiscoveredComponent(
            id="python",
            name="Python Runtime",
            category="development",
            status=ComponentStatus.ACTIVE,
            version=py_ver,
            path=py_path,
            details={"is_virtualenv": is_venv, "prefix": sys.prefix},
        )

        # Git
        git_exe = shutil.which("git")
        if git_exe:
            git_ver = self._run_command([git_exe, "--version"])
            results["git"] = DiscoveredComponent(
                id="git",
                name="Git Version Control",
                category="development",
                status=ComponentStatus.INSTALLED,
                version=git_ver.replace("git version", "").strip() if git_ver else None,
                path=git_exe,
            )
        else:
            results["git"] = DiscoveredComponent(
                id="git",
                name="Git Version Control",
                category="development",
                status=ComponentStatus.MISSING,
            )

        # Node.js
        node_exe = shutil.which("node")
        if node_exe:
            node_ver = self._run_command([node_exe, "-v"])
            results["nodejs"] = DiscoveredComponent(
                id="nodejs",
                name="Node.js Runtime",
                category="development",
                status=ComponentStatus.INSTALLED,
                version=node_ver.strip() if node_ver else None,
                path=node_exe,
            )
        else:
            results["nodejs"] = DiscoveredComponent(
                id="nodejs",
                name="Node.js Runtime",
                category="development",
                status=ComponentStatus.MISSING,
            )

        # VS Code
        code_exe = shutil.which("code")
        if code_exe:
            code_ver = self._run_command([code_exe, "--version"])
            first_line = code_ver.splitlines()[0] if code_ver else None
            results["vscode"] = DiscoveredComponent(
                id="vscode",
                name="Visual Studio Code",
                category="development",
                status=ComponentStatus.INSTALLED,
                version=first_line,
                path=code_exe,
            )
        else:
            results["vscode"] = DiscoveredComponent(
                id="vscode",
                name="Visual Studio Code",
                category="development",
                status=ComponentStatus.MISSING,
            )

        return results

    def _scan_package_managers(self) -> dict[str, DiscoveredComponent]:
        """Inspect winget, chocolatey, scoop, and pip."""
        results: dict[str, DiscoveredComponent] = {}

        for pm_id, pm_name, cmd in [
            ("winget", "Windows Package Manager (winget)", "winget"),
            ("choco", "Chocolatey", "choco"),
            ("scoop", "Scoop", "scoop"),
            ("pip", "Pip Package Installer", "pip"),
        ]:
            exe = shutil.which(cmd)
            if exe:
                ver = self._run_command([exe, "--version"])
                results[pm_id] = DiscoveredComponent(
                    id=pm_id,
                    name=pm_name,
                    category="package_manager",
                    status=ComponentStatus.INSTALLED,
                    version=ver.splitlines()[0].strip() if ver else None,
                    path=exe,
                )
            else:
                results[pm_id] = DiscoveredComponent(
                    id=pm_id,
                    name=pm_name,
                    category="package_manager",
                    status=ComponentStatus.MISSING,
                )

        return results

    def _scan_ai_tools(self) -> dict[str, DiscoveredComponent]:
        """Inspect FastMCP and local AI engines (e.g. Ollama)."""
        results: dict[str, DiscoveredComponent] = {}

        # FastMCP / MCP Python SDK
        try:
            import mcp
            mcp_ver = getattr(mcp, "__version__", "1.x")
            results["fastmcp"] = DiscoveredComponent(
                id="fastmcp",
                name="Model Context Protocol (FastMCP)",
                category="ai",
                status=ComponentStatus.INSTALLED,
                version=mcp_ver,
                details={"sdk": "Python mcp"},
            )
        except ImportError:
            results["fastmcp"] = DiscoveredComponent(
                id="fastmcp",
                name="Model Context Protocol (FastMCP)",
                category="ai",
                status=ComponentStatus.MISSING,
            )

        # Ollama local inference
        ollama_exe = shutil.which("ollama")
        ollama_running = self._check_http_service("http://127.0.0.1:11434/api/tags")

        if ollama_running:
            results["ollama"] = DiscoveredComponent(
                id="ollama",
                name="Ollama Local LLM Engine",
                category="ai",
                status=ComponentStatus.ACTIVE,
                path=ollama_exe or "127.0.0.1:11434",
                details={"endpoint": "http://127.0.0.1:11434"},
            )
        elif ollama_exe:
            ver = self._run_command([ollama_exe, "--version"])
            results["ollama"] = DiscoveredComponent(
                id="ollama",
                name="Ollama Local LLM Engine",
                category="ai",
                status=ComponentStatus.INSTALLED,
                version=ver.strip() if ver else None,
                path=ollama_exe,
            )
        else:
            results["ollama"] = DiscoveredComponent(
                id="ollama",
                name="Ollama Local LLM Engine",
                category="ai",
                status=ComponentStatus.MISSING,
            )

        return results

    def _scan_system_capabilities(self) -> dict[str, DiscoveredComponent]:
        """Inspect Windows capabilities, FFmpeg, and monitors."""
        results: dict[str, DiscoveredComponent] = {}

        # Windows Execution State (Kernel32)
        is_windows = os.name == "nt"
        results["windows_power_api"] = DiscoveredComponent(
            id="windows_power_api",
            name="Windows Power & ExecutionState API",
            category="system",
            status=ComponentStatus.INSTALLED if is_windows else ComponentStatus.INCOMPATIBLE,
            details={"platform": sys.platform, "os_name": os.name},
        )

        # FFmpeg
        ffmpeg_exe = shutil.which("ffmpeg")
        if not ffmpeg_exe:
            try:
                from imageio_ffmpeg import get_ffmpeg_exe
                ffmpeg_exe = get_ffmpeg_exe()
            except ImportError:
                ffmpeg_exe = None

        if ffmpeg_exe and Path(ffmpeg_exe).is_file():
            results["ffmpeg"] = DiscoveredComponent(
                id="ffmpeg",
                name="FFmpeg Media Encoder",
                category="system",
                status=ComponentStatus.INSTALLED,
                path=ffmpeg_exe,
            )
        else:
            results["ffmpeg"] = DiscoveredComponent(
                id="ffmpeg",
                name="FFmpeg Media Encoder",
                category="system",
                status=ComponentStatus.MISSING,
            )

        return results

    def _scan_mcp_servers(self) -> dict[str, DiscoveredComponent]:
        """Scan configured local MCP servers from MCPManager."""
        results: dict[str, DiscoveredComponent] = {}
        if not self.mcp_manager:
            return results

        try:
            servers = self.mcp_manager.list_servers()
            for s in servers:
                server_id = f"mcp_{s['id']}"
                is_running = self.mcp_manager.is_running(s["id"]) if hasattr(self.mcp_manager, "is_running") else False
                results[server_id] = DiscoveredComponent(
                    id=server_id,
                    name=f"MCP: {s['name']}",
                    category="mcp",
                    status=ComponentStatus.ACTIVE if is_running else ComponentStatus.INSTALLED,
                    path=s.get("executable"),
                    details={
                        "app_name": s.get("app_name"),
                        "transport": s.get("transport"),
                        "port": s.get("port"),
                    },
                )
        except Exception:
            pass

        return results

    def _scan_installed_applications(self) -> dict[str, DiscoveredComponent]:
        """Scan registry for key desktop applications."""
        results: dict[str, DiscoveredComponent] = {}
        if os.name != "nt":
            return results

        try:
            import winreg

            app_keys = [
                (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", winreg.HKEY_CURRENT_USER),
                (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", winreg.HKEY_LOCAL_MACHINE),
            ]

            sample_apps = {
                "chrome.exe": "Google Chrome",
                "msedge.exe": "Microsoft Edge",
                "firefox.exe": "Mozilla Firefox",
                "notepad++.exe": "Notepad++",
                "blender.exe": "Blender",
                "spotify.exe": "Spotify",
                "discord.exe": "Discord",
            }

            for subkey_path, root in app_keys:
                try:
                    with winreg.OpenKey(root, subkey_path) as key:
                        for exe_name, friendly_name in sample_apps.items():
                            app_id = f"app_{exe_name.split('.')[0]}"
                            if app_id in results:
                                continue
                            try:
                                with winreg.OpenKey(key, exe_name) as app_key:
                                    exe_path = winreg.QueryValue(app_key, None)
                                    if exe_path and Path(exe_path.strip('"')).is_file():
                                        results[app_id] = DiscoveredComponent(
                                            id=app_id,
                                            name=friendly_name,
                                            category="apps",
                                            status=ComponentStatus.INSTALLED,
                                            path=exe_path.strip('"'),
                                        )
                            except OSError:
                                pass
                except OSError:
                    continue

        except Exception:
            pass

        return results

    @staticmethod
    def _run_command(cmd: list[str]) -> str:
        """Run command with short timeout to prevent UI hangs."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return (result.stdout or result.stderr or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _check_http_service(url: str) -> bool:
        """Quick check if a local HTTP service responds within 500ms."""
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status in (200, 404, 405)
        except Exception:
            return False
