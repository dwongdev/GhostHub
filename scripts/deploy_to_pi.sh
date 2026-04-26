#!/usr/bin/env bash
# GhostHub Deployment System
# ==========================================

set -uo pipefail

# --- DEFAULTS ---
PI_HOST="ghosthub.local"
PI_USER="ghost"
TARGET_DIR="/home/ghost/ghosthub"
KEY_FILE=""
PASSWORD=""
SKIP_UPLOAD=false
FULL_INSTALL=false
LOCAL_ONLY=false
UPDATE=false
GOLDEN=false

# Capture argument count for interactive check
ORIG_ARG_COUNT=$#

# Visuals (Using standard bash compatibility)
CLR_RESET='\033[0m'; CLR_BOLD='\033[1m'; CLR_CYAN='\033[0;36m'; CLR_GREEN='\033[0;32m'; CLR_YELLOW='\033[1;33m'; CLR_RED='\033[0;31m'; CLR_BLUE='\033[0;34m'; CLR_MAGENTA='\033[0;35m'; CLR_GRAY='\033[0;90m'; CLR_WHITE='\033[1;37m'

BANNER="${CLR_CYAN}${CLR_BOLD}
   ______ __                      __     ____               __   
  / ____// /_   ____   _____ / /_   / __ \\ ____ _ _____ / /__ 
 / / __ / __ \\ / __ \\ / ___// __/  / /_/ // __ \`// ___// //_/ 
/ /_/ // / / // /_/ /(__  )/ /_   / ____// /_/ // /__ / ,<    
\\____//_/ /_/ \\____//____/ \\__/  /_/     \\__,_/ \\___//_/|_|   
                                                               
${CLR_MAGENTA}                    GHOSTHUB DEPLOYMENT v3.0${CLR_RESET}"

write_status()  { echo -e "${CLR_BLUE}[*]${CLR_RESET} $1"; }
write_success() { echo -e "${CLR_GREEN}[+]${CLR_RESET} $1"; }
write_warn()    { echo -e "${CLR_YELLOW}[!]${CLR_RESET} $1"; }
write_err()     { echo -e "${CLR_RED}[X]${CLR_RESET} $1"; }
write_phase()   { 
    # Portable uppercase conversion (macOS bash 3.2 compatible)
    local phase_name=$(echo "$1" | tr '[:lower:]' '[:upper:]')
    echo -e "\n${CLR_BOLD}${CLR_CYAN}--- $phase_name ---${CLR_RESET}"
}

print_fresh_pi_help() {
    cat <<EOF

Fresh Raspberry Pi OS Lite setup expected by this deploy script:
  Image:    2022-01-28-raspios-bullseye-armhf-lite
  Tool:     Raspberry Pi Imager v1.8.5
  Hostname: ghosthub
  Username: ghost
  SSH:      enabled

In Raspberry Pi Imager v1.8.5, open advanced options before writing the card,
set hostname to ghosthub, create the ghost user, enable SSH, and set a password.
Then boot the Pi and try:
  ssh ghost@ghosthub.local

If mDNS is not resolving, use the Pi IP address:
  $0 --host <pi-ip-address>

If SSH reports a host key warning after reflashing the Pi, clear the old key:
  ssh-keygen -R ghosthub.local
  ssh-keygen -R <pi-ip-address>

EOF
}

get_source_version() {
    sed -n 's/^VERSION = "\([0-9][0-9.]*\)"$/\1/p' "$PROJECT_DIR/app/version.py" | head -n 1
}

get_zip_version() {
    local zip_path="$1"
    unzip -p "$zip_path" Ghosthub_pi_github/install_ghosthub.sh 2>/dev/null \
        | sed -n 's/^GHOSTHUB_VERSION="\([0-9][0-9.]*\)"$/\1/p' \
        | head -n 1
}

