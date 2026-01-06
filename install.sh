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

echo
while read -t 0; do read -n 1 -s; done
read -rp "$(echo -e "${YELLOW}Do you want to install realsense-vision? (y/n): ${RESET}")" install_realsense
if [[ "$install_realsense" =~ ^[Yy]$ ]]; then

log_info "Checking for main.py..."
if [ ! -f "main.py" ]; then
    log_info "main.py not found, cloning repository..."
    git clone https://github.com/Galaxia5987/realsense-vision 1>/dev/null || { log_error "Git clone failed"; exit 1; }
    cd realsense-vision || { log_error "Failed to cd into repo"; exit 1; }
else
    log_info "main.py found, assuming correct directory"
fi

echo
while read -t 0; do read -n 1 -s; done

echo -e "${YELLOW}Select your board:${RESET}"
echo -e "${CYAN}1) Rubik Pi${RESET}"
echo -e "${CYAN}2) Orange Pi${RESET}"
read -rp "$(echo -e "${YELLOW}Enter choice (1 or 2): ${RESET}")" BOARD_CHOICE

case "$BOARD_CHOICE" in
    1)
        BOARD_TYPE="rubik_pi"
        log_info "Using Rubik Pi configuration"
        ;;
    2)
        BOARD_TYPE="orange_pi"
        log_info "Using Orange Pi configuration"
        ;;
    *)
        log_error "Invalid selection, exiting"
        exit 1
        ;;
esac

log_info "Updating apt..."
sudo apt update 1>/dev/null || log_error "apt update failed"

log_info "Installing cmake..."
sudo apt install -y cmake 1>/dev/null || log_error "Failed to install cmake"

log_info "Installing build-essential..."
sudo apt install -y build-essential 1>/dev/null || log_error "Failed to install build-essential"

log_info "Installing tools..."
sudo apt install cmake build-essential python3-dev libllvm15 clang 1>/dev/null || log_error "Failed to install tools"

if [ "$BOARD_TYPE" = "orange_pi" ]; then
    log_info "Installing librknn shared object..."
    sudo wget -P /usr/lib/ https://github.com/airockchip/rknn-toolkit2/raw/refs/heads/master/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so
fi


log_info "Adding deadsnakes PPA..."
sudo add-apt-repository -y ppa:deadsnakes/ppa 1>/dev/null || log_error "Failed to add PPA"

if [ "$BOARD_TYPE" = "orange_pi" ]; then
    log_info "Installing NetworkManager"
    sudo apt install network-manager -y || log_error "Failed to install NetworkManager"
    sudo systemctl enable NetworkManager || log_error "Failed to enable NetworkManager"
    sudo systemctl start NetworkManager || log_error "Failed to start NetworkManager"
fi


log_info "Updating apt after adding PPA..."
sudo apt update 1>/dev/null || log_error "Second apt update failed"

log_info "Installing Python 3.10 and dependencies..."
sudo apt install -y python3.10 python3.10-venv python3.10-dev 1>/dev/null || log_error "Failed to install Python 3.10"

log_info "Installing libgl1..."
sudo apt install -y libgl1 1>/dev/null || log_error "Failed to install libgl1"

log_info "Creating Python virtual environment..."
python3.10 -m venv .venv 1>/dev/null || log_error "Failed to create venv"

log_info "Activating virtual environment..."
source .venv/bin/activate || { log_error "Failed to activate venv"; exit 1; }

log_info "Installing uv..."
pip install uv 1>/dev/null || { log_error "Failed to install uv"; exit 1; }

log_info "Syncing dependencies with uv..."
uv sync 1>/dev/null && log_success "Environment setup complete!" || log_error "uv sync failed"

if [ "$BOARD_TYPE" = "rubik_pi" ]; then
    log_info "Installing shitty Qualcomm wrapper stuff."
    log_info "Hold on while we shit your computer."
    wget https://github.com/bazelbuild/bazelisk/releases/download/v1.27.0/bazelisk-arm64.deb 1> /dev/null || log_error "Failed to get bazelisk from github"
    sudo dpkg -i bazelisk-arm64.deb || log_error "Failed to install bazelisk"
    sudo apt install -y libopencv-dev 1> /dev/null || log_error "Failed to install OpenCV"
    uv pip install pybind11 1> /dev/null || log_error "Failed to install pybind11 using pip"
    cd RubikPiWrapper
    python3 setup.py install || log_error "Failed to build Tensorflow and other shit(try running this again, probably a RAM thing)"
    cd ..
fi

echo
while read -t 0; do read -n 1 -s; done

read -rp "$(echo -e "${YELLOW}Do you want to create a systemd service for realsense-vision? (y/n): ${RESET}")" install_rs_service
if [[ "$install_rs_service" =~ ^[Yy]$ ]]; then
    log_info "Creating realsense-vision systemd service..."

    SERVICE_PATH="/etc/systemd/system/realsense-vision.service"
    APP_DIR="$(pwd)"
    PYTHON_PATH="$APP_DIR/.venv/bin/python3"

    sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=Realsense Vision App
After=network.target

[Service]
ExecStart=$PYTHON_PATH $APP_DIR/main.py
WorkingDirectory=$APP_DIR
Restart=always
RestartSec=5
User=$USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    log_info "Reloading systemd and enabling realsense-vision service..."
    sudo systemctl daemon-reexec
    sudo systemctl daemon-reload
    sudo systemctl enable realsense-vision.service
    sudo systemctl start realsense-vision.service

    log_success "realsense-vision service created and started!"
    log_info "You can check the service status with: sudo systemctl status realsense-vision.service"

    echo
    while read -t 0; do read -n 1 -s; done

    echo -e "${YELLOW}This is required if you want to restart the realsense-vision service from the UI.${RESET}"
    read -rp "$(echo -e "${YELLOW}Allow restarting realsense-vision without sudo password? (y/n): ${RESET}")" allow_nopasswd_restart
    if [[ "$allow_nopasswd_restart" =~ ^[Yy]$ ]]; then
        log_info "Configuring sudoers to allow passwordless restart..."

        SUDOERS_FILE="/etc/sudoers.d/realsense-vision"
        SERVICE_NAME="realsense-vision"
        USERNAME="$USER"

        echo "$USERNAME ALL=NOPASSWD: /bin/systemctl restart $SERVICE_NAME.service" | sudo tee "$SUDOERS_FILE" > /dev/null
        sudo chmod 440 "$SUDOERS_FILE"

        log_success "Passwordless restart allowed for $SERVICE_NAME."
    else
        log_info "Skipping sudoers modification for realsense-vision."
    fi

else
    log_info "Skipping realsense-vision systemd service creation."
fi

else
    log_info "Skipping realsense-vision installation."
fi

echo
while read -t 0; do read -n 1 -s; done
read -rp "$(echo -e "${YELLOW}Do you want to install PhotonVision? (y/n): ${RESET}")" install_photon
if [[ "$install_photon" =~ ^[Yy]$ ]]; then
    log_info "Installing PhotonVision..."

    log_info "Install Mr. Cal dependency..."
    sudo apt install -y libsuitesparse-dev
    
    log_info "Installing Java (OpenJDK 17)..."
    sudo apt install -y openjdk-17-jre 1>/dev/null || { log_error "Failed to install Java"; exit 1; }

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
    sudo systemctl enable photonvision.service 1>/dev/null || log_error "Failed to enable PhotonVision service"
    sudo systemctl start photonvision.service || log_error "Failed to start PhotonVision service"

    log_success "PhotonVision installation completed!"
else
    log_info "Skipping PhotonVision installation."
fi
