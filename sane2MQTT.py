#!/usr/bin/python3

# \brief sane2MQTT
# \author Pascal Gollor
# \copyright cc 2020 by-sa

import optparse, logging, signal, time, re, argparse, json
import paho.mqtt.client as mqtt
import sane


DEFAULT_MQTT_SERVER = "127.0.0.1"
DEFAULT_MQTT_PORT = 1883
DEFAULT_TOPIC = "sane" # without leading /


## detecting kill signal
# source:	http://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully
class GracefulKiller:
	def __init__(self):
		self.kill_now = False
		
		signal.signal(signal.SIGINT, self.exit_gracefully)
		signal.signal(signal.SIGTERM, self.exit_gracefully)
	# end __init__

	def exit_gracefully(self, signum, frame):
		self.kill_now = True
	# end exit_gracefully
# end class GracefulKiller


# class as interface between sane and the mqtt protocol
class saneMQTT(mqtt.Client):
	logger = None
	outTopic = ""
	inTopic = ""
	stateTopic = ""
	devices = list()
	device = None

	def setTopics(self, inT, outT):
		self.outTopic = str(outT)
		self.inTopic = str(inT)
		self.stateTopic = self.outTopic + "/state"


	def setDevices(self, devices):
		self.devices = devices


	def on_connect(self, client, userdata, flags, rc):
		self.logger.debug("Connected with result code: %i", rc)

		self.subscribe(self.inTopic + "/#", qos=1)
		self.logger.debug("subscribe to: %s", self.inTopic + "/#")

		# commands
		self.message_callback_add(self.inTopic + "/set_device", self.on_setDevice)
		self.message_callback_add(self.inTopic + "/list_devices", self.on_listDevices)

		self.publish(self.stateTopic, payload="online", qos=1, retain=True)
		# last will message
		self.will_set(self.stateTopic, payload="offline", qos=1, retain=True)


	def on_disconnect(self, client, userdata, rc):
		msg = "Disconnected with result code: %i"
		if (rc):
			self.logger.error(msg, rc)
		else:
			self.logger.debug(msg, rc)


	def on_message(self, client, userdata, msg):
		self.logger.info("Topic: %s - Message: %s", msg.topic, msg.payload.decode())


	def publishDevices(self):
		if (len(self.devices) < 1):
			return

		msg = json.dumps(self.devices)
		self.publish(self.outTopic + "/devices", payload=msg)

		for i in range(len(self.devices)):
			device = self.devices[i]
			msg = json.dumps({'id': i, "port": device[0], "vendor": device[1], "pid": device[2], "type": device[3]})
			self.logger.debug(msg)
			self.publish(self.outTopic + "/device", payload=msg)


	def on_setDevice(self, client, userdata, msg):
		devID = -1
		
		try:
			try:
				devID = int(msg.payload.decode())
			except ValueError:
				raise RuntimeError("Unknown device ID")
			if (len(self.devices) == 0):
				raise RuntimeError("No devices available.")
			if (len(self.devices) < (devID + 1)):
				raise RuntimeError("Invalid device ID.")
		except RuntimeError as e:
			self.logger.error(e.args)
			return
		self.device = self.devices[devID]

		self.logger.info("using device: %s", self.device)
	

	def on_listDevices(self, client, userdata, msg):
		self.publishDevices()

# end class saneMQTT


