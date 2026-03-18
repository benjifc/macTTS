#!/usr/bin/env bash
set -euo pipefail

# ─── MacTTS Installer ────────────────────────────────────────────────────────
# Instala MacTTS: REST API para Text-to-Speech en macOS
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --update
#   curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --uninstall
# ──────────────────────────────────────────────────────────────────────────────

REPO_URL="https://github.com/benjifc/macTTS.git"
TARBALL_URL="https://github.com/benjifc/macTTS/archive/refs/heads/main.tar.gz"
VERSION_URL="https://raw.githubusercontent.com/benjifc/macTTS/main/VERSION"
INSTALL_DIR="$HOME/.local/share/mactts"
VENV="$INSTALL_DIR/venv"
PLIST_DIR="$HOME/Library/LaunchAgents"
API_LABEL="com.mactts.service"
MENUBAR_LABEL="com.mactts.menubar"
UID_NUM=$(id -u)

info()  { echo "[MacTTS] $*"; }
error() { echo "[MacTTS] ERROR: $*" >&2; }

# ─── Desinstalar ──────────────────────────────────────────────────────────────
uninstall() {
    info "Desinstalando MacTTS..."
    launchctl bootout "gui/$UID_NUM/$API_LABEL" 2>/dev/null || true
    launchctl bootout "gui/$UID_NUM/$MENUBAR_LABEL" 2>/dev/null || true
    rm -f "$PLIST_DIR/$API_LABEL.plist"
    rm -f "$PLIST_DIR/$MENUBAR_LABEL.plist"
    rm -rf "$INSTALL_DIR"
    info "MacTTS desinstalado correctamente."
    exit 0
}

# ─── Actualizar ──────────────────────────────────────────────────────────────
update() {
    if [[ ! -d "$INSTALL_DIR" ]]; then
        error "MacTTS no está instalado. Ejecuta el instalador primero."
        exit 1
    fi

    # Obtener versión local
    LOCAL_VERSION="desconocida"
    if [[ -f "$INSTALL_DIR/VERSION" ]]; then
        LOCAL_VERSION=$(cat "$INSTALL_DIR/VERSION" | tr -d '[:space:]')
    fi

    # Obtener versión remota
    REMOTE_VERSION=$(curl -fsSL "$VERSION_URL" 2>/dev/null | tr -d '[:space:]') || {
        error "No se pudo verificar la versión remota."
        exit 1
    }

    info "Versión local:  $LOCAL_VERSION"
    info "Versión remota: $REMOTE_VERSION"

    if [[ "$LOCAL_VERSION" == "$REMOTE_VERSION" ]]; then
        info "Ya tienes la última versión ($LOCAL_VERSION). No hay nada que actualizar."
        exit 0
    fi

    info "Actualizando $LOCAL_VERSION → $REMOTE_VERSION ..."

    # Detener servicios
    info "Deteniendo servicios..."
    launchctl bootout "gui/$UID_NUM/$API_LABEL" 2>/dev/null || true
    launchctl bootout "gui/$UID_NUM/$MENUBAR_LABEL" 2>/dev/null || true

    # Actualizar código
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Actualizando desde git..."
        git -C "$INSTALL_DIR" fetch origin main
        git -C "$INSTALL_DIR" reset --hard origin/main
    else
        info "Descargando nueva versión..."
        # Preservar venv y logs
        if [[ -d "$VENV" ]]; then
            mv "$VENV" "/tmp/mactts_venv_backup_$$"
        fi
        if [[ -d "$INSTALL_DIR/logs" ]]; then
            mv "$INSTALL_DIR/logs" "/tmp/mactts_logs_backup_$$"
        fi
        rm -rf "$INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
        curl -fsSL "$TARBALL_URL" | tar xz -C "$INSTALL_DIR" --strip-components=1
        # Restaurar venv y logs
        if [[ -d "/tmp/mactts_venv_backup_$$" ]]; then
            mv "/tmp/mactts_venv_backup_$$" "$VENV"
        fi
        if [[ -d "/tmp/mactts_logs_backup_$$" ]]; then
            mv "/tmp/mactts_logs_backup_$$" "$INSTALL_DIR/logs"
        fi
    fi

    # Actualizar dependencias
    info "Actualizando dependencias..."
    "$VENV/bin/pip" install --upgrade pip --quiet
    "$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

    # Regenerar plists (por si cambiaron los argumentos)
    generate_plists

    # Reiniciar servicios
    info "Reiniciando servicios..."
    launchctl bootstrap "gui/$UID_NUM" "$PLIST_DIR/$API_LABEL.plist"
    launchctl bootstrap "gui/$UID_NUM" "$PLIST_DIR/$MENUBAR_LABEL.plist"

    # Verificar
    sleep 3
    if curl -sf --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
        info "Actualización completada. MacTTS $REMOTE_VERSION está corriendo."
    else
        info "Actualización completada. El servicio está iniciando..."
    fi

    exit 0
}

