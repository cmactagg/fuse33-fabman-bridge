# python3

import requests, json, time, datetime, threading, logging, sys, pprint, os
import RPi.GPIO as GPIO

# for MFRC522 NFC Reader
import MFRC522 # from https://github.com/danjperron/MFRC522-python

import serial

logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO) # CRITICAL, ERROR, WARNING, INFO, DEBUG

class Fabman(object):

	def __init__(self, api_token, api_url_base="https://fabman.io/api/v1/", account_id=None):
		self.api_token = api_token
		self.api_header = {'Content-Type': 'application/json','Authorization': 'Bearer {0}'.format(self.api_token)}
		self.api_url_base = api_url_base
		if (account_id is not None):
			self.account_id = account_id
		else: # take first account_id in list (sort by id asc)
			self.api_header = {'Authorization': 'Bearer 0adb0caf-a2ae-4586-a74e-fe0a54f06a93'}
			api_endpoint = 'accounts'
			query_string = 'limit=1&orderBy=id&order=asc'
			api_url = self.api_url_base + api_endpoint + '?' + query_string
			#print(api_url)
			response = requests.get(api_url, headers=self.api_header)
			if (response.status_code == 200):
				self.account_id = json.loads(response.content.decode('utf-8'))[0]["id"]
				logging.info('Set account id to ' + str(self.account_id))
			else:
				logging.error('Could not fetch account id')
			#pprint.pprint(json.loads(response.content.decode('utf-8')))
		self.response = {}
		self.HTTP_OK = (200, 201, 204)

	def get(self, api_endpoint, id=None, query_string='limit=50'): # fetch entry
		if (id is None):
			api_url = self.api_url_base + api_endpoint + '?' + query_string
		else:
			api_url = self.api_url_base + api_endpoint + '/' + str(id)
		print(api_url)
		response = requests.get(api_url, headers=self.api_header)
		self.response = json.loads(response.content.decode('utf-8'))
		if (response.status_code in self.HTTP_OK):
			print("GET successful")
			return True
		else:
			logging.error('GET failed')
			return False
		#pprint.pprint(json.loads(response.content.decode('utf-8')))
		#return(json.loads(response.content.decode('utf-8')))
	
	def post(self, api_endpoint, data): # add entry
		#data = { 'emailAddress': user_id, 'configVersion': 0 }
		#data = { 'resource': 972, 'member': 6, 'createdAt': "2020-03-09T14:10:17.638Z" }
		api_url = self.api_url_base + api_endpoint
		print(api_url)
		response = requests.post(api_url, headers=self.api_header, json=data)
		self.response = json.loads(response.content.decode('utf-8'))
		#print("response.status_code = " + str(response.status_code))
		if (response.status_code in self.HTTP_OK):
			#return json.loads(response.content.decode('utf-8'))["id"] # return id of added entry
			print("POST successful")
			return True
		else:
			logging.error('POST failed')
			#pprint.pprint(json.loads(response.content.decode('utf-8')))
			return False
		#pprint.pprint(json.loads(response.content.decode('utf-8')))
		#return(json.loads(response.content.decode('utf-8')))
		
	def put(self, api_endpoint, id, data): # update entry
		if ('lockVersion' not in data.keys()):
			# get lockversion
			#print("lockVersion nicht in data -> get")
			if (self.get(api_endpoint, id)):
				lockversion = self.response['lockVersion']
				#print ("get liefert folgende lockversion: " + str(lockversion))
				data.update( {'lockVersion' : lockversion} )
		api_url = self.api_url_base + api_endpoint + "/" + str(id)
		#print(api_url)
		response = requests.put(api_url, headers=self.api_header, json=data)
		self.response = json.loads(response.content.decode('utf-8'))
		#print("response.status_code = " + str(response.status_code))
		if (response.status_code in self.HTTP_OK):
			#return json.loads(response.content.decode('utf-8'))["id"] # return id of added entry
			print("PUT successful")
			return True
		else:
			logging.error('PUT failed')
			pprint.pprint(json.loads(response.content.decode('utf-8')))
			return False

	def delete(self, api_endpoint, id):
		api_url = self.api_url_base + api_endpoint + '/' + str(id)
		print(api_url)
		response = requests.delete(api_url, headers=self.api_header)
		#self.response = json.loads(response.content.decode('utf-8'))
		print("response.status_code = " + str(response.status_code))
		if (response.status_code in self.HTTP_OK):
			print("DELETE successful")
			return True
		else:
			logging.error('DELETE failed')
			return False
			
	def start_resource(self, resource_id, member_id, takeover=True): # if takeover=True: if session running -> stop and start again as new user
		now = datetime.datetime.utcnow().isoformat() + "Z"
		data = {
				  "resource": resource_id,
				  "member": member_id,
				  "createdAt": now,
				  #"stoppedAt": "2020-03-09",
				  #"idleDurationSeconds": 0,
				  #"notes": "string",
				  #"metadata": {}
				}
		if (self.post("resource-logs", data)):
			print("resource started: " + str(self.response['id']))
			return True
		else:
			print("starting resource failed")
			return False
		
	def stop_resource(self, resource_id, member_id=None):
	
		# get resource-log id if active log entry
		self.get(api_endpoint="resource-logs", id=None, query_string="resource=" + str(resource_id) + "&status=active")
		resource_log_id = self.response[0]['id']
	
		now = datetime.datetime.utcnow().isoformat() + "Z"
			
		data = {
				  "resource": resource_id,
				  "stoppedAt": now,
			   }
			   
		if (member_id is not None):
			data.update( {"member": member_id} )

		if (self.put("resource-logs", resource_log_id, data)):
			print("resource stopped")
			return True
		else:
			print("stopping resource failed")
			return False
		
	def get_resources(self, space_id=None):
		self.get(api_endpoint="resources", id=None, query_string="space="+str(space_id))
		#resource_log_id = self.response[0]['id']
		resources = {}
		for r in self.response:
			#print(str(r['id']) + ": " + r['name'])
			resources[r['id']] = { 
									'name' : r['name'],
									#'metadata' : r['metadata']
								 }
		return resources
	
	def get_training_courses(self):
		if (self.get(api_endpoint="training-courses", id=None, query_string="account="+str(self.account_id))):
			return self.response
		else:
			return False

