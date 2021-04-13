import RPi.GPIO as GPIO
from time import sleep
import time
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

class LedDisplayStateEnum(Enum):
	ACTIVE = 1
	INACTIVE = 2
	ACTIVATE_ALLOWED = 3
	ACTIVATE_DENIED = 4
	ACTIVATE_FAILED = 5
	CHECK_IN_OUT_FAILED = 6
	OFFLINE = 7
	ERROR = 8
	THINKING = 9

class BridgeState():
	def __init__(self):
		self.isBridgeEnabled = True
		self.isActive = False
		self.isOnline = False
		self.ledDisplayState = LedDisplayStateEnum.ERROR
		self.bridgeSessionId = 0
		self.heartbeatConsecutiveFailures = 0
		self.configVersion = 0
		self.bridgeName = ""
		self.bridgeType = ""
		self.heartbeatTimeSec = 5 #this will quickly be overwritten
		self.authToken = ""
		self.apiUrl = ""


logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG) # CRITICAL, ERROR, WARNING, INFO, DEBUG

MIFAREReader = MFRC522.MFRC522()

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(RED_LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)

config = configparser.ConfigParser()
bridgeConfigFileName = "bridge-config.ini"
config.read(bridgeConfigFileName)

#print(config["fabman"]["heartbeat-time-sec"])
#HEARTBEAT_TIME_SEC = int(config["fabman"]["heartbeat-time-sec"])
#print(config["fabman"]["auth-token"])
#AUTH_TOKEN = config["fabman"]["auth-token"]
#API_URL = config["fabman"]["api-url"]



bridgeState = BridgeState()
bridgeState.heartbeatTimeSec = int(config["fabman"]["heartbeat-time-sec"])
bridgeState.authToken = config["fabman"]["auth-token"]
bridgeState.apiUrl = config["fabman"]["api-url"]




#def saveConfig(bridgeConfigId):
#	config.set("fabman", "bridgeConfigId", str(bridgeConfigId))

#	global bridgeConfigFileName
#	# save to a file
#	with open(bridgeConfigFileName, 'w') as configfile:
#		config.write(configfile)


def uidToString(uid):
	mystring = ""
	for i in uid:
		mystring += format(i, '02X')
	return mystring


def disableBridge(signal, frame):
	global bridgeState
	print("Ctrl+C captured, ending read.")
	bridgeState.isBridgeEnabled = False
	GPIO.cleanup()

signal.signal(signal.SIGINT, disableBridge)


def stopButtonHandler(channel):
	print("stop button pushed")
	stopMachine()

def doHeartbeat():
	global bridgeState
#	global API_URL
#	global AUTH_TOKEN
#	global config

	while True:
		logging.debug("heartbeat sent")
		
		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer " + bridgeState.authToken #use the bridge api key

		data = {
		#"uptime": 0,
		  "configVersion": bridgeState.configVersion
		}

		logging.debug("Heartbeat sent")
		resp = requests.post(bridgeState.apiUrl + "/bridge/heartbeat", data = data, headers = headers)

		# print request object
		logging.debug(resp.content)

		if resp.status_code == 200:
			response = json.loads(resp.content.decode('utf-8'))
			if response["config"] != None:
				bridgeState.configVersion = response["config"]["configVersion"]
				bridgeState.bridgeName = response["config"]["name"]
				bridgeState.bridgeType = response["config"]["controlType"] 
				#saveConfig(response["config"]["configVersion"])
			logging.debug("Heartbeat success")
			bridgeState.isOnline = True
			bridgeState.heartbeatConsecutiveFailures = 0
		else:
			logging.warning("Heartbeat failed")
			bridgeState.heartbeatConsecutiveFailurest += 1
			if bridgeState.heartbeatConsecutiveFailures >= 3:
				bridgeState.isOnline = False

		sleep(bridgeState.heartbeatTimeSec)


