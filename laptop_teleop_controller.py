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
    print("  A Button: Extend Frame (Dig down)")
    print("  Y Button: Retract Frame (Lift up)")
    print("  Right Bumper: Extend Deposit (Hold Sand)")
    print("  Left Bumper: Retract Deposit (Dump Sand)")
    print("  X Button: Toggle Driving Direction (Forward/Reverse cam)")
    print("  Left Trigger: AUTO DIG Sequence")
    print("  Right Trigger: AUTO DEPOSIT Sequence")
    print("  B Button: E-STOP (Hold to stop everything)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # State variables for toggles and macros
    direction_inverted = False
    x_button_was_pressed = False
    
    auto_dig_active = False
    auto_dig_start_time = 0
    
    auto_deposit_active = False
    auto_deposit_start_time = 0

    try:
        while True:
            pygame.event.pump()

            # Read Buttons first to check state
            a_pressed = joystick.get_button(BUTTON_A)
            y_pressed = joystick.get_button(BUTTON_Y)
            x_pressed = joystick.get_button(BUTTON_X)
            rb_pressed = joystick.get_button(BUTTON_RIGHT_BUMPER)
            # Assuming Left Bumper is button 4 (verify this on your controller)
            lb_pressed = joystick.get_button(4) 
            b_pressed = joystick.get_button(BUTTON_B) # E-STOP
            
            # Read Triggers (Triggers are axes in pygame, usually axis 2 (LT) and 5 (RT))
            # They go from -1.0 (unpressed) to 1.0 (fully pressed)
            lt_axis = joystick.get_axis(2) if joystick.get_numaxes() > 2 else -1.0
            rt_axis = joystick.get_axis(5) if joystick.get_numaxes() > 5 else -1.0
            
            lt_pressed = lt_axis > 0.5
            rt_pressed = rt_axis > 0.5

            # Handle X Button Toggle for Direction Inversion
            if x_pressed and not x_button_was_pressed:
                direction_inverted = not direction_inverted
                print(f"\n[INFO] Direction Inverted: {direction_inverted}")
            x_button_was_pressed = x_pressed

            # Check for E-Stop (Overrides everything)
            if b_pressed:
                auto_dig_active = False
                auto_deposit_active = False
                msg = "0.00,0.00,0,0,1"
                sock.sendto(msg.encode('utf-8'), (JETSON_IP, JETSON_PORT))
                print("E-STOP ACTIVE!                      \r", end="")
                time.sleep(0.05)
                continue

            # --- MACRO LOGIC ---
            current_time = time.time()
            v = 0.0
            w = 0.0
            frame_cmd = 0
            deposit_cmd = 0

            # 1. Check if triggering Auto Dig
            if lt_pressed and not auto_dig_active and not auto_deposit_active:
                auto_dig_active = True
                auto_dig_start_time = current_time
                print("\n[AUTO] Starting Dig Sequence...")

            # 2. Check if triggering Auto Deposit
            if rt_pressed and not auto_deposit_active and not auto_dig_active:
                auto_deposit_active = True
                auto_deposit_start_time = current_time
                print("\n[AUTO] Starting Deposit Sequence...")

            # Execute Auto Dig
            if auto_dig_active:
                elapsed = current_time - auto_dig_start_time
                if elapsed < 3.0:
                    # Phase 1: Lower frame to ground (3 seconds)
                    frame_cmd = 1
                elif elapsed < 8.0:
                    # Phase 2: Drive forward slowly (5 seconds)
                    frame_cmd = 0 # Frame stays down (limit switch holds it), just drive
                    v = 0.5 # Slow forward speed
                elif elapsed < 11.0:
                    # Phase 3: Lift frame back up (3 seconds)
                    frame_cmd = -1
                else:
                    # Sequence Complete
                    auto_dig_active = False
                    print("\n[AUTO] Dig Sequence Complete.")

            # Execute Auto Deposit
            elif auto_deposit_active:
                elapsed = current_time - auto_deposit_start_time
                if elapsed < 3.0:
                    # Phase 1: Retract door to dump (3 seconds)
                    deposit_cmd = -1 
                else:
                    auto_deposit_active = False
                    print("\n[AUTO] Deposit Sequence Complete.")

            # --- MANUAL LOGIC (Only runs if no macros are active) ---
            else:
                # Read Axes
                raw_v = -joystick.get_axis(AXIS_LEFT_STICK_Y) 
                raw_w = -joystick.get_axis(AXIS_RIGHT_STICK_X)

                if abs(raw_v) < 0.1: raw_v = 0.0
                if abs(raw_w) < 0.1: raw_w = 0.0

                # Apply Direction Inversion
                if direction_inverted:
                    raw_v = -raw_v
                    # Note: Turning direction (w) usually stays the same relative to the controller 
                    # so right stick right still turns the chassis clockwise.

                v = raw_v * 1.5 
                w = raw_w * 3.0 

                # Manual Actuator Control
                if a_pressed and not y_pressed:
                    frame_cmd = 1 # Extend (Dig)
                elif y_pressed and not a_pressed:
                    frame_cmd = -1 # Retract (Lift)

                if rb_pressed and not lb_pressed:
                    deposit_cmd = 1 # Extend (Hold)
                elif lb_pressed and not rb_pressed:
                    deposit_cmd = -1 # Retract (Dump)

            # Format Message
            # Format: "v,w,frame_cmd,deposit_cmd,estop"
            msg = f"{v:.2f},{w:.2f},{frame_cmd},{deposit_cmd},0"
            
            # Send via UDP
            sock.sendto(msg.encode('utf-8'), (JETSON_IP, JETSON_PORT))
            
            # Print for debugging
            mode = "AUTO" if (auto_dig_active or auto_deposit_active) else ("REV " if direction_inverted else "FWD ")
            print(f"[{mode}] Sent: {msg}          \r", end="")
            
            # Run at ~20Hz
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExiting...")
        pygame.quit()
        sock.close()

if __name__ == '__main__':
    main()
