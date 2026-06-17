#include <Arduino.h>
#include "driver/twai.h"

// WIRING PINS
#define CAN_TX_PIN GPIO_NUM_27
#define CAN_RX_PIN GPIO_NUM_26

#define MOTOR_FL 1
#define MOTOR_RL 3
#define MOTOR_FR 2
#define MOTOR_RR 4

// --- EMERGENCY PIT-STOP PINS ---
// The Cytron is physically plugged into 19 (acting as PWM/Power) and 21 (acting as DIR)
#define CYTRON_PWM 19
#define CYTRON_DIR 21

// The old frame pins (18 & 23) are physically empty right now
#define UNUSED_IN1 18
#define UNUSED_IN2 23

// AK45-36 LIMITS 
#define P_MIN -12.5f
#define P_MAX  12.5f
#define V_MIN -6.0f
#define V_MAX  6.0f
#define T_MIN -34.0f
#define T_MAX  34.0f
#define KP_MIN 0.0f
#define KP_MAX 500.0f
#define KD_MIN 0.0f
#define KD_MAX 5.0f

#define WHEEL_RADIUS 0.15f 
#define TRACK_WIDTH 0.7f 

// State variables
float target_v = 0.0;
float target_w = 0.0;
int frame_cmd = 0;
int deposit_cmd = 0; 
bool estop = false;

unsigned long previousMillis = 0;
unsigned long last_cmd_time = 0;
const unsigned long CMD_TIMEOUT_MS = 500;

// Unsigned Integer to Float Conversion
float uint_to_float(int x_int, float x_min, float x_max, int bits) {
    float span = x_max - x_min;
    float offset = x_min;
    return ((float)x_int) * span / ((float)((1 << bits) - 1)) + offset;
}

// Float to Unsigned Integer Conversion
int float_to_uint(float x, float x_min, float x_max, int bits) {
    float span = x_max - x_min;
    float offset = x_min;
    if(x < x_min) x = x_min;
    else if(x > x_max) x = x_max;
    return (int) ((x - offset) * ((float)((1 << bits) - 1)) / span);
}

// Send standard CAN frame
void send_can_message(uint32_t id, uint8_t* data, uint8_t len) {
    twai_message_t message = {};
    message.identifier = id;
    message.extd = 0;
    message.rtr = 0;
    message.data_length_code = len;
    for (int i = 0; i < len; i++) {
        message.data[i] = data[i];
    }
    twai_transmit(&message, pdMS_TO_TICKS(1));
}

// SPECIAL HEX COMMANDS
void enter_mit_mode(uint32_t id) {
    uint8_t data[8] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFC};
    send_can_message(id, data, 8);
}

// PACK AND SEND MIT COMMAND
void pack_cmd(uint32_t id, float p_des, float v_des, float kp, float kd, float t_ff) {
    p_des = constrain(p_des, P_MIN, P_MAX);
    v_des = constrain(v_des, V_MIN, V_MAX);
    kp = constrain(kp, KP_MIN, KP_MAX);
    kd = constrain(kd, KD_MIN, KD_MAX);
    t_ff = constrain(t_ff, T_MIN, T_MAX);
    
    int p_int = float_to_uint(p_des, P_MIN, P_MAX, 16);
    int v_int = float_to_uint(v_des, V_MIN, V_MAX, 12);
    int kp_int = float_to_uint(kp, KP_MIN, KP_MAX, 12);
    int kd_int = float_to_uint(kd, KD_MIN, KD_MAX, 12);
    int t_int = float_to_uint(t_ff, T_MIN, T_MAX, 12);
    
    uint8_t data[8];
    data[0] = p_int >> 8;                          
    data[1] = p_int & 0xFF;
    data[2] = v_int >> 4;                          
    data[3] = ((v_int & 0xF) << 4) | (kp_int >> 8);
    data[4] = kp_int & 0xFF;                        
    data[5] = kd_int >> 4;                          
    data[6] = ((kd_int & 0xF) << 4) | (t_int >> 8);
    data[7] = t_int & 0xFF;                        
    
    send_can_message(id, data, 8);
}

void receive_can_messages() {
    twai_message_t message;
    while (twai_receive(&message, 0) == ESP_OK) {
        if (message.data_length_code >= 7) {
            uint8_t id = message.data[0];
            int p_int = (message.data[1] << 8) | message.data[2];
            int v_int = (message.data[3] << 4) | (message.data[4] >> 4);
            int t_int = ((message.data[4] & 0xF) << 8) | message.data[5];
            int temp = message.data[6];

            float p = uint_to_float(p_int, P_MIN, P_MAX, 16);
            float v = uint_to_float(v_int, V_MIN, V_MAX, 12);
            float t = uint_to_float(t_int, T_MIN, T_MAX, 12);

            Serial.print("M,");
            Serial.print(id); Serial.print(",");
            Serial.print(p, 2); Serial.print(",");
            Serial.print(v, 2); Serial.print(",");
            Serial.print(t, 2); Serial.print(",");
            Serial.println(temp);
        }
    }
}