def doLedDisplay():
	global bridgeState

	previousLedDisplayState = None

	while bridgeState.isBridgeEnabled:
		ledDisplayState = bridgeState.ledDisplayState
		if ledDisplayState != previousLedDisplayState:
			logging.debug('led display state ' + str(ledDisplayState))
			previousLedDisplayState = ledDisplayState
		GPIO.output(RED_LED_PIN, GPIO.LOW)
		GPIO.output(GREEN_LED_PIN, GPIO.LOW)

		if ledDisplayState == LedDisplayStateEnum.ACTIVE:
			GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
			sleep(.5)
		elif ledDisplayState == LedDisplayStateEnum.INACTIVE:
			GPIO.output(RED_LED_PIN, GPIO.HIGH)
			sleep(.5)
		elif ledDisplayState == LedDisplayStateEnum.ACTIVATE_ALLOWED:
			for i in range(0, 10):				
				GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
				sleep(.1)
				GPIO.output(GREEN_LED_PIN, GPIO.LOW)
				sleep(.1)

		elif ledDisplayState == LedDisplayStateEnum.ACTIVATE_DENIED:
			for i in range(0, 10):				
				GPIO.output(RED_LED_PIN, GPIO.HIGH)
				sleep(.1)
				GPIO.output(RED_LED_PIN, GPIO.LOW)
				sleep(.1)
		elif (ledDisplayState == LedDisplayStateEnum.ACTIVATE_FAILED
			or ledDisplayState == LedDisplayStateEnum.CHECK_IN_OUT_FAILED
			or ledDisplayState == LedDisplayStateEnum.ERROR):
			for i in range(0, 10):			
				GPIO.output(RED_LED_PIN, GPIO.HIGH)
				GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
				sleep(.1)
				GPIO.output(RED_LED_PIN, GPIO.LOW)
				GPIO.output(GREEN_LED_PIN, GPIO.LOW)
				sleep(.1)

		elif ledDisplayState == LedDisplayStateEnum.OFFLINE:
			GPIO.output(RED_LED_PIN, GPIO.HIGH)
			GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
			sleep(.25)
			GPIO.output(RED_LED_PIN, GPIO.LOW)
			GPIO.output(GREEN_LED_PIN, GPIO.LOW)
			sleep(.75)

		elif ledDisplayState == LedDisplayStateEnum.THINKING:
			GPIO.output(GREEN_LED_PIN, GPIO.LOW)
			GPIO.output(RED_LED_PIN, GPIO.HIGH)
			sleep(.1)
			GPIO.output(RED_LED_PIN, GPIO.LOW)
			GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
			sleep(.1)

def startLedThread():
	_thread.start_new_thread(doLedDisplay, ())
	s = 5


def startHeartbeatThread():
	_thread.start_new_thread(doHeartbeat, ())


def activateRelay(activate):

	logging.debug('activating relay ' + str(activate))
	pinState = GPIO.HIGH

	if activate:
		pinState = GPIO.LOW
	else:
		pinState = GPIO.HIGH

	GPIO.output(RELAY_PIN, pinState)


def doMachineStopTimer(machineOnForSec):
	global bridgeState
	
	machineEndTime = time.time() + machineOnForSec
	doStopMachine = False
	while not doStopMachine:
		logging.debug('checking machine stop ' + str(machineOnForSec))
		if time.time() > machineEndTime:
			doStopMachine = True
			stopMachine()
		elif bridgeState.isActive == False:
			doStopMachine = True
		sleep(.5) #check every half second

def startMachineStopThread(machineOnForSec):
	_thread.start_new_thread(doMachineStopTimer, (machineOnForSec,))