find_python39() {
    if command -v python3.9 >/dev/null 2>&1; then
        command -v python3.9
        return 0
    fi
    if command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 9) else 1)' 2>/dev/null; then
        command -v python
        return 0
    fi
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 9) else 1)' 2>/dev/null; then
        command -v python3
        return 0
    fi
    return 1
}

print_python39_help() {
    cat <<'EOF'

Python 3.9 was not found.

Install Python 3.9, then rerun this deploy script.

macOS with Homebrew:
  brew install python@3.9

Ubuntu/Debian:
  sudo apt update
  sudo apt install python3.9 python3.9-venv python3.9-dev

Windows:
  Install Python 3.9 from https://www.python.org/downloads/release/python-3913/
  Then rerun scripts\deploy_to_pi.ps1 from PowerShell.

EOF
}

ensure_local_build_env() {
    write_phase "Local Build Environment"

    local py39
    if ! py39="$(find_python39)"; then
        print_python39_help
        exit 1
    fi
    write_status "Using Python 3.9: $py39"

    if [ ! -x "$LOCAL_PYTHON" ]; then
        write_status "Creating virtualenv..."
        "$py39" -m venv "$PROJECT_DIR/venv"
    fi

    if [ ! -x "$LOCAL_PYTHON" ]; then
        write_err "Virtualenv was not created correctly: $LOCAL_PYTHON"
        exit 1
    fi

    write_status "Installing Python dependencies..."
    "$LOCAL_PYTHON" -m pip install --upgrade pip setuptools wheel
    "$LOCAL_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt"

    if ! command -v npm >/dev/null 2>&1; then
        write_err "npm was not found. Install Node.js/npm, then rerun this deploy script."
        write_warn "Recommended: install the current Node.js LTS from https://nodejs.org/"
        exit 1
    fi

    if [ ! -d "$PROJECT_DIR/static/js/node_modules" ] || [ ! -x "$PROJECT_DIR/static/js/node_modules/.bin/vitest" ]; then
        write_status "Installing JavaScript dependencies..."
        (cd "$PROJECT_DIR/static/js" && npm install)
    else
        write_status "JavaScript dependencies already installed."
    fi
}

# --- ARGUMENT PARSING ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -H|--host)       PI_HOST="$2";      shift 2 ;;
        -u|--user)       PI_USER="$2";      shift 2 ;;
        -k|--key)        KEY_FILE="$2";     shift 2 ;;
        -d|--dir)        TARGET_DIR="$2";   shift 2 ;;
        -p|--password)   PASSWORD="$2";     shift 2 ;;
        --skip-upload)   SKIP_UPLOAD=true;  shift ;;
        --full-install)  FULL_INSTALL=true; shift ;;
        --local-only)    LOCAL_ONLY=true;   shift ;; # compatibility; deploy_to_pi is local-source-only now
        --update)        UPDATE=true;       shift ;;
        --golden)        GOLDEN=true;       shift ;;
        *) write_err "Unknown option: $1"; exit 1 ;;
    esac
done

# --- INTERACTIVE MENU (Only if no flags provided) ---
if [ $ORIG_ARG_COUNT -eq 0 ]; then
    echo -e "$BANNER"
    echo -e "${CLR_BOLD}${CLR_WHITE}TARGET:${CLR_RESET} ${CLR_CYAN}${PI_USER}@${PI_HOST}${CLR_RESET}\n"
    
    echo -e "${CLR_BOLD}${CLR_CYAN}CHOOSE DEPLOYMENT MODE:${CLR_RESET}"
    echo -e "  [1] ${CLR_WHITE}Standard${CLR_RESET}   (Fresh local install from this repo)"
    echo -e "  [2] ${CLR_WHITE}Update${CLR_RESET}     (Local update, preserve /instance and /venv)"
    echo -e "  [3] ${CLR_WHITE}Image Prep${CLR_RESET} (Fresh local install + clear state + power off)"
    echo -e "  [4] ${CLR_WHITE}Abort${CLR_RESET}"
    echo ""
    
    # Prompt before doing ANYTHING
    read -p "$(echo -e ${CLR_BOLD}${CLR_CYAN}"Selection [1]: "${CLR_RESET})" choice
    
    case ${choice:-1} in
        1) ;;
        2) UPDATE=true ;;
        3) GOLDEN=true ;;
        4) exit 0 ;;
        *) write_err "Invalid selection"; exit 1 ;;
    esac
