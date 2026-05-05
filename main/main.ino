#include <Arduino.h>

/*
// PINS
// BTS7960 -> extension/retraction motor - J6
#define EXTEND_RPWM  19    // GP2
#define EXTEND_LPWM  18    // GP3
#define EXTEND_R_EN  39    // GP4
#define EXTEND_L_EN  39    // GP5

// BTS7960 -> tilt motor - J7
#define TILT_RPWM    20   // GP6
#define TILT_LPWM    21    // GP7
#define TILT_R_EN    39   // GP8
#define TILT_L_EN    39    // GP9

// TB6612 -> left wheels
#define L_IN1  10         // GP10
#define L_IN2  11         // GP11
#define L_PWM  12         // GP12

// TB6612 -> right wheels
#define R_IN1  13         // GP13
#define R_IN2  14         // GP14
#define R_PWM  15         // GP15

#define STBY   22         // GP22

// Sensors / IO
#define TILT_LIMIT_SWITCH  17   // GP17
#define START_BUTTON       15   // GP15
#define COMPLETE_LED       12   // GP12


// sensors
#define TILT_LIMIT_SWITCH 21  // stops tilt when detected
#define ZONE_DISTANCE_MM 100  // distance the ToF detects
#define HOPPER_DISTANCE_MM 100

// motor duration and speed
#define EXTENSION_SPEED 200 // 0 - 255, motor speed -> starting low and increasing
#define EXTENSION_DURATION 4000 // in ms -> how long the extension runs for

#define RETRACTION_SPEED 200
#define RETRACTION_DURATION 4000

#define TILT_SPEED 200
#define TILT_UP_DURATION 4000
#define TILT_DOWN_DURATION 4000

// FLAGS - state control
volatile bool running = false;
volatile bool complete = false;

// VL53L0X sensor object from pololu library
VL53L0X tof_sensor;


// BUTTON CODE
void check_button_press(){
  // if button PRESSED -> start LOOP
  // button press = LOW, not pressed = HIGH -> depends on PULLUP (GND OR 3.3V)
  // pico holds HIGH internally so not pressed is HIGH
  while (digitalRead(START_BUTTON) == HIGH){
    delay(10); // checks for button press every 10ms
  }
  running = true; // starts system
  Serial.println("start button pressed, system ON");
}



// SENSOR CODE
void downwards_sensor(){
  while (digitalRead(TILT_LIMIT_SWITCH) == HIGH){
    delay(5);
    // checks every 5ms
  }
  // when switch hits, turn motors OFF
  analogWrite(TILT_RPWM, 0);
  analogWrite(TILT_LPWM, 0);
  Serial.println("limit switch hit !");
}

void hopper_lip_sensor(){
  while (true) {
    int distance = tof_sensor.readRangeContinuousMillimeters();
      if (tof_sensor.timeoutOccurred()){
        continue;
}
Serial.print("hopper ToF distance: ");
Serial.print(distance);
Serial.println("mm");
if (distance < HOPPER_DISTANCE_MM){
  // hopper detected -> stop motors
  analogWrite(EXTEND_RPWM, 0);
  Serial.println("hopper detected !");
  break;
  }
delay(10);
  }
}

void dump_zone_lip_sensor(){
while (true) {
    int distance = tof_sensor.readRangeContinuousMillimeters();
      if (tof_sensor.timeoutOccurred()){
        continue;
      }
Serial.print("dump zone ToF distance: ");
Serial.print(distance);
Serial.println("mm");
if (distance < ZONE_DISTANCE_MM){
  // dump zone detected -> stop motors
  analogWrite(EXTEND_RPWM, 0);
  Serial.println("dump zone detected !");
  break;
  }
delay(10);
}
}

void time_of_flight(){
// intialise VL53L0X over I2C
  Wire.begin();
  if (!tof_sensor.init()){
    while (true){}
  }
  tof_sensor.setTimeout(500);
  tof_sensor.startContinuous();
  // sensor keeps measuring continuously
  Serial.println("VL53L0X initialised !");
}


// MOVEMENT FUNCTIONS
// move robot forward
void move_forward() {
  digitalWrite(L_IN1, HIGH);   // left wheels forward
  digitalWrite(L_IN2, LOW);    // needs L_IN1 HIGH and L_IN2 LOW to move left wheels foward
  digitalWrite(R_IN1, HIGH);   // right wheels forward
  digitalWrite(R_IN2, LOW);    // needs R_IN1 HIGH and R_IN2 LOW to move right wheels foward

  analogWrite(L_PWM, 200);     // speed control (0-255)
  analogWrite(R_PWM, 200);
}

// move backwards
void move_backwards() {
  digitalWrite(L_IN1, LOW);   // left backwards
  digitalWrite(L_IN2, HIGH);
  digitalWrite(R_IN1, LOW);   // right backwards
  digitalWrite(R_IN2, HIGH);

  analogWrite(L_PWM, 200);     // speed control (0-255)
  analogWrite(R_PWM, 200);
}

// turn left
void turn_left() {
  digitalWrite(L_IN1, LOW);    // left backwards
  digitalWrite(L_IN2, HIGH);
  digitalWrite(R_IN1, HIGH);   // right forwards
  digitalWrite(R_IN2, LOW);

  analogWrite(L_PWM, 200);
  analogWrite(R_PWM, 200);
}

// turn right
void turn_right() {
  digitalWrite(L_IN1, HIGH);   // left foward
  digitalWrite(L_IN2, LOW);
  digitalWrite(R_IN1, LOW);   // right backwards
  digitalWrite(R_IN2, HIGH);

  analogWrite(L_PWM, 200);
  analogWrite(R_PWM, 200);
}

// stop all wheels
void stop_motors() {
  digitalWrite(L_IN1, LOW);
  digitalWrite(L_IN2, LOW);
  digitalWrite(R_IN1, LOW);
  digitalWrite(R_IN2, LOW);

  analogWrite(L_PWM, 0);
  analogWrite(R_PWM, 0);
}

// ARM MOVEMENT FUNCTIONS
void extension(){
  analogWrite(EXTEND_RPWM, EXTENSION_SPEED);
  analogWrite(EXTEND_LPWM, 0);
  dump_zone_lip_sensor();
  Serial.println("arm extension complete !");
}

void extension_to_hopper(){
  analogWrite(EXTEND_RPWM, EXTENSION_SPEED);
  analogWrite(EXTEND_LPWM, 0);
  hopper_lip_sensor();
  Serial.println("arm extension to hopper complete !");
}

void retraction(){
  analogWrite(EXTEND_RPWM, 0);
  analogWrite(EXTEND_LPWM, RETRACTION_SPEED);
  delay(RETRACTION_DURATION);    // timed — no sensor on retraction
  analogWrite(EXTEND_LPWM, 0);
  Serial.println("arm retraction complete !");
}

void upwards(){
  analogWrite(TILT_RPWM, TILT_SPEED);
  analogWrite(TILT_LPWM, 0);
  delay(TILT_UP_DURATION);       // timed
  analogWrite(TILT_RPWM, 0);
  Serial.println("arm moved upwards !");
}

void downwards(){
  analogWrite(TILT_RPWM, 0);
  analogWrite(TILT_LPWM, TILT_SPEED);
  downwards_sensor();
  Serial.println("arm moved downwards !");
}

void setup(){
Serial.begin(9600); // start serial communication

// extension motor outputs (pico controls)
pinMode(EXTEND_RPWM, OUTPUT);
pinMode(EXTEND_LPWM, OUTPUT);
pinMode(EXTEND_R_EN, OUTPUT);  digitalWrite(EXTEND_R_EN, HIGH);
pinMode(EXTEND_L_EN, OUTPUT);  digitalWrite(EXTEND_L_EN, HIGH);

// tilt motor outputs (pico controls)
pinMode(TILT_RPWM, OUTPUT);
pinMode(TILT_LPWM, OUTPUT);
pinMode(TILT_R_EN, OUTPUT); digitalWrite(TILT_R_EN, HIGH);
pinMode(TILT_L_EN, OUTPUT); digitalWrite(TILT_L_EN, HIGH);

// wheel motor pins
pinMode(L_IN1, OUTPUT);
pinMode(L_IN2, OUTPUT);
pinMode(L_PWM, OUTPUT);
pinMode(R_IN1, OUTPUT);
pinMode(R_IN2, OUTPUT);
pinMode(R_PWM, OUTPUT);

pinMode(STBY, OUTPUT);
digitalWrite(STBY, HIGH); // enable motor driver

// sensors
pinMode(TILT_LIMIT_SWITCH, INPUT_PULLUP);
time_of_flight();

pinMode(LED_BUILTIN, OUTPUT);

// LED is an output, start button -> HIGH by default
pinMode(COMPLETE_LED, OUTPUT);
pinMode(START_BUTTON, INPUT_PULLUP);

// LED OFF at start
digitalWrite(COMPLETE_LED, LOW);
// print output
Serial.println("system initalised");
// BLOCK until button is pressed, then start LOOP
check_button_press();
}

// MAIN ROBOT LOGIC
void active_loop(){
  if (running && !complete){
    // CALL IN ORDER NEEDED -> adjust later

    extension(); // ToF sensor to dump zone
    downwards(); // tilt down -> limit switch
    upwards(); // tilt back to desired angle (timed)
    upwards(); // second tilt if needed

    move_forward();
    delay(3000);
    stop_motors();

    turn_left();
    delay(2000);
    stop_motors();

    extension_to_hopper(); // ToF sensor
    retraction(); // timed

    turn_right();
    delay(2000);
    stop_motors();

    move_backwards();
    delay(3000);
    stop_motors();

    // built in LED on HIGH
    digitalWrite(LED_BUILTIN, HIGH);

    // mark as done
    complete = true;
    running = false;
    // activate LED
    digitalWrite(COMPLETE_LED, HIGH);
    Serial.println("system complete !");
  }
}

void loop(){
  active_loop(); // continuously check if robot should run
}


*/




