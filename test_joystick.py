import pygame
import sys
import time

def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick found. Please connect a controller.")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Detected controller: {joystick.get_name()}")
    print("-" * 40)
    print("Press Ctrl+C to exit.")
    print("Test your mappings below:")
    print("-" * 40)

    # Dictionary mapping for descriptive outputs
    button_map = {
        0: "A (Manual Dig Frame)",
        1: "B (E-Stop LATCH)",
        2: "X (Invert Driving Direction)",
        3: "Y (Manual Lift Frame)",
        4: "LB (Manual Door Retract/Dump)",
        5: "RB (Manual Door Extend/Close)",
        6: "Select/View (Unused)",
        7: "Start (Clear E-Stop)"
    }
    
    axis_map = {
        1: "L-Stick Y (Drive FWD/REV)",
        3: "R-Stick X (Steer L/R)",
        2: "LT (Auto Dig Sequence)",
        5: "RT (Auto Deposit Sequence)"
    }

    try:
        while True:
            pygame.event.pump()
            
            output = []
            
            # Read Axes
            for i in range(joystick.get_numaxes()):
                axis_val = joystick.get_axis(i)
                # Left/Right triggers range from -1.0 to 1.0 (0.0 at rest before first press)
                if abs(axis_val) > 0.15 and (axis_val != -1.0 or i not in [2, 5]):
                    desc = axis_map.get(i, f"Axis {i}")
                    output.append(f"{desc}: {axis_val:+.2f}")
                    
            # Read Buttons
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    desc = button_map.get(i, f"Btn {i}")
                    output.append(f"{desc}: DOWN")
                    
            # Read Hats (D-Pad)
            for i in range(joystick.get_numhats()):
                hat_val = joystick.get_hat(i)
                if hat_val != (0, 0):
                    output.append(f"D-Pad: {hat_val}")
            
            if output:
                # \033[K clears the current line
                print("\033[K" + " | ".join(output) + " " * 10, end="\r")
            else:
                print("\033[Kwaiting for input...", end="\r")
                
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        pygame.quit()

if __name__ == "__main__":
    main()