fi

# deploy_to_pi always installs from the zip it builds and uploads to /tmp.
# GitHub Releases are used by the public installer/admin update flow, not this local deploy tool.
LOCAL_ONLY=true
if $GOLDEN; then LOCAL_ONLY=true; fi

# --- ENV PREP ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOCAL_PYTHON="$PROJECT_DIR/venv/bin/python"

echo -e "$BANNER"
write_status "Initializing GhostHub deployment..."

# SSH Check & Password Prompt (Safe for macOS)
if [ -z "$KEY_FILE" ] && [ -z "$PASSWORD" ]; then
    if ! ssh -q -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no "${PI_USER}@${PI_HOST}" "echo ok" &>/dev/null; then
        write_status "No SSH keys found. Authenticating..."
        read -rsp "Enter Pi Password: " PASSWORD; echo ""
    fi
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=10)
if [ -n "$KEY_FILE" ] && [ -f "$KEY_FILE" ]; then SSH_OPTS+=(-i "$KEY_FILE"); fi

# SSH Wrappers (with sshpass guard)
run_ssh() {
    if [ -n "$PASSWORD" ]; then
        if ! command -v sshpass &>/dev/null; then
            write_err "sshpass required for password authentication. Install with 'brew install hudochenkov/sshpass/sshpass'"
            exit 1
        fi
        sshpass -p "$PASSWORD" ssh "${SSH_OPTS[@]}" "${PI_USER}@${PI_HOST}" "$@"
    else
        ssh "${SSH_OPTS[@]}" "${PI_USER}@${PI_HOST}" "$@"
    fi
}
run_ssh_tty() {
    if [ -n "$PASSWORD" ]; then
        sshpass -p "$PASSWORD" ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_HOST}" "$@"
    else
        ssh -t "${SSH_OPTS[@]}" "${PI_USER}@${PI_HOST}" "$@"
    fi
}
run_scp() {
    if [ -n "$PASSWORD" ]; then
        sshpass -p "$PASSWORD" scp "${SSH_OPTS[@]}" "$1" "${PI_USER}@${PI_HOST}:$2"
    else
        scp "${SSH_OPTS[@]}" "$1" "${PI_USER}@${PI_HOST}:$2"
    fi
}

# --- DEPLOYMENT PHASES ---

# 1. Local Build
if ! $SKIP_UPLOAD; then
    ensure_local_build_env
    write_phase "Building Project"
    "$LOCAL_PYTHON" "$PROJECT_DIR/scripts/ghostpack.py" --zip
    if [ $? -ne 0 ]; then write_err "Ghostpack build failed"; exit 1; fi
fi

# 2. Connection Audit
write_phase "Connection Audit"
if ! run_ssh "echo connected" 2>&1 | grep -q "connected"; then
    print_fresh_pi_help
    write_err "CONNECTION FAILURE: $PI_HOST unreachable"
    exit 1
fi

