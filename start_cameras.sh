#!/bin/bash

# REPLACE THIS WITH YOUR LAPTOP'S IP ADDRESS!
LAPTOP_IP="192.168.8.x" 

echo "=========================================================="
echo "Starting Lunabotics Camera Streams (H.264 Hardware Encoded)"
echo "Target Laptop IP: $LAPTOP_IP"
echo "Press Ctrl+C to stop all streams."
echo "=========================================================="

# NOTE: The /dev/videoX numbers might change depending on what order you plug them in. 
# Run 'ls -la /dev/video*' on the Jetson to verify which is which!

# 1. Front Camera (1.2 Mbps, Port 5010)
echo "Starting Front Camera on /dev/video0 -> Port 5010..."
gst-launch-1.0 v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=15/1 ! nvvidconv ! nvv4l2h264enc bitrate=1200000 ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5010 sync=false &

# 2. Rear Camera (1.2 Mbps, Port 5011)
echo "Starting Rear Camera on /dev/video2 -> Port 5011..."
gst-launch-1.0 v4l2src device=/dev/video2 ! video/x-raw,width=640,height=480,framerate=15/1 ! nvvidconv ! nvv4l2h264enc bitrate=1200000 ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5011 sync=false &

# 3. Scraper Camera (The dual-lens one) (1.2 Mbps, Port 5012)
echo "Starting Scraper Camera on /dev/video4 -> Port 5012..."
gst-launch-1.0 v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=15/1 ! nvvidconv ! nvv4l2h264enc bitrate=1200000 ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5012 sync=false &

# Wait keeps the script running so we can kill all background tasks easily with Ctrl+C
wait
