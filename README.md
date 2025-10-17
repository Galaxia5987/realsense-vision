# Intel RealSense Vision for FRC

Integrate Intel RealSense cameras with FRC robots seamlessly.

> **Note:** Tested only on Orange Pi 5. Other platforms are not guaranteed to work.

## Table of Contents

* [Installation](#installation)
* [Model Training](#model-training)

  * [Dataset](#dataset)
  * [Training and Uploading a Model](#training-and-uploading-a-model)
* [Network Tables](#network-tables)

  * [Format](#format)
  * [Detection Structure](#detection-structure)
* [License](#license)

## Installation

1. **Flash Ubuntu Server Image**

   * Download Ubuntu Server for Orange Pi 5 from this [site](https://joshua-riek.github.io/ubuntu-rockchip-download/boards/orangepi-5.html)(use ubuntu24.04).
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

## License

Licensed under the MIT License. See the [LICENSE](LICENSE) file.
