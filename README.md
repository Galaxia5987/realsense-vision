# Intel RealSense Vision for FRC

Integrate Intel RealSense cameras with FRC robots seamlessly.

> **Note:** Tested only on Orange Pi 5, and Orange Pi 5 Pro. Other platforms are not guaranteed to work.

## Table of Contents

* [Installation](#installation)
* [Model Training](#model-training)

  * [Dataset](#dataset)
  * [Training and Uploading a Model](#training-and-uploading-a-model)
* [Network Tables](#network-tables)
* [Setting a static IP Address](#setting-a-static-ip-address)
* [License](#license)

## Installation

1. **Flash Ubuntu Server Image**

   * Download Ubuntu Server for Orange Pi 5 (or Pro) from this [site](https://joshua-riek.github.io/ubuntu-rockchip-download/boards/orangepi-5.html)(use ubuntu24.04 only).
   * Flash it to a microSD card using [Balena Etcher](https://www.balena.io/etcher/).
   * Insert the card into the Orange Pi 5 and power it on.

2. **Run the Installer**

   * SSH into the Orange Pi 5 or use a terminal.
   * Run:

     ```bash
     wget https://raw.githubusercontent.com/Galaxia5987/realsense-vision/refs/heads/main/install.sh
     chmod +x install.sh
     ./install.sh
     ```
   * The installer will prompt you for configuration and ask whether to install PhotonVision aswell.

3. **Access the Dashboard**

   * Visit `http://<orange-pi-ip>:5000` in your browser.

## Model Training

### Dataset

We recommend [Roboflow](https://roboflow.com/) for image collection, annotation, and export.

1. **Collect Images**

   * Use the `image_capture.py` script from [realsense-tools](https://github.com/Galaxia5987/realsense-tools) to capture images.
   * Upload them to a Roboflow project.

2. **Annotate**

   * Label objects using Roboflow's tools.

3. **Save the Dataset**

   * Save your annotated dataset and its version for later use.

4. **Get an API Key**

   * Obtain your key [here](https://app.roboflow.com/settings/api) to use with the Kaggle training notebook.

See [Roboflow Documentation](https://docs.roboflow.com/) for more help.

### Training and Uploading a Model

Use this [Kaggle Notebook](https://www.kaggle.com/code/adarwas/yolov11-traning) for training.

1. **Train**

   * Train a YOLOv11 model using the notebook.
   * Download the `.pt` (PyTorch) model after training.

2. **Upload**

   * Open the dashboard and go to the "Model Upload" section.
   * Upload your `.pt` file.
   * Do not refresh the page during upload or conversion.

3. **Conversion**

   * The dashboard will convert the model to RKNN format automatically.

4. **Configure Detection**

   * Set the pipeline type to `detection` and define the model path in `args` (e.g. `./uploads/best_rknn_model`).
   * Update this via `config.yaml` or the dashboard config page.

## Network Tables

The `poses` topic in NetworkTables is a Pose3d struct array representing detected objects.

You can configure the server address and table name via `config.yaml` or the dashboard.

## Calibration

The calibration proccess is not difficult, but it contains many steps and different tool paths.

### Self Calibrations (Built into `Realsense Viewer`)

Realsense cameras have built-in self calibration, which are easy to perform and has good results.

You'll need to do the `On-Chip Calibration`, `Focal Length Calibration`, and `Tare Calibration` using the `RealsenseViewer` app.

Refer to [Realsense Calibration Docs](https://dev.realsenseai.com/docs/self-calibration-for-depth-cameras) for detailed steps.

### Dynamic Calibration

This step is a bit more complicated.

You'll need to use the [`D400 Dynamic Calibration Tool`](https://dev.realsenseai.com/docs/intel-realsensetm-d400-series-calibration-tools-user-guide), and print a chessboard-like target to calibrate with([Download Here](https://realsenseai.com/download/18533/)).

Refer to [Realsense Dynamic Calibration Docs](https://dev.realsenseai.com/docs/intel-realsensetm-d400-series-calibration-tools-user-guide) for detailed steps.

### IMU Calibration

This step calibrates the IMU(Inertial measurement unit) of the camera.
In this step, You'll need to run the IMU calibration python script.

Refer to []


## Setting a static IP Address

Run this to disable `cloud-init`:
```
sudo bash -c 'echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg'
```
You need to configure `/etc/netplan/50-cloud-init.yaml` like that:
```
network:
  version: 2
  renderer: networkd
  ethernets:
    enP4p65s0:
      dhcp4: false
      dhcp6: false
      addresses:
      - 10.59.87.12/24
      routes:
      - to: default
        via: 10.59.87.4
        metric: 100
      nameservers:
       addresses: [8.8.8.8,8.8.4.4]
  wifis:
    wlan0:
      dhcp4: true
      access-points:
        "Reali Beit Biram": {}
      dhcp4-overrides:
        route-metric: 75


```
Edit `addresses` to change the ip.
Edit `enP4p65s0` and `wlan0` with the right interface after running `ip link`.

Run `sudo netplan apply` to apply the changes without the need of a reboot.

In case something goes wrong, this is the default config:
```
network:
  version: 2
  ethernets:
    zz-all-en:
      match:
        name: "en*"
      dhcp4: true
      optional: true
    zz-all-eth:
      match:
        name: "eth*"
      dhcp4: true
      optional: true
```

## License

Licensed under the MIT License. See the [LICENSE](LICENSE) file.
