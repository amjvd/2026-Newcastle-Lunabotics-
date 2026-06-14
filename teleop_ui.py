import pygame
import socket
import time
import sys
import threading

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV (cv2) or numpy not installed. Camera feeds will be disabled.")
    print("To enable, run: pip install opencv-python numpy")

JETSON_IP = "192.168.8.160"
JETSON_PORT = 5005
TELEMETRY_PORT = 5006

# Map constants
AXIS_LEFT_STICK_Y = 1 
AXIS_RIGHT_STICK_X = 3 
BUTTON_A = 0
BUTTON_B = 1
BUTTON_X = 2
BUTTON_Y = 3
BUTTON_LEFT_BUMPER = 4
BUTTON_RIGHT_BUMPER = 5
BUTTON_START = 7  

MAX_V = 0.20  
MAX_W = 0.50  
AUTO_DIG_SPEED = 0.15  

# Global Motor Data Store
motor_data = {
    1: {"pos": 0.0, "vel": 0.0, "trq": 0.0, "temp": 0},
    2: {"pos": 0.0, "vel": 0.0, "trq": 0.0, "temp": 0},
    3: {"pos": 0.0, "vel": 0.0, "trq": 0.0, "temp": 0},
    4: {"pos": 0.0, "vel": 0.0, "trq": 0.0, "temp": 0},
}

# Global Camera Frames Store
latest_frames = {
    "front": None,
    "rear": None,
    "scraper": None
}

