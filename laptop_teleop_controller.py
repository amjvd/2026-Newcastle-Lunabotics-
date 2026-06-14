import pygame
import socket
import time
import sys

JETSON_IP = "192.168.8.1" 
JETSON_PORT = 5005

#
AXIS_LEFT_STICK_Y = 1 
AXIS_RIGHT_STICK_X = 3 

BUTTON_A = 0
BUTTON_B = 1
BUTTON_X = 2
BUTTON_Y = 3
BUTTON_LEFT_BUMPER = 4
BUTTON_RIGHT_BUMPER = 5
BUTTON_START = 7  

MAX_V = 0.20  # m/s
MAX_W = 0.50  # rad/s
AUTO_DIG_SPEED = 0.15  

def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick found. Connect Xbox controller.")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Initialized: {joystick.get_name()}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    direction_inverted = False
    x_button_was_pressed = False
    estop_latched = False
    
    auto_dig_active = False
    auto_dig_start_time = 0
    lt_was_pressed = False
    
    auto_deposit_active = False
    auto_deposit_start_time = 0
    rt_was_pressed = False

    try:
        while True:
            pygame.event.pump()

            a_pressed = joystick.get_button(BUTTON_A)
            y_pressed = joystick.get_button(BUTTON_Y)
            x_pressed = joystick.get_button(BUTTON_X)
            rb_pressed = joystick.get_button(BUTTON_RIGHT_BUMPER)
            lb_pressed = joystick.get_button(BUTTON_LEFT_BUMPER)
            b_pressed = joystick.get_button(BUTTON_B)
            start_pressed = joystick.get_button(BUTTON_START) if joystick.get_numbuttons() > BUTTON_START else False
            
            lt_axis = joystick.get_axis(2) if joystick.get_numaxes() > 2 else -1.0
            rt_axis = joystick.get_axis(5) if joystick.get_numaxes() > 5 else -1.0
            
            lt_pressed = lt_axis > 0.5
            rt_pressed = rt_axis > 0.5

            # Direction Inversion
            if x_pressed and not x_button_was_pressed:
                direction_inverted = not direction_inverted
                print(f"\n[INFO] Direction Inverted: {direction_inverted}")
            x_button_was_pressed = x_pressed

            # Latching E-Stop
            if b_pressed and not estop_latched:
                estop_latched = True
                auto_dig_active = False
                auto_deposit_active = False
                print("\n[E-STOP] LATCHED! Press START to clear.")
            if estop_latched and start_pressed and not b_pressed:
                estop_latched = False
                print("\n[E-STOP] Cleared. Resuming control.")

            if estop_latched:
                sock.sendto("0.00,0.00,0,0,1".encode('utf-8'), (JETSON_IP, JETSON_PORT))
                print("E-STOP ACTIVE - press START to clear \r", end="")
                time.sleep(0.05)
                continue

            current_time = time.time()
            v = 0.0
            w = 0.0
            frame_cmd = 0
            deposit_cmd = 0

            # Trigger Edge Detection (Prevents Macro Lockout)
            if lt_pressed and not lt_was_pressed and not auto_dig_active and not auto_deposit_active:
                auto_dig_active = True
                auto_dig_start_time = current_time
            lt_was_pressed = lt_pressed

            if rt_pressed and not rt_was_pressed and not auto_deposit_active and not auto_dig_active:
                auto_deposit_active = True
                auto_deposit_start_time = current_time
            rt_was_pressed = rt_pressed

            if auto_dig_active:
                elapsed = current_time - auto_dig_start_time
                if elapsed < 3.0:
                    frame_cmd = 1
                elif elapsed < 8.0:
                    frame_cmd = 0 
                    v = AUTO_DIG_SPEED 
                elif elapsed < 11.0:
                    frame_cmd = -1
                else:
                    auto_dig_active = False

            elif auto_deposit_active:
                elapsed = current_time - auto_deposit_start_time
                if elapsed < 3.0:
                    deposit_cmd = -1 # Retract actuator to dump 
                elif elapsed < 6.0:
                    deposit_cmd = 1  # Extend actuator back to normal
                else:
                    auto_deposit_active = False

            else:
                raw_v = -joystick.get_axis(AXIS_LEFT_STICK_Y) 
                raw_w = -joystick.get_axis(AXIS_RIGHT_STICK_X)

                if abs(raw_v) < 0.1: raw_v = 0.0
                if abs(raw_w) < 0.1: raw_w = 0.0

                if direction_inverted:
                    raw_v = -raw_v

                v = raw_v * MAX_V
                w = raw_w * MAX_W

                if a_pressed and not y_pressed:
                    frame_cmd = 1 # Dig
                elif y_pressed and not a_pressed:
                    frame_cmd = -1 # Lift

                # UPDATED MANUAL DOOR MAPPING
                if lb_pressed and not rb_pressed:
                    deposit_cmd = -1 # Retract (Dump)
                elif rb_pressed and not lb_pressed:
                    deposit_cmd = 1 # Extend (Close/Normal)

            msg = f"{v:.2f},{w:.2f},{frame_cmd},{deposit_cmd},0"
            sock.sendto(msg.encode('utf-8'), (JETSON_IP, JETSON_PORT))
            
            mode = "AUTO" if (auto_dig_active or auto_deposit_active) else ("REV " if direction_inverted else "FWD ")
            print(f"[{mode}] Sent: {msg}          \r", end="")
            time.sleep(0.05)

    except KeyboardInterrupt:
        pygame.quit()
        sock.close()

if __name__ == '__main__':
    main()
