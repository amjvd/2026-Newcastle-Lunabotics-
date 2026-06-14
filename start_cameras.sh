#!/bin/bash


LAPTOP_IP="192.168.8.x" 

echo "=========================================================="
echo "Starting Lunabotics Camera Streams (H.264 Software Encoded)"
echo "Target Laptop IP: $LAPTOP_IP"
echo "Press Ctrl+C to stop all streams."
echo "=========================================================="



# 1. Front Camera (Port 5010)
echo "Starting Front Camera on /dev/video0 -> Port 5010..."
gst-launch-1.0 v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=15/1 ! videoconvert ! x264enc tune=zerolatency bitrate=1200 speed-preset=ultrafast ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5010 sync=false &

# 2. Rear Camera (Port 5011)
echo "Starting Rear Camera on /dev/video4 -> Port 5011..."
gst-launch-1.0 v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=15/1 ! videoconvert ! x264enc tune=zerolatency bitrate=1200 speed-preset=ultrafast ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5011 sync=false &

# 3. Scraper Camera (The dual-lens one) (Port 5012)
echo "Starting Scraper Camera on /dev/video8 -> Port 5012..."
gst-launch-1.0 v4l2src device=/dev/video8 ! video/x-raw,width=640,height=480,framerate=15/1 ! videoconvert ! x264enc tune=zerolatency bitrate=1200 speed-preset=ultrafast ! h264parse ! rtph264pay ! udpsink host=$LAPTOP_IP port=5012 sync=false &

wait