class Relay(object):

	def __init__(self, signal_pin = 26, state = 0):
		try:
			self.signal_pin = signal_pin
			self.state = state
			GPIO.setmode(GPIO.BCM)
			GPIO.setup(self.signal_pin, GPIO.OUT)
			self.off()
		except Exception as e: 
			logging.error('Function Relay.__init__ raised exception (' + str(e) + ')')

	def on(self): 
		try:
			GPIO.output(self.signal_pin, 1)
			self.state = 1
		except Exception as e: 
			logging.error('Function Relay.on raised exception (' + str(e) + ')')

	def off(self): 
		try:
			GPIO.output(self.signal_pin, 0)
			self.state = 0
		except Exception as e: 
			logging.error('Function Relay.off raised exception (' + str(e) + ')')

	def toggle(self): 
		try:
			if (self.state == 0):
				self.on()
			else:
				self.off()
		except Exception as e: 
			logging.error('Function Relay.toggle raised exception (' + str(e) + ')')

	def __del__(self):
		try:
			GPIO.setmode(GPIO.BCM)
			GPIO.setup(self.signal_pin, GPIO.OUT)
			self.off()
			GPIO.cleanup()
		except Exception as e: 
			logging.error('Function Relay.__del__ raised exception (' + str(e) + ')')