// ------- TESTING ------------------------------------------------

// BTS7960 -> extension motor
#define EXTEND_RPWM  19
#define EXTEND_LPWM  18
#define EXTEND_R_EN  39
#define EXTEND_L_EN  39

// BTS7960 -> tilt motor
#define TILT_RPWM    21
#define TILT_LPWM    20
#define TILT_R_EN    39
#define TILT_L_EN    39

// dont send pwm on both channels at once -> apply a bit of enable break

#define TILT_SPEED        75
#define TILT_UP_DURATION  50

// LEFT BTS7960 (left wheels) - J5
#define L_RPWM 7
#define L_LPWM 6
#define L_EN   39

// RIGHT BTS7960 (right wheels) - J7
#define R_RPWM 5
#define R_LPWM 4
#define R_EN   39

#define WHEEL_SPEED 255  // 100% duty cycle


void downwards_sensor() {
  delay(2000);
}

void upwards() {
  Serial.println("tilting up...");
  analogWrite(TILT_RPWM, TILT_SPEED);
  analogWrite(TILT_LPWM, 0);
  delay(TILT_UP_DURATION);

  // enable brake - both HIGH locks the motor in place
  digitalWrite(TILT_RPWM, HIGH);
  digitalWrite(TILT_LPWM, HIGH);

  Serial.println("arm moved upwards - brake applied !");
}

