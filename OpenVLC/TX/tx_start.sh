#!/bin/bash

# Go to Driver folder and load driver
cd /home/debian/OpenVLC/Latest_Version/Driver || { echo "Driver folder not found!"; exit 1; }
sudo ./load_test.sh
sudo ./load_test.sh

# Go to PRU/TX folder
cd /home/debian/OpenVLC/Latest_Version/PRU/TX || { echo "TX folder not found!"; exit 1; }

# Deploy firmware
sudo ./deploy.sh
