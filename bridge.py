import RPi.GPIO as GPIO
from time import sleep
from mfrc522 import SimpleMFRC522
from enum import Enum
import _thread

STOP_BUTTON_PIN = 10
GREEN_LED_PIN = 8
RED_LED_PIN = 12
RELAY_PIN = 7

class LedDisplayState(Enum):
	ACTIVE = 1
	DEACTIVE = 2
	AUTH_PASS = 3
	AUTH_FAIL = 4
	THINKING = 5

class MachineState(Enum):
	ACTIVATING = 1
	ACTIVE = 2
	DEACTIVATING = 3
	DEACTIVE = 4


blinkTime = 0.5

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(RED_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)



reader = SimpleMFRC522()

def stopButtonHandler(channel):
	print("stop button pushed")
	stopMachine()

def doHeartbeat():
	while True:
		print("heartbeat sent")
		sleep(5)

def startHeartbeatThread():
	_thread.start_new_thread(doHeartbeat, ())


def blinkLed(pins, iterations = 3, blinkSec = .5):
	iterationCounter = 0
	lowHigh = GPIO.LOW
	while iterationCounter < iterations * 2:
		for pin in pins:
			GPIO.output(pin, lowHigh)
		iterationCounter += 1
		lowHigh = GPIO.LOW if lowHigh == GPIO.HIGH else GPIO.HIGH
		print("blink")
		sleep(blinkSec)



def displayLedState(ledDisplayState):
	if ledDisplayState == LedDisplayState.ACTIVE:
		GPIO.output(RED_LED_PIN, GPIO.LOW)
		GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
	elif ledDisplayState == LedDisplayState.DEACTIVE:
		GPIO.output(GREEN_LED_PIN, GPIO.LOW)
		GPIO.output(RED_LED_PIN, GPIO.HIGH)
	elif ledDisplayState == LedDisplayState.AUTH_PASS:
		GPIO.output(RED_LED_PIN, GPIO.LOW)
		blinkLed([GREEN_LED_PIN])
	elif ledDisplayState == LedDisplayState.AUTH_FAIL:
		GPIO.output(GREEN_LED_PIN, GPIO.LOW)
		blinkLed([RED_LED_PIN])
	elif ledDisplayState == LedDisplayState.THINKING:
		GPIO.output(GREEN_LED_PIN, GPIO.LOW)
		GPIO.output(RED_LED_PIN, GPIO.LOW)
		blinkLed([GREEN_LED_PIN, RED_LED_PIN])

def activateRelay(activate):
	pinState = GPIO.HIGH

	if activate:
		pinState = GPIO.LOW
	else:
		pinState = GPIO.HIGH

	GPIO.output(RELAY_PIN, pinState)


def startMachine():
	displayLedState(LedDisplayState.THINKING)
	displayLedState(LedDisplayState.AUTH_PASS)
	print("starting machine")
	print("machine started")
	displayLedState(LedDisplayState.ACTIVE)
	#GPIO.output(RELAY_PIN, GPIO.LOW)
	activateRelay(True)
def stopMachine():
	displayLedState(LedDisplayState.DEACTIVE)
	print("stopping machine")
	#GPIO.output(RELAY_PIN, GPIO.HIGH)
	activateRelay(False)

try:
	GPIO.add_event_detect(STOP_BUTTON_PIN, GPIO.RISING, callback=stopButtonHandler)
	startHeartbeatThread()

	while True:
		print("read to read...")
		id, text = reader.read()
		print(id)
		print(text)
		startMachine()
#		while True:
#			if GPIO.input(STOP_BUTTON_PIN) == GPIO.HIGH:
#				stopMachine()
#				break
		sleep(.25)

finally:
	GPIO.cleanup()


