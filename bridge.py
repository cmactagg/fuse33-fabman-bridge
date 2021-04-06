import RPi.GPIO as GPIO
from time import sleep
from mfrc522 import SimpleMFRC522
import MFRC522
from enum import Enum
import _thread
import configparser
import requests
from requests.structures import CaseInsensitiveDict
import signal

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
	ERROR = 6

class BridgeState(Enum):
	ACTIVATING = 1
	ACTIVE = 2
	DEACTIVATING = 3
	DEACTIVE = 4


#blinkTime = 0.5

MIFAREReader = MFRC522.MFRC522()

bridgeState = BridgeState.DEACTIVE
bridgeSessionId = 0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(RED_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)

config = configparser.ConfigParser()
config.read("bridge-config.ini")
print(config["fabman"]["heartbeat-time-sec"])
HEARTBEAT_TIME_SEC = int(config["fabman"]["heartbeat-time-sec"])
print(config["fabman"]["auth-token"])
AUTH_TOKEN = config["fabman"]["auth-token"]

reader = SimpleMFRC522()

continueReading = True

def uidToString(uid):
	mystring = ""
	for i in uid:
		mystring += format(i, '02X')
	return mystring


def end_read(signal, frame):
	global continueReading
	print("Ctrl+C captured, ending read.")
	continueReading = False
	GPIO.cleanup()

signal.signal(signal.SIGINT, end_read)


def stopButtonHandler(channel):
	print("stop button pushed")
	stopMachine()

def doHeartbeat():
	while True:
		print("heartbeat sent")

		url = "https://fabman.io/api/v1/bridge/heartbeat"

		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer 640c6085-8f75-4c87-9619-99a552f1fa55" #use the bridge api key

		data = {
		#"uptime": 0,
		  "configVersion": 0
		}

		resp = requests.post(url, data = data, headers=headers)

		# print request object 
		print(resp.content) 

		sleep(HEARTBEAT_TIME_SEC)



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
	elif ledDisplayState == LedDisplayState.ERROR:
		GPIO.output(GREEN_LED_PIN, GPIO.LOW)
		GPIO.output(RED_LED_PIN, GPIO.LOW)
		blinkLed([GREEN_LED_PIN, RED_LED_PIN], 3, 2)

def activateRelay(activate):
	pinState = GPIO.HIGH

	if activate:
		pinState = GPIO.LOW
	else:
		pinState = GPIO.HIGH

	GPIO.output(RELAY_PIN, pinState)


def startMachineFabmanApi(rfid):
	try:
		url = "https://fabman.io/api/v1/bridge/access"

		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer 640c6085-8f75-4c87-9619-99a552f1fa55" #use the bridge api key

		data = {
		  #"member": 224972,
		  #"emailAddress":  "mtags22@gmail.com",
		  "keys": [ { "type": "nfca", "token": rfid } ],
		  "configVersion": 0
		}
		resp = requests.post(url, json = data, headers=headers)

		respContent = resp.json()

		print(respContent)

		global bridgeSessionId
		bridgeSessionId = respContent['sessionId']

		print(bridgeSessionId)
		# print request object 
	except Exception as e:
		print("Error calling Access")

def stopMachineFabmanApi():
	#import json
	#from io import StringIO

	url = "https://fabman.io/api/v1/bridge/stop"

	headers = CaseInsensitiveDict()
	headers["Accept"] = "application/json"
	headers["Authorization"] = "Bearer 640c6085-8f75-4c87-9619-99a552f1fa55" #use the bridge api key
	global bridgeSessionId
	print(bridgeSessionId)

	dataStop = { "stopType": "normal", "currentSession": { "id": bridgeSessionId } }

	resp = requests.post(url, json = dataStop, headers=headers)
    
	# print request object 
	print(resp.content) 
	bridgeSessionId = 0


def startMachine(rfid):
	displayLedState(LedDisplayState.THINKING)
	displayLedState(LedDisplayState.AUTH_PASS)
	print("starting machine")
	startMachineFabmanApi(rfid)
	print("machine started")
	displayLedState(LedDisplayState.ACTIVE)
	#GPIO.output(RELAY_PIN, GPIO.LOW)
	activateRelay(True)
def stopMachine():
	displayLedState(LedDisplayState.DEACTIVE)
	print("stopping machine")
	stopMachineFabmanApi()
	print("machine stopped")
	#GPIO.output(RELAY_PIN, GPIO.HIGH)
	activateRelay(False)

try:
	GPIO.add_event_detect(STOP_BUTTON_PIN, GPIO.RISING, callback=stopButtonHandler)
	startHeartbeatThread()

	#while True:
		#print("read to read...")
		#id, text = reader.read()
		#print(id)
		#print(text)
		#startMachine()
		#while True:
			#if GPIO.input(STOP_BUTTON_PIN) == GPIO.HIGH:
				#stopMachine()
				#break
		#sleep(.25)



	while continueReading:

		# Scan for cards
		(status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)

		# If a card is found
		if status == MIFAREReader.MI_OK:
			print ("Card detected")

			# Get the UID of the card
			(status, uid) = MIFAREReader.MFRC522_SelectTagSN()
			# If we have the UID, continue
			if status == MIFAREReader.MI_OK:
				uid_string = uidToString(uid)
				print("Card read UID: %s" % uid_string)
				startMachine(uid_string)
				
			else:
				print("Error reading card")



finally:
	GPIO.cleanup()