# ─── Generar plists ──────────────────────────────────────────────────────────
generate_plists() {
    mkdir -p "$PLIST_DIR"

    cat > "$PLIST_DIR/$API_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$API_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/service.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/service.stderr.log</string>
</dict>
</plist>
PLIST

    cat > "$PLIST_DIR/$MENUBAR_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MENUBAR_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV/bin/python3</string>
        <string>$INSTALL_DIR/menubar.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/menubar.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/menubar.stderr.log</string>
</dict>
</plist>
PLIST
}

# ─── Parsear argumentos ─────────────────────────────────────────────────────
case "${1:-}" in
    --uninstall) uninstall ;;
    --update)    update ;;
esac

# ─── Verificaciones ──────────────────────────────────────────────────────────
if [[ "$(uname -s)" != "Darwin" ]]; then
    error "MacTTS solo funciona en macOS."
    exit 1
fi

if ! command -v say &>/dev/null; then
    error "El comando 'say' no se encontró. Verifica tu instalación de macOS."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    error "python3 no encontrado. Instálalo con: brew install python3"
    exit 1
fi

# Verificar Python >= 3.10
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
    error "Se requiere Python >= 3.10 (tienes $PY_VERSION)"
    exit 1
fi

info "Python $PY_VERSION detectado"

# ─── Descargar / Instalar ────────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Actualizando instalación existente..."
    git -C "$INSTALL_DIR" pull --ff-only
elif command -v git &>/dev/null; then
    info "Clonando repositorio..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
    info "git no disponible, descargando tarball..."
    mkdir -p "$INSTALL_DIR"
    curl -fsSL "$TARBALL_URL" | tar xz -C "$INSTALL_DIR" --strip-components=1
fi

# ─── Entorno virtual ─────────────────────────────────────────────────────────
info "Configurando entorno virtual..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# ─── Directorio de logs ──────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/logs"

# ─── Generar LaunchAgents ─────────────────────────────────────────────────────
generate_plists

# ─── Cargar LaunchAgents ──────────────────────────────────────────────────────
info "Cargando servicios..."

# Descargar si ya existen
launchctl bootout "gui/$UID_NUM/$API_LABEL" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM/$MENUBAR_LABEL" 2>/dev/null || true

# Cargar nuevos
launchctl bootstrap "gui/$UID_NUM" "$PLIST_DIR/$API_LABEL.plist"
launchctl bootstrap "gui/$UID_NUM" "$PLIST_DIR/$MENUBAR_LABEL.plist"

# ─── Verificar ───────────────────────────────────────────────────────────────
info "Esperando que el servicio inicie..."
sleep 3

INSTALLED_VERSION="?"
if [[ -f "$INSTALL_DIR/VERSION" ]]; then
    INSTALLED_VERSION=$(cat "$INSTALL_DIR/VERSION" | tr -d '[:space:]')
fi

if curl -sf --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    info "MacTTS v$INSTALLED_VERSION está corriendo correctamente!"
else
    info "El servicio aún está iniciando. Revisa los logs en: $INSTALL_DIR/logs/"
fi

# ─── Resumen ─────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            MacTTS v$INSTALLED_VERSION instalado con éxito                  ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  API:        http://127.0.0.1:8000                          ║"
echo "║  Docs:       http://127.0.0.1:8000/docs                     ║"
echo "║  Health:     http://127.0.0.1:8000/health                    ║"
echo "║                                                              ║"
echo "║  Instalado en: ~/.local/share/mactts                         ║"
echo "║  Logs:         ~/.local/share/mactts/logs/                   ║"
echo "║                                                              ║"
echo "║  El icono 🔊 aparece en la barra de menú                   ║"
echo "║  El servicio se inicia automáticamente al iniciar sesión     ║"
echo "║                                                              ║"
echo "║  Actualizar:                                                 ║"
echo "║    curl -fsSL https://raw.githubusercontent.com/             ║"
echo "║      benjifc/macTTS/main/install.sh | bash -s -- --update    ║"
echo "║                                                              ║"
echo "║  Desinstalar:                                                ║"
echo "║    curl -fsSL https://raw.githubusercontent.com/             ║"
echo "║      benjifc/macTTS/main/install.sh | bash -s -- --uninstall ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
