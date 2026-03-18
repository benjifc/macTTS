#!/usr/bin/env bash
set -euo pipefail

# ─── MacTTS Uninstaller ─────────────────────────────────────────────────────
# Desinstala MacTTS completamente del sistema
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/uninstall.sh | bash
# ─────────────────────────────────────────────────────────────────────────────

INSTALL_DIR="$HOME/.local/share/mactts"
PLIST_DIR="$HOME/Library/LaunchAgents"
API_LABEL="com.mactts.service"
MENUBAR_LABEL="com.mactts.menubar"
UID_NUM=$(id -u)

info()  { echo "[MacTTS] $*"; }
error() { echo "[MacTTS] ERROR: $*" >&2; }

unload_agent() {
    local label="$1"
    local plist="$2"
    launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || \
        launchctl unload -w "$plist" 2>/dev/null || true
}

# ─── Verificar instalacion ──────────────────────────────────────────────────
if [[ ! -d "$INSTALL_DIR" ]] && [[ ! -f "$PLIST_DIR/$API_LABEL.plist" ]]; then
    info "MacTTS no está instalado."
    exit 0
fi

# ─── Obtener version antes de borrar ─────────────────────────────────────────
VERSION="?"
if [[ -f "$INSTALL_DIR/VERSION" ]]; then
    VERSION=$(cat "$INSTALL_DIR/VERSION" | tr -d '[:space:]')
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Desinstalando MacTTS v$VERSION                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── Detener servicios ───────────────────────────────────────────────────────
info "Deteniendo servicios..."
unload_agent "$API_LABEL" "$PLIST_DIR/$API_LABEL.plist"
unload_agent "$MENUBAR_LABEL" "$PLIST_DIR/$MENUBAR_LABEL.plist"

# ─── Eliminar LaunchAgents ───────────────────────────────────────────────────
info "Eliminando LaunchAgents..."
rm -f "$PLIST_DIR/$API_LABEL.plist"
rm -f "$PLIST_DIR/$MENUBAR_LABEL.plist"

# ─── Eliminar directorio de instalacion ──────────────────────────────────────
info "Eliminando $INSTALL_DIR ..."
rm -rf "$INSTALL_DIR"

# ─── Resumen ─────────────────────────────────────────────────────────────────
echo ""
info "MacTTS v$VERSION desinstalado correctamente."
echo ""
info "Se eliminaron:"
info "  - $INSTALL_DIR"
info "  - $PLIST_DIR/$API_LABEL.plist"
info "  - $PLIST_DIR/$MENUBAR_LABEL.plist"
echo ""
info "Para reinstalar:"
info "  curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash"
echo ""