void downwards() {
  Serial.println("tilting down...");

  // release brake first
  digitalWrite(TILT_RPWM, LOW);
  digitalWrite(TILT_LPWM, LOW);
  delay(10);

  analogWrite(TILT_RPWM, 0);
  analogWrite(TILT_LPWM, TILT_SPEED);
  downwards_sensor();
  analogWrite(TILT_RPWM, 0);
  analogWrite(TILT_LPWM, 0);
  Serial.println("arm moved downwards !");
}

// wheel helpers
void set_left(int speed) {
  speed = constrain(speed, -255, 255);
  if (speed > 0) {
    analogWrite(L_RPWM, speed);
    analogWrite(L_LPWM, 0);
  } else if (speed < 0) {
    analogWrite(L_RPWM, 0);
    analogWrite(L_LPWM, -speed);
  } else {
    analogWrite(L_RPWM, 0);
    analogWrite(L_LPWM, 0);
  }
}

void set_right(int speed) {
  speed = constrain(speed, -255, 255);
  if (speed > 0) {
    analogWrite(R_RPWM, speed);
    analogWrite(R_LPWM, 0);
  } else if (speed < 0) {
    analogWrite(R_RPWM, 0);
    analogWrite(R_LPWM, -speed);
  } else {
    analogWrite(R_RPWM, 0);
    analogWrite(R_LPWM, 0);
  }
}

void move_forward() {
  set_left(WHEEL_SPEED);
  set_right(WHEEL_SPEED);
}

void move_backwards() {
  set_left(-WHEEL_SPEED);
  set_right(-WHEEL_SPEED);
}

void stop_motors() {
  set_left(0);
  set_right(0);
}


void setup() {
  Serial.begin(9600);

  // extension motor
  pinMode(EXTEND_RPWM, OUTPUT);
  pinMode(EXTEND_LPWM, OUTPUT);
  pinMode(EXTEND_R_EN, OUTPUT);  digitalWrite(EXTEND_R_EN, HIGH);
  pinMode(EXTEND_L_EN, OUTPUT);  digitalWrite(EXTEND_L_EN, HIGH);

  // tilt motor
  pinMode(TILT_RPWM, OUTPUT);
  pinMode(TILT_LPWM, OUTPUT);
  pinMode(TILT_R_EN, OUTPUT);  digitalWrite(TILT_R_EN, HIGH);
  pinMode(TILT_L_EN, OUTPUT);  digitalWrite(TILT_L_EN, HIGH);

  delay(100);

  // wheels - safe state before enabling
  pinMode(L_RPWM, OUTPUT);
  pinMode(L_LPWM, OUTPUT);
  pinMode(R_RPWM, OUTPUT);
  pinMode(R_LPWM, OUTPUT);

  digitalWrite(L_RPWM, LOW);
  digitalWrite(L_LPWM, LOW);
  digitalWrite(R_RPWM, LOW);
  digitalWrite(R_LPWM, LOW);

  // enable wheel drivers
  pinMode(L_EN, OUTPUT);  digitalWrite(L_EN, HIGH);
  pinMode(R_EN, OUTPUT);  digitalWrite(R_EN, HIGH);

  delay(500);

  Serial.println("system initialised");
}

void loop() {
  Serial.println("moving forward...");
  move_forward();
  delay(2000);

  stop_motors();
  delay(100);

  Serial.println("moving backwards...");
  move_backwards();
  delay(2000);

  stop_motors();
  delay(100);
}
