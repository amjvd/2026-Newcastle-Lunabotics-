import socket
import serial
import time
import sys

# Configuration
UDP_IP = "0.0.0.0" # Listen on all interfaces
UDP_PORT = 5005
SERIAL_PORT = "/dev/ttyUSB0" # Change this to the correct ESP32 port (e.g., /dev/ttyACM0)
BAUD_RATE = 115200

def main():
    # Setup Serial
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to ESP32 on {SERIAL_PORT}")
        # Wait for ESP32 to reboot after serial connection
        time.sleep(2) 
    except Exception as e:
        print(f"Failed to connect to Serial: {e}")
        print("Please check the SERIAL_PORT and ensure the ESP32 is connected.")
        sys.exit(1)

    # Setup UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Listening for UDP packets on port {UDP_PORT}")

    last_receive_time = time.time()
    
    try:
        while True:
            # Check for UDP data
            sock.settimeout(0.5) # 500ms timeout
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8').strip()
                last_receive_time = time.time()
                
                # We expect the format "v,w,frame_cmd,deposit_cmd,estop"
                # Validate the message briefly (check commas)
                if message.count(',') == 4:
                    cmd_str = f"{message}\n"
                    ser.write(cmd_str.encode('utf-8'))
                    # Optional: Print what we are sending for debugging
                    # print(f"Sent to ESP32: {cmd_str.strip()}")
                else:
                    print(f"Invalid message format received: {message}")

            except socket.timeout:
                # No data received within timeout, safety stop
                if time.time() - last_receive_time > 0.5:
                    ser.write(b"0.0,0.0,0,0,0\n")

    except KeyboardInterrupt:
        print("Shutting down...")
        ser.write(b"0.0,0.0,0,0,0\n")
        ser.close()
        sock.close()

if __name__ == '__main__':
    main()
