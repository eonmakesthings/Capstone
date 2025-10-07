# 💡 Warehouse Sorting Robot Using a Single Luminaire

### Capstone Research Project — Colorado School of Mines  
**Advised by Dr. Sihua Shao**  
*By: Noe Avila, Chase, and Nils*

---

## 🧠 Overview

This repository contains the firmware, ROS 2 nodes, and communication scripts developed for the **Warehouse Sorting Robot Using Visible Light Communication (VLC)** Capstone project.

The system enables a **TurtleBot 4** robot to receive and execute motion commands transmitted via **visible light**, removing the need for RF or Wi-Fi infrastructure.  
Communication between a fixed LED luminaire and the robot’s onboard receiver (BeagleBone Black + OpenVLC cape) is achieved through **VLC-to-UDP relaying**, bridging light-based signaling into ROS 2 motion commands.

---

## ⚙️ System Architecture

```
        ┌──────────────────────────────┐
        │     LED Luminaire (TX)       │
        │ Encodes Commands in Light    │
        └────────────┬─────────────────┘
                     │ Visible Light
                     ▼
        ┌──────────────────────────────┐
        │  BeagleBone Black (RX)       │
        │  OpenVLC Firmware + Driver   │
        │  Converts VLC → UDP Packets  │
        └────────────┬─────────────────┘
                     │ Ethernet (UDP)
                     ▼
        ┌──────────────────────────────┐
        │    UDP Relay / BeagleBone    │
        │ Receives & Relays Packets    │
        │  <START>command<END> format  │
        └────────────┬─────────────────┘
                     │ Ethernet (UDP)
                     ▼
        ┌──────────────────────────────┐
        │   TurtleBot 4 (ROS 2 Node)   │
        │ turtlebot_ethernet_bridge.py │
        │ Parses Command → ROS Action  │
        └────────────┬─────────────────┘
                     │ ROS 2 Actions
                     ▼
        ┌──────────────────────────────┐
        │   Create 3 Base Controller   │
        │ Executes Drive/Rotate Motion │
        └──────────────────────────────┘
```

---

## 🧩 Core Components

### 1. **OpenVLC Firmware and Driver Scripts**
Located in:
```
/OpenVLC/Latest_Version/Driver
/OpenVLC/Latest_Version/PRU/RX
```
- `load_test.sh` and `deploy.sh` configure the BeagleBone’s PRU cores.  
- Initializes VLC driver modules and deploys firmware for the RX/TX chain.

---

### 2. **UDP Communication Bridge**
- **Files:** `udp_relay.py`, `vlc_receiver.py`
- Handles light-to-Ethernet packet translation.
- Uses a framed message protocol:  
  ```
  <START>drive forward 0.5 speed 0.25<END>
  ```
- Buffers incoming messages, verifies completeness, and relays them to the TurtleBot via UDP.

---

### 3. **TurtleBot 4 ROS 2 Node**
- **File:** `turtlebot_ethernet_bridge.py`
- A ROS 2 Python node that receives UDP messages, parses them, and converts them to:
  - `/drive_distance` and `/rotate_angle` **ROS 2 Actions**, or  
  - `/cmd_vel` **velocity commands**
- Example commands:
  ```
  drive forward 0.5 speed 0.25
  rotate clockwise 45
  vel 0.2 -0.3
  ```

---

### 4. **Test & Utility Scripts**
- `udp_sender.py` — Manual testing of the UDP relay.  
- `simple_drive.py` — Minimal ROS 2 test node that moves forward 0.25 m at 0.25 m/s.  
- `network_test.sh` — Quick diagnostic to verify Ethernet and UDP connectivity.

---

## 🧰 Dependencies

- **Hardware**
  - BeagleBone Black Rev C + OpenVLC Cape  
  - TurtleBot 4 (Standard or Lite)  
  - LED Array Luminaire (TX Unit)
- **Software**
  - Debian 11 (armhf) + OpenVLC driver v1.3+  
  - ROS 2 Jazzy or Humble  
  - Python 3.10+  
  - iRobot Create 3 ROS 2 Packages (`irobot_create_msgs`)

---

## 🚀 Setup & Deployment

### 1. **Deploy OpenVLC Firmware**
```bash
cd /home/debian/OpenVLC/Latest_Version/Driver
sudo ./load_test.sh
cd /home/debian/OpenVLC/Latest_Version/PRU/RX
sudo ./deploy.sh
```

### 2. **Run the UDP Relay (BeagleBone)**
```bash
python3 udp_relay.py
```

### 3. **Start the TurtleBot 4 Node**
```bash
ros2 run tb4_bridge turtlebot_ethernet_bridge
```

### 4. **Send a Test Command**
```bash
python3 udp_sender.py
# Enter:
drive forward 0.25 speed 0.25
```

---

## 📈 Project Goals

✅ Develop a low-cost communication interface using **Visible Light Communication**  
✅ Replace radio-based localization with optical signaling  
✅ Demonstrate real-time control of a **mobile robot** using a **single luminaire**  
✅ Explore future expansion to multi-robot indoor networks

---

## 🧭 Authors

| Name | Role | Focus |
|------|------|--------|
| **Noe Avila** | Electrical Engineer | ROS 2 Control, VLC Signal Processing |
| **Chase …** | Embedded Systems Engineer | PRU Firmware & BeagleBone Integration |
| **Nils …** | Systems Engineer | Network Interface & Thermal Design |

---

## 🧠 References

- [TurtleBot 4 User Manual](https://turtlebot.github.io/turtlebot4-user-manual/)
- [iRobot Create 3 ROS 2 Interface](https://github.com/iRobotEducation/irobot_create_msgs)
- [OpenVLC Project Documentation](https://github.com/openvlc/openvlc)

---

### 📸 Demo Overview
> VLC signal transmission drives TurtleBot movement in real time  
> using light intensity modulation decoded by the BeagleBone Black.

---

### 🧾 License
MIT License © 2025 Colorado School of Mines Capstone Team

---
