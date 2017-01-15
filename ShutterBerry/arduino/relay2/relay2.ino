
#include <SPI.h>
#include <nRF24L01.h>
#include <printf.h>
#include <RF24.h>
#include <RF24_config.h>

RF24 radio(9,10);

int buttonState = LOW;
int mode = 2; //0 = auto, 1 = on, 2 = off
String StrMode = "OFF";

const int myDelay = 500 ;
const int buttonPin = 17;
const int autoLed = 14;
const int onLed = 15;
const int offLed = 16;  
const int relay = 2; 
             
void setup(void)

{    

  radio.begin() ;
  radio.setPALevel(RF24_PA_MAX) ;
  radio.setChannel(0x76);
  radio.openWritingPipe(0xF0F0F0F0E2LL) ;
  const uint64_t pipe = 0xE8E8F0F0E2LL ;
  radio.openReadingPipe(1, pipe) ;
  radio.enableDynamicPayloads() ;
  radio.powerUp() ;
  radio.setDataRate(RF24_250KBPS) ;

  Serial.begin(9600);

  //Set Relay
  pinMode(relay, OUTPUT);
  digitalWrite(relay, LOW);
  
  //Set and Test the LEDs
  pinMode(autoLed, OUTPUT);       
  pinMode(onLed, OUTPUT);
  pinMode(offLed, OUTPUT);
  
  digitalWrite(autoLed, HIGH);
  digitalWrite(onLed, HIGH);
  digitalWrite(offLed, HIGH);
  delay(1000);
  digitalWrite(autoLed, LOW);
  digitalWrite(onLed, LOW);
  digitalWrite(offLed, LOW);
  delay(1000);
  
  //A3 used for the Button
  pinMode(buttonPin, INPUT); 
  
  ModeChange();

}

  void loop(void)

{
   
   radio.startListening() ;
   char receivedMessage[8] = {0} ;
   
   if (radio.available()){
      radio.read(receivedMessage, sizeof(receivedMessage)) ;
      radio.stopListening() ;
      //SPI.write(0xE2);
  
      Serial.println("Received Message");
      
      String stringMessage(receivedMessage) ;
      Serial.println(stringMessage);
      
      delay(250);
      
      //if message = mode, perform the mode change and write message
      if (stringMessage == "mode" || stringMessage == "status"){
        if (stringMessage == "mode"){  
          ModeChange(); 
        }
      if (mode == 0){
          char text[] = "AUTO";
          radio.write(text, sizeof(text));
          Serial.println("writing auto");  
          }       
      if (mode == 1){
          char text[] = "ON";
          radio.write(text, sizeof(text));
          Serial.println("writing on"); 
          }
      if (mode == 2){
          char text[] = "OFF";
          radio.write(text, sizeof(text));
          Serial.println("writing off"); 
        }
      }
    //if message = ON, check the mode and switch on if necessary
    if (stringMessage == "ON" && mode == 0){
          char text[] = "SON";
          radio.write(text, sizeof(text));
          Serial.println("writing son"); 
          digitalWrite(relay, LOW);
    }
    
   if (stringMessage == "OFF" && mode == 0){
          char text[] = "SOFF";
          radio.write(text, sizeof(text));
          Serial.println("writing soff"); 
          digitalWrite(relay, HIGH);
    }
      
   }
  
  // read the state of the pushbutton value:
  buttonState = digitalRead(buttonPin);
  if (buttonState == HIGH) {
    ModeChange();
  }
   

}

void ModeChange() {

  mode = (mode + 1) % 3;
    String mode_message = "mode = " + String(mode); 
    Serial.println(mode_message);
    delay(250);
  
  
  if (mode == 0) {

    digitalWrite(autoLed, HIGH);
    digitalWrite(onLed, LOW);
    digitalWrite(offLed, LOW);
  }
  if (mode == 1) {
  
    digitalWrite(autoLed, LOW);
    digitalWrite(onLed, HIGH);
    digitalWrite(offLed, LOW);
    digitalWrite(relay, LOW);
  }
  if (mode == 2) {
   
    digitalWrite(autoLed, LOW);
    digitalWrite(onLed, LOW);
    digitalWrite(offLed, HIGH);
    digitalWrite(relay, HIGH);
  }
  
}
