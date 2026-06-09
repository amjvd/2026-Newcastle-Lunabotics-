import pygame
import socket
import time
import sys

# Configuration
JETSON_IP = "192.168.8.1" # Change this to the Jetson's IP on the GL.iNet router network
JETSON_PORT = 5005

# Controller mapping (Standard Xbox Controller via Pygame)
# These may vary slightly depending on your OS (Windows/Linux/Mac)
AXIS_LEFT_STICK_Y = 1 # Up/Down
AXIS_RIGHT_STICK_X = 3 # Left/Right (sometimes 2 or 4 depending on OS, verify with test)

BUTTON_A = 0
BUTTON_B = 1
BUTTON_X = 2
BUTTON_Y = 3
BUTTON_RIGHT_BUMPER = 5

def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick/controller found. Please connect an Xbox controller.")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Initialized Joystick: {joystick.get_name()}")
    
    print(f"Sending UDP commands to {JETSON_IP}:{JETSON_PORT}")
    print("Controls:")
    print("  Left Stick Y: Forward/Backward")
    print("  Right Stick X: Turn Left/Right")
    print("  A Button: Extend Frame (Dig)")
    print("  Y Button: Retract Frame (Lift)")
    print("  X Button: Extend Deposit (Hold Sand)")
    print("  Right Bumper: Retract Deposit (Dump Sand)")
    print("  B Button: E-STOP (Hold to stop everything)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        while True:
            pygame.event.pump()

            # Read Axes
            # Pygame Y axis is inverted (-1 is up, 1 is down), so we negate it for standard v (positive forward)
            raw_v = -joystick.get_axis(AXIS_LEFT_STICK_Y) 
            # X axis: right is positive. For w (angular velocity), turning left is usually positive, turning right is negative.
            raw_w = -joystick.get_axis(AXIS_RIGHT_STICK_X)

            # Deadzones
            if abs(raw_v) < 0.1: raw_v = 0.0
            if abs(raw_w) < 0.1: raw_w = 0.0

            # Scale to Max Velocities
            v = raw_v * 1.5 # Max 1.5 m/s (Adjust as needed)
            w = raw_w * 3.0 # Max 3.0 rad/s (Adjust as needed)

            # Read Buttons
            a_pressed = joystick.get_button(BUTTON_A)
            y_pressed = joystick.get_button(BUTTON_Y)
            x_pressed = joystick.get_button(BUTTON_X)
            rb_pressed = joystick.get_button(BUTTON_RIGHT_BUMPER)
            b_pressed = joystick.get_button(BUTTON_B) # E-STOP

            # Evaluate Commands
            frame_cmd = 0
            if a_pressed and not y_pressed:
                frame_cmd = 1 # Extend
            elif y_pressed and not a_pressed:
                frame_cmd = -1 # Retract

            deposit_cmd = 0
            if x_pressed and not rb_pressed:
                deposit_cmd = 1 # Extend
            elif rb_pressed and not x_pressed:
                deposit_cmd = -1 # Retract

            estop = 1 if b_pressed else 0

            # Format Message
            # Format: "v,w,frame_cmd,deposit_cmd,estop"
            msg = f"{v:.2f},{w:.2f},{frame_cmd},{deposit_cmd},{estop}"
            
            # Send via UDP
            sock.sendto(msg.encode('utf-8'), (JETSON_IP, JETSON_PORT))
            
            # Print for debugging
            print(f"Sent: {msg}\r", end="")
            
            # Run at ~20Hz
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting...")
        pygame.quit()
        sock.close()

if __name__ == '__main__':
    main()