def startMachine(rfid):

	global bridgeState
        
	if bridgeState.isActive == True and bridgeSessionId != 0:
                stopMachine()


	bridgeState.ledDisplayState = LedDisplayStateEnum.THINKING
	logging.info("starting machine")

	try:
		headers = CaseInsensitiveDict()
		headers["Accept"] = "application/json"
		headers["Authorization"] = "Bearer " + bridgeState.authToken #use the bridge api key

		data = {
		  #"member": 224972,
		  #"emailAddress":  "abc@123.com",
		  "keys": [ { "type": "nfca", "token": rfid } ],
		  "configVersion": bridgeState.configVersion
		}
		resp = requests.post(bridgeState.apiUrl + "/bridge/access", json = data, headers = headers)

		jsonResp = json.loads(resp.content.decode('utf-8'))

		logging.debug(jsonResp)

		accessType = jsonResp['type']

		logging.debug('accessType ' + accessType)

		if resp.status_code == 200:
			respContent = resp.json()
			if accessType == "allowed":
				bridgeState.bridgeSessionId = respContent['sessionId']
				bridgeState.isActive = True
				bridgeState.ledDisplayState = LedDisplayStateEnum.ACTIVATE_ALLOWED
				sleep(3)
				bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()
				activateRelay(True)
				logging.debug(bridgeState.bridgeSessionId)
				machineOnForSec = respContent['maxDuration']
				if machineOnForSec != None:
					startMachineStopThread(machineOnForSec)

			elif accessType == "denied":
				bridgeState.ledDisplayState = LedDisplayStateEnum.ACTIVATE_DENIED
				sleep(3)
				bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()

			elif accessType == "checkIn":
				bridgeState.ledDisplayState = LedDisplayStateEnum.ACTIVATE_ALLOWED
				sleep(3)
				bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()

			elif accessType == "checkOut":
				bridgeState.ledDisplayState = LedDisplayStateEnum.ACTIVATE_ALLOWED
				sleep(3)
				bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()
		else:
			respMessages = jsonResp['messages']
			logging.warning(respMessages)
			bridgeState.ledDisplayState = LedDisplayStateEnum.ACTIVATE_FAILED
			sleep(2)
			bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()
			logging.warning('Bridge could not be started (rfid: ' + str(rfid) + ')')

	except Exception as e:
		print(e)
		print("Error calling Access")
		bridgeState.ledDisplayState = LedDisplayStateEnum.ERROR
		sleep(2)
		bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()

	#return allowAccess

def stopMachine():
	global bridgeState
	#displayLedState(LedDisplayStateEnum.THINKING)
	logging.info("stopping machine")
	bridgeState.ledDisplayState = LedDisplayStateEnum.THINKING

	headers = CaseInsensitiveDict()
	headers["Accept"] = "application/json"
	headers["Authorization"] = "Bearer " + bridgeState.authToken #use the bridge api key
	#global bridgeSessionId
	#logging.debug(bridgeSessionId)

	dataStop = { "stopType": "normal", "currentSession": { "id": bridgeState.bridgeSessionId } }

	resp = requests.post(bridgeState.apiUrl + "/bridge/stop", json = dataStop, headers = headers)

	logging.debug(resp.content)

	if resp.status_code == 200 or resp.status_code == 204:
		#self.session_id = None
		bridgeState.bridgeSessionId = 0
		bridgeState.isActive = False
		bridgeState.ledDisplayState = LedDisplayStateEnum.INACTIVE
		activateRelay(False)
		logging.info('Bridge stopped successfully.')
	else:
		logging.error('Bridge could not be stopped (status code ' + str(resp.status_code) + ')')
		bridgeState.ledDisplayState = LedDisplayStateEnum.ERROR
		sleep(2)
		bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()

	# print request object 
	print(resp.content) 



def determineLedDisplayStateBasedOnBridgeState():
	global bridgeState
	ledDisplayState = LedDisplayStateEnum.INACTIVE

	if bridgeState.isOnline == False:
		ledDisplayState = LedDisplayStateEnum.OFFLINE
	elif bridgeState.isActive == True:
		ledDisplayState = LedDisplayStateEnum.ACTIVE

	return ledDisplayState

def errorReadingCard():
	global bridgeState
	logging.warning("error reading card")
	bridgeState.ledDisplayState = LedDisplayStateEnum.ERROR
	sleep(2)
	bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()




try:
	GPIO.add_event_detect(STOP_BUTTON_PIN, GPIO.RISING, callback=stopButtonHandler)
	startLedThread()
	startHeartbeatThread()


	while bridgeState.isBridgeEnabled:
		
		bridgeState.ledDisplayState = determineLedDisplayStateBasedOnBridgeState()
		# Scan for cards
		(status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)
		#logging.info(TagType)
		# If a card is found
		#logging.debug(status)
		if status == MIFAREReader.MI_OK:
			logging.debug("Card detected")

			# Get the UID of the card
			(status, uid) = MIFAREReader.MFRC522_SelectTagSN()
			# If we have the UID, continue
			uid_string = uidToString(uid)
			print("Card read UID: %s" % uid_string)
			
			if bridgeState.isActive == False:
				startMachine(uid_string)
			elif bridgeState.isActive == True:
				stopMachine()
				if bridgeState.isActive == False:
					startMachine(uid_string)
				
		#elif status == MIFAREReader.MI_ERR:
			
		#	errorReadingCard()
		sleep(.5)

finally:
	GPIO.cleanup()