def camera_receiver(port, name, width, height):
    """Background thread to receive and decode H.264 UDP video streams."""
    if not CV2_AVAILABLE:
        return
        
    # GStreamer pipeline to receive UDP, depayload, decode, and convert to BGR
    cap = cv2.VideoCapture(f"udp://0.0.0.0:{port}", cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Force lowest latency possibl
    if not cap.isOpened():
        # Fallback if OpenCV was built without GStreamer
        cap = cv2.VideoCapture(f"udp://127.0.0.1:{port}", cv2.CAP_FFMPEG)
        
    while True:
        ret, frame = cap.read()
        if ret:
            # Resize
            frame = cv2.resize(frame, (width, height))
            # Convert BGR (OpenCV) to RGB (Pygame)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Pygame wants (width, height, color) so we swap axes
            frame = np.swapaxes(frame, 0, 1)
            
            latest_frames[name] = pygame.surfarray.make_surface(frame)
        else:
            time.sleep(0.01)

def telemetry_receiver():
    """Background thread to constantly listen for motor data from Jetson."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", TELEMETRY_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            msg = data.decode('utf-8').strip()
            if msg.startswith("M,"):
                parts = msg.split(',')
                if len(parts) >= 6:
                    m_id = int(parts[1])
                    if m_id in motor_data:
                        motor_data[m_id]["pos"] = float(parts[2])
                        motor_data[m_id]["vel"] = float(parts[3])
                        motor_data[m_id]["trq"] = float(parts[4])
                        motor_data[m_id]["temp"] = int(parts[5])
        except Exception as e:
            pass

def draw_ui(screen, font, title_font, ctrl_state, sys_state):
    """Draws the Dashboard UI."""
    screen.fill((30, 30, 30))
    
    # ---------------------------------------------------------
    # LEFT PANEL: Controller Inputs
    # ---------------------------------------------------------
    pygame.draw.rect(screen, (45, 45, 45), (20, 20, 350, 680), border_radius=10)
    screen.blit(title_font.render("CONTROLLER STATE", True, (255, 255, 255)), (80, 40))
    
    y = 100
    for key, val in ctrl_state.items():
        if isinstance(val, float):
            # Axes
            color = (0, 255, 255) if abs(val) > 0.05 else (150, 150, 150)
            text = font.render(f"{key}: {val:+.2f}", True, color)
        else:
            # Buttons
            color = (0, 255, 0) if val else (100, 100, 100)
            text = font.render(f"{key}: {'PRESSED' if val else '----'}", True, color)
        
        screen.blit(text, (40, y))
        y += 35

    y += 20
    screen.blit(title_font.render("SYSTEM MODES", True, (255, 255, 255)), (100, y))
    y += 40
    for key, active in sys_state.items():
        color = (255, 100, 100) if active else (100, 100, 100)
        text = font.render(f"{key}: {'ACTIVE' if active else 'IDLE'}", True, color)
        screen.blit(text, (40, y))
        y += 35

    # ---------------------------------------------------------
    # MIDDLE PANEL: Cameras
    # ---------------------------------------------------------
    # Front Camera
    if latest_frames["front"]:
        screen.blit(latest_frames["front"], (390, 20))
        pygame.draw.rect(screen, (0, 255, 0), (390, 20, 480, 360), width=2, border_radius=5)
    else:
        pygame.draw.rect(screen, (0, 0, 0), (390, 20, 480, 360), border_radius=5)
        pygame.draw.rect(screen, (100, 100, 100), (390, 20, 480, 360), width=2, border_radius=5)
        screen.blit(title_font.render("FRONT CAMERA (No Signal)", True, (150, 150, 150)), (470, 180))

    # Rear Camera
    if latest_frames["rear"]:
        screen.blit(latest_frames["rear"], (390, 400))
        pygame.draw.rect(screen, (0, 255, 0), (390, 400, 230, 180), width=2, border_radius=5)
    else:
        pygame.draw.rect(screen, (0, 0, 0), (390, 400, 230, 180), border_radius=5)
        pygame.draw.rect(screen, (100, 100, 100), (390, 400, 230, 180), width=2, border_radius=5)
        screen.blit(font.render("REAR CAM", True, (150, 150, 150)), (450, 480))

    # Scraper Camera
    if latest_frames["scraper"]:
        screen.blit(latest_frames["scraper"], (640, 400))
        pygame.draw.rect(screen, (0, 255, 0), (640, 400, 230, 180), width=2, border_radius=5)
    else:
        pygame.draw.rect(screen, (0, 0, 0), (640, 400, 230, 180), border_radius=5)
        pygame.draw.rect(screen, (100, 100, 100), (640, 400, 230, 180), width=2, border_radius=5)
        screen.blit(font.render("SCRAPER CAM", True, (150, 150, 150)), (690, 480))

    # ---------------------------------------------------------
    # RIGHT PANEL: Motor Telemetry
    # ---------------------------------------------------------
    pygame.draw.rect(screen, (45, 45, 45), (890, 20, 370, 680), border_radius=10)
    screen.blit(title_font.render("MOTOR TELEMETRY", True, (255, 255, 255)), (970, 40))
    
    m_y = 100
    motor_names = {1: "FL (Front Left)", 2: "RL (Rear Left)", 3: "FR (Front Right)", 4: "RR (Rear Right)"}
    
    for m_id, data in motor_data.items():
        pygame.draw.rect(screen, (60, 60, 60), (910, m_y, 330, 130), border_radius=8)
        
        name_txt = font.render(f"ID {m_id} : {motor_names[m_id]}", True, (255, 200, 50))
        screen.blit(name_txt, (925, m_y + 10))
        
        p_txt = font.render(f"Pos: {data['pos']:>7.2f} rad", True, (200, 255, 200))
        v_txt = font.render(f"Vel: {data['vel']:>7.2f} rad/s", True, (200, 255, 200))
        t_txt = font.render(f"Trq: {data['trq']:>7.2f} Nm", True, (200, 200, 255))
        
        tmp_color = (255, 80, 80) if data['temp'] > 50 else (200, 200, 200)
        tmp_txt = font.render(f"Temp: {data['temp']} C", True, tmp_color)
        
        screen.blit(p_txt, (925, m_y + 45))
        screen.blit(v_txt, (925, m_y + 70))
        screen.blit(t_txt, (1100, m_y + 45))
        screen.blit(tmp_txt, (1100, m_y + 70))
        
        m_y += 145

    pygame.display.flip()

def main():
    pygame.init()
    pygame.joystick.init()
    
    # Setup Window
    screen = pygame.display.set_mode((1280, 720))
    pygame.display.set_caption("Lunabotics Telemetry Dashboard")
    font = pygame.font.SysFont("consolas", 16, bold=True)
    title_font = pygame.font.SysFont("consolas", 22, bold=True)

    if pygame.joystick.get_count() == 0:
        print("No joystick found. Connect Xbox controller.")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Start background thread to listen for incoming motor data
    threading.Thread(target=telemetry_receiver, daemon=True).start()
    
    # Start background threads for cameras
    if CV2_AVAILABLE:
        threading.Thread(target=camera_receiver, args=(5010, "front", 480, 360), daemon=True).start()
        threading.Thread(target=camera_receiver, args=(5011, "rear", 230, 180), daemon=True).start()
        threading.Thread(target=camera_receiver, args=(5012, "scraper", 230, 180), daemon=True).start()

    # State variables
    direction_inverted = False
    x_button_was_pressed = False
    estop_latched = False
    
    auto_dig_active = False
    auto_dig_start_time = 0
    lt_was_pressed = False
    
    auto_deposit_active = False
    auto_deposit_start_time = 0
    rt_was_pressed = False

    clock = pygame.time.Clock()

    try:
        while True:
            # 1. Handle Events (Quit)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            # 2. Read Controller
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
            
            left_stick_y = joystick.get_axis(AXIS_LEFT_STICK_Y)
            right_stick_x = joystick.get_axis(AXIS_RIGHT_STICK_X)

            # 3. Controller Logic
            if x_pressed and not x_button_was_pressed:
                direction_inverted = not direction_inverted
            x_button_was_pressed = x_pressed

            if b_pressed and not estop_latched:
                estop_latched = True
                auto_dig_active = False
                auto_deposit_active = False
            if estop_latched and start_pressed and not b_pressed:
                estop_latched = False

            current_time = time.time()
            v, w, frame_cmd, deposit_cmd = 0.0, 0.0, 0, 0

            if not estop_latched:
                # Trigger Edge Detection
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
                    if elapsed < 3.0: frame_cmd = 1
                    elif elapsed < 8.0: frame_cmd = 0; v = AUTO_DIG_SPEED 
                    elif elapsed < 11.0: frame_cmd = -1
                    else: auto_dig_active = False

                elif auto_deposit_active:
                    elapsed = current_time - auto_deposit_start_time
                    if elapsed < 3.0: deposit_cmd = -1 
                    elif elapsed < 6.0: deposit_cmd = 1  
                    else: auto_deposit_active = False

                else:
                    raw_v = -left_stick_y 
                    raw_w = -right_stick_x

                    if abs(raw_v) < 0.1: raw_v = 0.0
                    if abs(raw_w) < 0.1: raw_w = 0.0

                    if direction_inverted: raw_v = -raw_v

                    v = raw_v * MAX_V
                    w = raw_w * MAX_W

                    if a_pressed and not y_pressed: frame_cmd = 1 
                    elif y_pressed and not a_pressed: frame_cmd = -1 

                    if lb_pressed and not rb_pressed: deposit_cmd = -1 
                    elif rb_pressed and not lb_pressed: deposit_cmd = 1 

            # 4. Send Network Command
            estop_flag = 1 if estop_latched else 0
            msg = f"{v:.2f},{w:.2f},{frame_cmd},{deposit_cmd},{estop_flag}"
            sock.sendto(msg.encode('utf-8'), (JETSON_IP, JETSON_PORT))

            # 5. Update UI
            ctrl_state = {
                "Left Stick Y": left_stick_y,
                "Right Stick X": right_stick_x,
                "Left Trigger": lt_axis,
                "Right Trigger": rt_axis,
                "Btn A (Dig Frame)": a_pressed,
                "Btn Y (Lift Frame)": y_pressed,
                "Btn LB (Retract Door)": lb_pressed,
                "Btn RB (Extend Door)": rb_pressed,
                "Btn X (Invert)": x_pressed,
                "Btn B (E-STOP)": b_pressed,
                "Start (Clear E-Stop)": start_pressed
            }
            
            sys_state = {
                "E-STOP LATCHED": estop_latched,
                "DRIVE INVERTED": direction_inverted,
                "AUTO DIG": auto_dig_active,
                "AUTO DEPOSIT": auto_deposit_active,
            }

            draw_ui(screen, font, title_font, ctrl_state, sys_state)
            
            # Limit to ~20 fps to match sleep(0.05) from original script
            clock.tick(20)

    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        sock.close()

if __name__ == '__main__':
    main()