# 3. Transmission & Extraction
if ! $SKIP_UPLOAD; then
    write_phase "Data Transmission"
    DIST_ZIP="$PROJECT_DIR/dist/Ghosthub_pi_github.zip"
    ROOT_ZIP="$PROJECT_DIR/Ghosthub_pi_github.zip"
    SOURCE_VERSION="$(get_source_version)"

    if [ ! -f "$DIST_ZIP" ]; then
        write_err "Expected fresh build artifact was not created:"
        write_err "  $DIST_ZIP"
        if [ -f "$ROOT_ZIP" ]; then
            write_warn "Legacy root zip exists but will NOT be used:"
            write_warn "  $ROOT_ZIP"
        fi
        exit 1
    fi

    ZIP_VERSION="$(get_zip_version "$DIST_ZIP")"
    if [ -z "$ZIP_VERSION" ]; then
        write_err "Could not read GHOSTHUB_VERSION from built artifact:"
        write_err "  $DIST_ZIP"
        exit 1
    fi

    if [ -n "$SOURCE_VERSION" ] && [ "$ZIP_VERSION" != "$SOURCE_VERSION" ]; then
        write_err "Built zip version mismatch:"
        write_err "  source version: $SOURCE_VERSION"
        write_err "  zip version:    $ZIP_VERSION"
        exit 1
    fi

    if [ -f "$ROOT_ZIP" ]; then
        ROOT_ZIP_VERSION="$(get_zip_version "$ROOT_ZIP")"
        if [ -n "$ROOT_ZIP_VERSION" ] && [ "$ROOT_ZIP_VERSION" != "$ZIP_VERSION" ]; then
            write_warn "Ignoring stale legacy root zip (v$ROOT_ZIP_VERSION) in favor of dist artifact (v$ZIP_VERSION)"
        fi
    fi

    write_status "Using zip artifact: $DIST_ZIP (v$ZIP_VERSION)"
    if ! run_scp "$DIST_ZIP" "/tmp/ghosthub_deploy.zip"; then
        write_err "Upload failed"
        exit 1
    fi
    
    write_phase "Remote Extraction"
    if $UPDATE; then
        EXTRACT_CMD="
set -e
sudo mkdir -p $TARGET_DIR
sudo chown -R $PI_USER:$PI_USER $TARGET_DIR
cd $TARGET_DIR
rm -rf .deploy_stage
mkdir -p .deploy_stage
unzip -oq /tmp/ghosthub_deploy.zip \
    Ghosthub_pi_github/install_ghosthub.sh \
    -d .deploy_stage
mv .deploy_stage/Ghosthub_pi_github/install_ghosthub.sh .
rm -rf .deploy_stage
chmod +x install_ghosthub.sh"
    else
        EXTRACT_CMD="set -e && sudo rm -rf $TARGET_DIR && sudo mkdir -p $TARGET_DIR && sudo chown -R $PI_USER:$PI_USER $TARGET_DIR && cd $TARGET_DIR && unzip -o /tmp/ghosthub_deploy.zip -d . && if [ -d Ghosthub_pi_github ]; then shopt -s dotglob nullglob; for path in Ghosthub_pi_github/*; do mv \"\$path\" .; done; shopt -u dotglob nullglob; rm -rf Ghosthub_pi_github; fi && chmod +x install_ghosthub.sh"
    fi
    if ! run_ssh "$EXTRACT_CMD"; then
        write_err "Remote extraction failed"
        exit 1
    fi
fi

# 4. System Installation
write_phase "System Installation"
INSTALL_FLAGS="--no-self-update"
[[ $LOCAL_ONLY == true ]] && INSTALL_FLAGS="$INSTALL_FLAGS --local-only"
[[ $UPDATE == true ]] && INSTALL_FLAGS="$INSTALL_FLAGS --update"
[[ $FULL_INSTALL == true ]] && INSTALL_FLAGS="$INSTALL_FLAGS --full-install"

INSTALL_CMD="cd $TARGET_DIR && sudo bash install_ghosthub.sh $INSTALL_FLAGS"
run_ssh_tty "$INSTALL_CMD"
EXIT_CODE=$?

# 5. Cleanup / Finalize
if [ $EXIT_CODE -eq 0 ]; then
    write_success "Deploy Successful"
    if $GOLDEN; then
        write_phase "Image Prep"
        run_ssh "sudo systemctl stop ghosthub ghosthub-kiosk 2>/dev/null || true; sudo rm -rf $TARGET_DIR/instance/* 2>/dev/null || true; rm -f /tmp/ghosthub_deploy.zip; sudo shutdown -h now"
        write_success "Pi is powering off"
    fi
else
    write_err "Deployment Failed (Code $EXIT_CODE)"
fi
echo ""