class FabmanBridge(object):

	def __init__(self, config = None, config_file = "fabman.json"): # if no config is given read config from "fabman.json"
		#try:
			# default values
			self.config = {
							"api_url_base"       : "https://fabman.io/api/v1/",
							"heartbeat_interval" : 30,
							"left_button"        : 24,
							"reader_type"        : "MFRC522",
							"led_r"              : 17,
							"led_g"              : 27,
							"led_b"              : 22,
							"display"            : "SSD1306_128_32",
							"relay"              : 26,
							"buzzer"             : 18
						  }

			if (config is None):
				self.config_file = config_file
				self.load_config(self.config_file)
			else: 
				self.config_file = None
				pprint.pprint(config)
				self.config.update(config)

			if ("api_token" in self.config):
				self.api_header = {'Content-Type': 'application/json','Authorization': 'Bearer {0}'.format(self.config['api_token'])}
			else:
				logging.warning('Not api-token defined: Cannot access Fabman via Bridge API')
			self.session_id = None
			self.next_heartbeat_call = time.time()
			#self.rgbled = RGBLED(self.config["led_r"], self.config["led_g"], self.config["led_b"])
			#self.buzzer = Buzzer(self.config["buzzer"])
			self.relay = Relay(self.config["relay"],0)
			GPIO.setwarnings(False)
			
			if (self.config["reader_type"] == "MFRC522"):
				#self.reader = SimpleMFRC522()
				#self.reader = SimpleMFRC522()
				self.reader = MFRC522.MFRC522(dev=1)
				self.chip_type = "nfca"
			
			if ("left_button" in self.config and not(self.config["left_button"] is None)):
				GPIO.setmode(GPIO.BCM) #GPIO.setmode(GPIO.BOARD)  
				GPIO.setup(self.config["left_button"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
			if ("right_button" in self.config and not(self.config["right_button"] is None)):
				GPIO.setmode(GPIO.BCM) #GPIO.setmode(GPIO.BOARD)  
				GPIO.setup(self.config["right_button"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
			#if ("left_button_pin" in self.config and not(self.config["left_button_pin"] is None)):
			#	self.left_button = Button(self.config["left_button_pin"], pull_up=True, bounce_time=0.3)
			#if ("right_button_pin" in self.config and not(self.config["right_button_pin"] is None)):
			#	self.right_button = Button(pin=self.config["right_button_pin"], pull_up=True, bounce_time=0.3)
			if (self.config["display"] == "sh1106"): # 1,3" I2C OLED Display
				self.device = get_device(("--display", self.config["display"]))
				
			self.screen_message = ""
			
		#except Exception as e: 
		#	logging.error('Function FabmanBridge.__init__ raised exception (' + str(e) + ')')

	def save_config(self, filename = "fabman.json"):
		try:
			with open(filename, 'w') as fp:
				json.dump(self.config, fp, sort_keys=True, indent=4)
			return True
		except Exception as e: 
			logging.error('Function FabmanBridge.save_config raised exception (' + str(e) + ')')
			return False

	def load_config(self, filename = "fabman.json"):
		try:
			with open(filename, 'r') as fp:
				file_config = json.load(fp)
				self.config.update(file_config)
			return self.config
		except Exception as e: 
			logging.error('Function FabmanBridge.load_config raised exception (' + str(e) + ')')
			return False

	def access(self, user_id):# user_id can be email address or rfid key 
		try:
			if (user_id):
				if ("@" in str(user_id)): # authenticate with email address
					data = { 'emailAddress': user_id, 'configVersion': 0 }
				else: # authenticate with rfid key 
					data = { "keys": [ { "type": self.chip_type, "token": user_id } ], "configVersion": 0 }
				api_url = '{0}bridge/access'.format(self.config["api_url_base"])
				response = requests.post(api_url, headers=self.api_header, json=data)
				if (response.status_code == 200 and json.loads(response.content.decode('utf-8'))['type'] == "allowed"):
					logging.info('Bridge started successfully.')
					#self.display_text("Access granted\n\n\n<-STOP")
					#self.rgbled.color = Color('green')
					self.session_id = json.loads(response.content.decode('utf-8'))["sessionId"]
					return True
				else:
					logging.warning('Bridge could not be started (user_id: ' + str(user_id) + ')')
					#self.display_error("Access\ndenied")
					#self.display_text("Access denied")
					#self.display_text("Access denied",3)
					return False
			else:
				logging.warning("No user_id set for /bridge/access")
		except Exception as e: 
			logging.error('Function FabmanBridge.access raised exception (' + str(e) + ')')
			return False
	
	def stop(self, metadata = None, charge = None):
		try:
			api_url = '{0}bridge/stop'.format(self.config["api_url_base"])

			data = { "stopType": "normal", "currentSession": { "id": self.session_id } }
			if (metadata is not None):
				data['currentSession'].update( { 'metadata' : metadata } )
			if (charge is not None):
				data['currentSession'].update( { 'charge' : charge } )			
			
			response = requests.post(api_url, headers=self.api_header, json=data)
			if response.status_code == 200 or response.status_code == 204:
				#self.user_id = None
				self.session_id = None
				logging.info('Bridge stopped successfully.')
				#self.rgbled.off("g")
				#self.rgbled.off()
				return True
			else:
				logging.error('Bridge could not be stopped (status code ' + str(response.status_code) + ')')
				pprint.pprint(data)
				self.display_error()
				return False			
		except Exception as e: 
			logging.error('Function FabmanBridge.stop raised exception (' + str(e) + ')')
			return False

	def read_key(self):
		try:
			if (self.config["reader_type"] == "MFRC522"):
				#return str(hex(self.reader.read_id()))[2:10] 
				continue_reading = True
				while continue_reading:
					# Scan for cards
					(status, TagType) = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
					# If a card is found
					if status == self.reader.MI_OK:
						logging.debug("Card detected")
						continue_reading = False
						# Get the UID of the card
						(status, uid) = self.reader.MFRC522_SelectTagSN()
						# If we have the UID, continue
						if status == self.reader.MI_OK:
							uid_string = ""
							for i in uid:
								uid_string += format(i, '02X') 
							logging.debug("Card uid: " + uid_string)
							return uid_string
						else:
							logging.debug("Card authentication error")			
			
			else:
				logging.error("Undefined reader type")
				return False
		except Exception as e: 
			logging.error('Function FabmanBridge.read_key raised exception (' + str(e) + ')')
			return False
		
	def is_on(self):
		try:
			if (self.session_id is None):
				return False
			else:
				return True
		except Exception as e: 
			logging.error('Function FabmanBridge.is_on raised exception (' + str(e) + ')')
			return False
				
	def is_off(self):
		try:
			return not(self.is_on())
		except Exception as e: 
			logging.error('Function FabmanBridge.is_off raised exception (' + str(e) + ')')
			return False

	def display_error(self, message = None):
		try:
			#self.rgbled.on("r",0.1)
			#self.rgbled.off("r",0.1)
			#self.rgbled.on("r",0.1)
			#self.rgbled.off("r",0.1)
			#self.rgbled.on("r",0.1)
			#self.rgbled.off("r")	
			#self.rgbled.blink(0.1, 0.1, 0, 0, Color('red'), Color('black'), 3, True)
			if (message is not None):
				logging.error(message)
				self.display_text(message, 3)
				print(message)
			return True
		except Exception as e: 
			logging.error('Function FabmanBridge.display_error raised exception (' + str(e) + ')')
			return False

	def display_warning(self, message = None):
		try:
			#self.rgbled.on("b",0.1)
			#self.rgbled.off("b",0.1)
			#self.rgbled.on("b",0.1)
			#self.rgbled.off("b",0.1)
			#self.rgbled.on("b",0.1)
			#self.rgbled.off("b")			
			#self.rgbled.blink(0.1, 0.1, 0, 0, Color('yellow'), Color('black'), 3, True)
			if (message is not None):
				logging.warning(message)
				self.display_text(message, 3)
				print(message)
			return True
		except Exception as e: 
			logging.error('Function FabmanBridge.display_warning raised exception (' + str(e) + ')')
			return False

	def display_text(self, text= "", duration = None):
        logging.warning(text)

	def _start_heartbeat_thread(self):
		try:
			#print datetime.datetime.now()
			api_url = '{0}bridge/heartbeat'.format(self.config["api_url_base"])
			data = { 'configVersion': 0 }
			response = requests.post(api_url, headers=self.api_header, json=data)
			if response.status_code == 200:
				response = json.loads(response.content.decode('utf-8'))
				logging.debug("Heartbeat sent")
			else:
				logging.warning("Heartbeat failed")
			self.next_heartbeat_call += self.config["heartbeat_interval"]
			heartbeat_thread = threading.Timer( self.next_heartbeat_call - time.time(), self._start_heartbeat_thread )
			heartbeat_thread.daemon = True
			heartbeat_thread.start()
		except Exception as e: 
			logging.error('Function FabmanBridge._start_heartbeat_thread raised exception (' + str(e) + ')')
			return False

	
if __name__ == '__main__':

	# Bridge config
	'''
	Example for "bridge.json" (Use bridge API token for the equipment you want to connect to.)
	{ 
		"api_url_base"       : "https://fabman.io/api/v1/",
		"api_token"          : "xxxxxxxxxxx-xxxxxxxxx-x-xxxxxxxx-xxxxxx",
		"display"            : "sh1106",
		"reader_type"        : "Gwiot7941E",
		"left_button"        : 4,
		"relay"              : 26
	}
	'''
	bridge = FabmanBridge(config_file="bridge.json")

	# Handle stop button
	def callback_left_button(channel):
		if (bridge.is_on()):
			logging.debug("Switching off")
			bridge.stop()
	GPIO.add_event_detect(bridge.config["left_button"], GPIO.FALLING, callback=callback_left_button, bouncetime=300)

	# Run bridge
	logging.info("Bridge started")
	while (True):
		if (bridge.is_off()):		
			bridge.display_text("Show card to start")
			logging.debug("Waiting for key")
			key = bridge.read_key()
			if (key != False and key is not None):
				if (bridge.access(key)):
					bridge.display_text("Access granted\n\n\n<-STOP")
					logging.debug("Switching on")
				else:
					bridge.display_text("Access denied",3)
					logging.debug("Access denied")
