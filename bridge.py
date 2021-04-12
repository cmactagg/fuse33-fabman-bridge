import RPi.GPIO as GPIO
from time import sleep
import time
from mfrc522 import SimpleMFRC522
import MFRC522
from enum import Enum
import _thread
import configparser
import requests
from requests.structures import CaseInsensitiveDict
import signal
import logging
import sys
import json

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


logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG) # CRITICAL, ERROR, WARNING, INFO, DEBUG

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
bridgeConfigFileName = "bridge-config.ini"
config.read(bridgeConfigFileName)
print(config["fabman"]["heartbeat-time-sec"])
HEARTBEAT_TIME_SEC = int(config["fabman"]["heartbeat-time-sec"])
print(config["fabman"]["auth-token"])
AUTH_TOKEN = config["fabman"]["auth-token"]
API_URL = config["fabman"]["api-url"]


reader = SimpleMFRC522()

continueReading = True



def saveConfig(bridgeConfigId):
	config.set("fabman", "bridgeConfigId", str(bridgeConfigId))

	global bridgeConfigFileName
	# save to a file
	with open(bridgeConfigFileName, 'w') as configfile:
		config.write(configfile)


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
	global API_URL
	global AUTH_TOKEN
	global config

	while True:
		logging.debug("heartbeat sent")
		
		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer " + AUTH_TOKEN #use the bridge api key

		data = {
		#"uptime": 0,
		  "configVersion": config["fabman"]["bridgeConfigId"]
		}

		logging.debug("Heartbeat sent")
		resp = requests.post(API_URL + "/bridge/heartbeat", data = data, headers=headers)

		# print request object
		logging.debug(resp.content)

		if resp.status_code == 200:
			response = json.loads(resp.content.decode('utf-8'))
			if response["config"] != None:
				saveConfig(response["config"]["configVersion"])
			logging.debug("Heartbeat success")
		else:
			logging.warning("Heartbeat failed")

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
		logging.debug("blink")
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

	logging.debug('activating relay ' + str(activate))
	pinState = GPIO.HIGH

	if activate:
		pinState = GPIO.LOW
	else:
		pinState = GPIO.HIGH

	GPIO.output(RELAY_PIN, pinState)


def doMachineStopTimer(machineOnForSec):
	machineEndTime = time.time() + machineOnForSec
	doStopMachine = False
	while not doStopMachine:
		logging.debug('checking machine stop ' + str(machineOnForSec))
		if time.time() > machineEndTime:
			doStopMachine = True
			stopMachine()
		sleep(1) #check every second

def startMachineStopThread(machineOnForSec):
	_thread.start_new_thread(doMachineStopTimer, (machineOnForSec,))


def startMachineFabmanApi(rfid):
	global API_URL
	global AUTH_TOKEN
	global config

	allowAccess = False
	try:
		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer " + AUTH_TOKEN #use the bridge api key

		data = {
		  #"member": 224972,
		  #"emailAddress":  "abc@123.com",
		  "keys": [ { "type": "nfca", "token": rfid } ],
		  "configVersion": config["fabman"]["bridgeConfigId"]
		}
		resp = requests.post(API_URL + "/bridge/access", json = data, headers = headers)

		jsonResp = json.loads(resp.content.decode('utf-8'))

		logging.debug(jsonResp)

		accessType = jsonResp['type']

		logging.debug('accessType ' + accessType)

		if (resp.status_code == 200 and accessType == "allowed"):
			respContent = resp.json()

			global bridgeSessionId
			bridgeSessionId = respContent['sessionId']
			allowAccess = True
			logging.debug(bridgeSessionId)
			machineOnForSec = respContent['maxDuration']
			if machineOnForSec != None:
				startMachineStopThread(machineOnForSec)
		else:
			respMessages = jsonResp['messages']
			logging.warning(respMessages)
			logging.warning('Bridge could not be started (rfid: ' + str(rfid) + ')')

	except Exception as e:
		print(e)
		print("Error calling Access")

	return allowAccess

def stopMachineFabmanApi():
	global API_URL
	global AUTH_TOKEN
	global config

	allowStop = False

	headers = CaseInsensitiveDict()
	headers["Accept"] = "application/json"
	headers["Authorization"] = "Bearer " + AUTH_TOKEN #use the bridge api key
	global bridgeSessionId
	logging.debug(bridgeSessionId)

	dataStop = { "stopType": "normal", "currentSession": { "id": bridgeSessionId } }

	resp = requests.post(API_URL + "/bridge/stop", json = dataStop, headers = headers)

	logging.debug(resp.content)

	if resp.status_code == 200 or resp.status_code == 204:
		#self.session_id = None
		bridgeSessionId = 0
		allowStop = True
		logging.info('Bridge stopped successfully.')
	else:
		logging.error('Bridge could not be stopped (status code ' + str(resp.status_code) + ')')

	# print request object 
	print(resp.content) 

	return allowStop

def startMachine(rfid):

	global bridgeSessionId
	if bridgeSessionId != 0:
		stopMachine()


	displayLedState(LedDisplayState.THINKING)
	displayLedState(LedDisplayState.AUTH_PASS)
	logging.info("starting machine")
	if startMachineFabmanApi(rfid):
		logging.info("machine started")
		displayLedState(LedDisplayState.ACTIVE)
		#GPIO.output(RELAY_PIN, GPIO.LOW)
		activateRelay(True)
	else:
		displayLedState(LedDisplayState.ERROR)
		displayLedState(LedDisplayState.DEACTIVE)
		
def stopMachine():
	displayLedState(LedDisplayState.DEACTIVE)
	logging.info("stopping machine")
	if stopMachineFabmanApi():
		logging.info("machine stopped")
		activateRelay(False)
	else:
		displayLedState(LedDisplayState.ERROR)


try:
	GPIO.add_event_detect(STOP_BUTTON_PIN, GPIO.RISING, callback=stopButtonHandler)
	startHeartbeatThread()


	while continueReading:

		# Scan for cards
		(status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)
		#logging.info(TagType)
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