void stop_all_actuators() {
    digitalWrite(CYTRON_PWM, LOW);
    digitalWrite(CYTRON_DIR, LOW);
    digitalWrite(UNUSED_IN1, LOW);
    digitalWrite(UNUSED_IN2, LOW);
}

void parse_serial_command(String cmd) {
    int commaIndex1 = cmd.indexOf(',');
    int commaIndex2 = cmd.indexOf(',', commaIndex1 + 1);
    int commaIndex3 = cmd.indexOf(',', commaIndex2 + 1);
    int commaIndex4 = cmd.indexOf(',', commaIndex3 + 1);

    if (commaIndex1 > 0 && commaIndex2 > 0 && commaIndex3 > 0 && commaIndex4 > 0) {
        target_v = cmd.substring(0, commaIndex1).toFloat();
        target_w = cmd.substring(commaIndex1 + 1, commaIndex2).toFloat();
        frame_cmd = cmd.substring(commaIndex2 + 1, commaIndex3).toInt();
        deposit_cmd = cmd.substring(commaIndex3 + 1, commaIndex4).toInt();
        estop = cmd.substring(commaIndex4 + 1).toInt() == 1;
        
        last_cmd_time = millis();
    }
}

// Non-blocking serial line reader
char serial_buf[64];
uint8_t serial_idx = 0;
void read_serial_nonblocking() {
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n') {
            serial_buf[serial_idx] = '\0';
            parse_serial_command(String(serial_buf));
            serial_idx = 0;
        } else if (c != '\r') {
            if (serial_idx < sizeof(serial_buf) - 1) {
                serial_buf[serial_idx++] = c;
            } else {
                serial_idx = 0; // Prevent overflow
            }
        }
    }
}

void setup() {
    Serial.begin(115200);
    
    pinMode(CYTRON_PWM, OUTPUT);
    pinMode(CYTRON_DIR, OUTPUT);
    pinMode(UNUSED_IN1, OUTPUT);
    pinMode(UNUSED_IN2, OUTPUT);
    
    stop_all_actuators();

    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_1MBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    
    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK) {
        twai_start();
    }
    
    delay(1000);
    enter_mit_mode(MOTOR_FL);
    enter_mit_mode(MOTOR_RL);
    enter_mit_mode(MOTOR_FR);
    enter_mit_mode(MOTOR_RR);
    delay(100);
}

void loop() {
    read_serial_nonblocking();
    receive_can_messages();
    unsigned long currentMillis = millis();
    
    if (currentMillis - last_cmd_time > CMD_TIMEOUT_MS) {
        target_v = 0.0;
        target_w = 0.0;
        frame_cmd = 0;
        deposit_cmd = 0;
    }
    
    if (estop) {
        target_v = 0.0;
        target_w = 0.0;
        frame_cmd = 0;
        deposit_cmd = 0;
        stop_all_actuators();
    } else {
        
        // --- BUTTONS A & Y (FRAME CONTROL TO CYTRON) ---
        if (frame_cmd == 1) {             // Button A 
            digitalWrite(CYTRON_PWM, HIGH); // POWER ON
            digitalWrite(CYTRON_DIR, LOW);  // DIR 1
        } else if (frame_cmd == -1) {     // Button Y 
            digitalWrite(CYTRON_PWM, HIGH); // POWER ON (Needed for Cytron!)
            digitalWrite(CYTRON_DIR, HIGH); // DIR 2
        } else {                          
            digitalWrite(CYTRON_PWM, LOW);  // POWER OFF
            digitalWrite(CYTRON_DIR, LOW);
        }

        // --- BUMPERS LB & RB (DUMMY CONTROL FOR EMPTY PINS) ---
        if (deposit_cmd == 1) { 
            digitalWrite(UNUSED_IN1, HIGH);
            digitalWrite(UNUSED_IN2, LOW);
        } else if (deposit_cmd == -1) { 
            digitalWrite(UNUSED_IN1, LOW);
            digitalWrite(UNUSED_IN2, HIGH);
        } else { 
            digitalWrite(UNUSED_IN1, LOW);
            digitalWrite(UNUSED_IN2, LOW);
        }
    }
    
    if (currentMillis - previousMillis >= 10) {
        previousMillis = currentMillis;
        
        float v_left = target_v - (target_w * TRACK_WIDTH / 2.0);
        float v_right = target_v + (target_w * TRACK_WIDTH / 2.0);
        
        float w_left = v_left / WHEEL_RADIUS;
        float w_right = v_right / WHEEL_RADIUS;
        
        w_right = -w_right;
        
        // Command format: Position, Velocity, Kp (stiffness), Kd (damping), Torque
        pack_cmd(MOTOR_FL, 0.0, w_left, 0.0, 2.0, 0.0);
        pack_cmd(MOTOR_RL, 0.0, w_left, 0.0, 2.0, 0.0);
        pack_cmd(MOTOR_FR, 0.0, w_right, 0.0, 2.0, 0.0);
        pack_cmd(MOTOR_RR, 0.0, w_right, 0.0, 2.0, 0.0);
    }
}
