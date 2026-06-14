import socket
import serial
import time
import sys

UDP_IP = "0.0.0.0" 
UDP_PORT = 5005
SERIAL_PORT = "/dev/ttyUSB0" 
BAUD_RATE = 115200

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01) # Short timeout for non-blocking style
        time.sleep(2) 
    except Exception as e:
        print(f"Failed to connect to Serial: {e}")
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.01)  # Short socket timeout so we can poll serial quickly

    laptop_addr = None

    try:
        last_receive_time = time.time()
        while True:
            # 1. Check for incoming UDP from Laptop
            try:
                data, addr = sock.recvfrom(1024)
                laptop_addr = addr # Remember the laptop's IP and port
                message = data.decode('utf-8').strip()
                last_receive_time = time.time()
                
                if message.count(',') == 4:
                    cmd_str = f"{message}\n"
                    ser.write(cmd_str.encode('utf-8'))
            
            except socket.timeout:
                if time.time() - last_receive_time > 0.2:
                    ser.write(b"0.0,0.0,0,0,0\n")

            # 2. Check for incoming Serial Telemetry from ESP32
            while ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line.startswith("M,") and laptop_addr:
                        # Forward telemetry back to laptop on port 5006
                        sock.sendto(line.encode('utf-8'), (laptop_addr[0], 5006))
                except Exception:
                    pass # Ignore any corrupted serial lines

    except KeyboardInterrupt:
        ser.write(b"0.0,0.0,0,0,0\n")
        ser.close()
        sock.close()

if __name__ == '__main__':
    main()
