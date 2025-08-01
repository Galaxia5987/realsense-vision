#!/bin/bash

# Define color codes
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RESET="\033[0m"

log_info() {
    echo -e "${CYAN}[INFO]${RESET} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${RESET} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${RESET} $1"
}

log_info "Checking for main.py..."
if [ ! -f "main.py" ]; then
    log_info "main.py not found, cloning repository..."
    git clone https://github.com/Galaxia5987/realsense-vision || { log_error "Git clone failed"; exit 1; }
    cd realsense-vision || { log_error "Failed to cd into repo"; exit 1; }
else
    log_info "main.py found, assuming correct directory"
fi

log_info "Updating apt..."
sudo apt update

log_info "Installing cmake..."
sudo apt install -y cmake

log_info "Installing build-essential..."
sudo apt install -y build-essential

log_info "Adding deadsnakes PPA..."
sudo add-apt-repository -y ppa:deadsnakes/ppa

log_info "Updating apt after adding PPA..."
sudo apt update

log_info "Installing Python 3.10 and dependencies..."
sudo apt install -y python3.10 python3.10-venv python3.10-dev

log_info "Installing libgl1..."
sudo apt install -y libgl1

log_info "Creating Python virtual environment..."
python3.10 -m venv .venv

log_info "Activating virtual environment..."
source .venv/bin/activate

log_info "Installing uv..."
pip install uv

log_info "Syncing dependencies with uv..."
uv sync && log_success "Environment setup complete!" || log_error "uv sync failed"

echo
read -rp "$(echo -e "${YELLOW}Do you want to install PhotonVision? (y/n): ${RESET}")" install_photon
if [[ "$install_photon" =~ ^[Yy]$ ]]; then
    log_info "Installing PhotonVision..."

    log_info "Installing Java (OpenJDK 17)..."
    sudo apt install -y openjdk-17-jre || { log_error "Failed to install Java"; exit 1; }

    mkdir -p ~/photonvision
    cd ~/photonvision || exit 1

    log_info "Downloading PhotonVision..."
    wget https://github.com/PhotonVision/photonvision/releases/download/v2025.3.2/photonvision-v2025.3.2-linuxarm64.jar -O photonvision.jar || { log_error "Failed to download PhotonVision"; exit 1; }

    log_info "Creating PhotonVision service..."
        sudo tee /etc/systemd/system/photonvision.service > /dev/null <<EOF
[Unit]
Description=PhotonVision
After=network.target

[Service]
ExecStart=/usr/bin/java -jar /home/$USER/photonvision/photonvision.jar
User=$USER
WorkingDirectory=/home/$USER/photonvision
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reexec
    sudo systemctl daemon-reload
    sudo systemctl enable photonvision.service
    sudo systemctl start photonvision.service

    log_success "PhotonVision installation completed!"
else
    log_info "Skipping PhotonVision installation."
fi