def main():
	parser = optparse.OptionParser(
		usage = "%prog [options]",
		description = "sane2MQTT controls scanner with sane via MQTT",
		version="%prog 0.1a"
	)

	group = optparse.OptionGroup(parser, "MQTT settings")
	group.add_option("-s", "--server",
		dest = "server",
		help = "mqtt server, default %default",
		default = DEFAULT_MQTT_SERVER
	)
	group.add_option("--port",
		dest = "port",
		action = "store",
		type = 'int',
		help = "mqtt server port, default %default",
		default = DEFAULT_MQTT_PORT
	)
	group.add_option("-k", "--keepalive",
		dest = "keepalive",
		action = "store",
		type = 'int',
		help = "keepalive option for mqtt server, default %default",
		default = 60
	)
	group.add_option("-t", "--topic",
		dest = "topic",
		help = "topic to publish to without leading /, default %default",
		default = DEFAULT_TOPIC
	)
	group.add_option("-u", "--username",
		dest = "username",
		help = "connection username",
		default = ""
	)
	group.add_option("-p", "--password",
		dest = "password",
		help = "connection password",
		default = ""
	)
	parser.add_option_group(group)


	group = optparse.OptionGroup(parser, "Basic settings")
	group.add_option("-l", "--loglevel",
		dest = "loglevel",
		action = "store",
		type = 'int',
		help = str(logging.CRITICAL) + ": critical  " + str(logging.ERROR) + ": error  " + str(logging.WARNING) + ": warning  " + str(logging.INFO) + ":info  " + str(logging.DEBUG) + ":debug",
		default = logging.ERROR
	)
	group.add_option("-v", "--verbose",
		dest = "verbose",
		action = "store_true",
		help = "show debug messages (overrites loglevel to debug)",
		default = False
	)
	parser.add_option_group(group)

	# parse options
	(options, _) = parser.parse_args()

	# mqtt topics
	mqttTopic = str(options.topic)
	while (mqttTopic.endswith("/")):
		mqttTopic = mqttTopic[:-1]

	# add infos to userdata
	userdata = dict()
	inTopic = mqttTopic + "/in"
	outTopic = mqttTopic
	
	# init logging
	loglevel = int(options.loglevel)
	if (options.verbose):
		loglevel = logging.DEBUG
	logger = logging.getLogger("miflora2mqtt")
	logger.setLevel(loglevel)
	ch = logging.StreamHandler()
	ch.setLevel(loglevel)
	formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
	formatter.datefmt = '%Y-%m-%d %H:%M:%S'
	ch.setFormatter(formatter)
	logger.addHandler(ch)

	# add killer
	killer = GracefulKiller()

	# add MQTT client
	client = saneMQTT()
	
	# set user data
	client.logger = logger
	client.setTopics(inTopic, outTopic)
	
	# check username and password
	if (len(options.username) > 0):
		if (len(options.password) == 0):
			raise ValueError("please do not use username without password")
		
		client.username_pw_set(options.username, options.password)
	# end if

	# sane init
	ver = sane.init()
	logger.debug("SANE version: %s", ver)

	# scanner devices
	devices = sane.get_devices()
	client.setDevices(devices)
	logger.debug("scanner: %s", str(devices))
	print(len(devices))
	if (len(devices) < 1):
		logger.error("No devices available. Please trigger device search at runtime.")
	else:
		for i in range(len(devices)):
			logger.info("scanner %i: %s %s", i, devices[0][1], devices[0][2])
	# end if

	# mqtt parameters
	mqttServer = str(options.server).strip()
	mqttPort = int(options.port)
	mqttKeepalive = int(options.keepalive)

	# debug output
	logger.debug("MQTT server: %s", mqttServer)
	logger.debug("MQTT port: %i", mqttPort)
	logger.debug("MQTT keepalive: %i", mqttKeepalive)
	logger.info("MQTT input topic: %s", inTopic)

	# connect to mqttclient
	logger.debug("connect to mqtt client")
	client.connect(mqttServer, mqttPort, mqttKeepalive)

	if (len(devices) > 0):
		client.publishDevices()

	# start client loop
	client.loop_start()

	# forever loop
	try:
		logger.debug("start program loop")
		
		while (1):
			time.sleep(0.1)
		
			if (killer.kill_now):
				raise KeyboardInterrupt
			# end if
		# end while
	except KeyboardInterrupt:
		logger.debug("exit program loop")
	# end try
	
	# disconnecting
	client.publish(client.stateTopic, payload="offline", qos=1, retain=True)
	logger.debug("disconnecting from MQTT server")
	client.loop_stop()
	client.disconnect()
# end main



if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		logging.error(str(e))
