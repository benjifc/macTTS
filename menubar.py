import json
import os
import subprocess
import threading
import urllib.request
import webbrowser

import rumps

HEALTH_URL = "http://127.0.0.1:8000/health"
VERSION_URL = "http://127.0.0.1:8000/version"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/benjifc/macTTS/main/VERSION"
DOCS_URL = "http://127.0.0.1:8000/docs"
SERVICE_LABEL = "com.mactts.service"
INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh"

# Rutas a los iconos template (SF Symbols style)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_ACTIVE = os.path.join(_BASE_DIR, "assets", "menubar_active.png")
ICON_MUTED = os.path.join(_BASE_DIR, "assets", "menubar_muted.png")


class MacTTSMenuBar(rumps.App):
    def __init__(self):
        super().__init__("MacTTS", icon=ICON_MUTED, template=True)  # Template = auto dark/light
        self.status_item = rumps.MenuItem("Estado: Verificando...")
        self.version_item = rumps.MenuItem("Versión: ...")
        self.update_item = rumps.MenuItem(
            "Buscar Actualizaciones", callback=self.check_update
        )
        self.menu = [
            self.status_item,
            self.version_item,
            None,
            rumps.MenuItem("Iniciar Servicio", callback=self.start_service),
            rumps.MenuItem("Detener Servicio", callback=self.stop_service),
            None,
            self.update_item,
            rumps.MenuItem("Abrir API Docs", callback=self.open_docs),
        ]
        self._local_version = None

    @rumps.timer(5)
    def check_health(self, _):
        running = False
        try:
            req = urllib.request.urlopen(HEALTH_URL, timeout=2)
            if req.status == 200:
                running = True
        except Exception:
            pass

        if running:
            self.icon = ICON_ACTIVE
            self.template = True   # macOS tinta blanco/negro según modo
            self.status_item.title = "Estado: Activo \u2713"
            self.menu["Iniciar Servicio"].set_callback(None)
            self.menu["Detener Servicio"].set_callback(self.stop_service)
            self._fetch_local_version()
        else:
            self.icon = ICON_MUTED
            self.template = None   # Color fijo rojo, sin tinting de macOS
            self.status_item.title = "Estado: Detenido \u2717"
            self.menu["Iniciar Servicio"].set_callback(self.start_service)
            self.menu["Detener Servicio"].set_callback(None)

    def _fetch_local_version(self):
        if self._local_version:
            return
        try:
            req = urllib.request.urlopen(VERSION_URL, timeout=2)
            data = json.loads(req.read().decode())
            self._local_version = data.get("version", "?")
            self.version_item.title = f"Versión: {self._local_version}"
        except Exception:
            pass

    def check_update(self, _):
        self.update_item.title = "Buscando actualizaciones..."
        self.update_item.set_callback(None)
        thread = threading.Thread(target=self._check_update_async, daemon=True)
        thread.start()

    def _check_update_async(self):
        try:
            req = urllib.request.urlopen(REMOTE_VERSION_URL, timeout=10)
            remote_version = req.read().decode().strip()
        except Exception:
            rumps.notification(
                "MacTTS",
                "Error",
                "No se pudo verificar actualizaciones.",
            )
            self._reset_update_item()
            return

        local = self._local_version or "?"

        if local == remote_version:
            rumps.notification(
                "MacTTS",
                "Sin actualizaciones",
                f"Ya tienes la última versión ({local}).",
            )
            self._reset_update_item()
        else:
            self._reset_update_item()
            self.update_item.title = f"Actualizar a v{remote_version}"
            self.update_item.set_callback(self._run_update)

    def _run_update(self, _):
        self.update_item.title = "Actualizando..."
        self.update_item.set_callback(None)
        thread = threading.Thread(target=self._run_update_async, daemon=True)
        thread.start()

    def _run_update_async(self):
        try:
            result = subprocess.run(
                ["bash", "-c", f"curl -fsSL {INSTALL_SCRIPT_URL} | bash -s -- --update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                rumps.notification(
                    "MacTTS",
                    "Actualización completada",
                    "MacTTS se ha actualizado. Reiniciando...",
                )
            else:
                rumps.notification(
                    "MacTTS",
                    "Error al actualizar",
                    result.stderr[:200] if result.stderr else "Error desconocido",
                )
        except Exception as e:
            rumps.notification("MacTTS", "Error al actualizar", str(e)[:200])
        self._reset_update_item()

    def _reset_update_item(self):
        self.update_item.title = "Buscar Actualizaciones"
        self.update_item.set_callback(self.check_update)
        self._local_version = None

    def start_service(self, _):
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", f"gui/{uid}/{SERVICE_LABEL}"],
            capture_output=True,
        )

    def stop_service(self, _):
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kill", "SIGTERM", f"gui/{uid}/{SERVICE_LABEL}"],
            capture_output=True,
        )

    def open_docs(self, _):
        webbrowser.open(DOCS_URL)


if __name__ == "__main__":
    MacTTSMenuBar().run()
