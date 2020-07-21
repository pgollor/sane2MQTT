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


class saneMQTT(mqtt.Client):

	def on_connect(self, client, userdata, flags, rc):
		userdata['logger'].debug("Connected with result code: %i", rc)

		client.subscribe(userdata["in-topic"], qos=1)

		stateTopic = userdata["out-topic"] + "/state"
		client.publish(stateTopic, payload="online", qos=1, retain=True)
		# last will message
		client.will_set(stateTopic, payload="offline", qos=1, retain=True)
	# end on_connect


	def on_disconnect(self, client, userdata, rc):
		msg = "Disconnected with result code: %i"
		if (rc):
			userdata['logger'].error(msg, rc)
		else:
			userdata['logger'].debug(msg, rc)
		# end if
	# end on_disconnect


	def on_message(self, client, userdata, msg):
		userdata['logger'].info("Topic: %s - Message: %s", msg.topic, msg.payload.decode())
	# end on_message


	def publishDevices(self, topic, devices):
		msg = json.dumps(devices)
		self.publish(topic, payload=msg)
	# end publishDevices


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
	# end while

	# add infos to userdata
	userdata = dict()
	userdata["in-topic"] = mqttTopic + "/in"
	userdata["out-topic"] = mqttTopic
	
	# init logging
	loglevel = int(options.loglevel)
	if (options.verbose):
		loglevel = logging.DEBUG
	# end if
	logger = logging.getLogger("miflora2mqtt")
	userdata["logger"] = logger
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
	
	# set user data for callbacks
	client.user_data_set(userdata)

	# check username and password
	if (len(options.username) > 0):
		if (len(options.password) == 0):
			raise ValueError("please do not use username without password")
		# end if
		
		client.username_pw_set(options.username, options.password)
	# end if

	# sane init
	ver = sane.init()
	logger.debug("SANE version: %s", ver)

	# scanner devices
	devices = sane.get_devices()
	userdata["devices"] = devices
	logger.debug("scanner: %s", str(devices))
	if (len(devices) < 1):
		logger.error("No devices available. Please trigger device search at runtime.")
	else:
		logger.info("scanner: %s %s", devices[0][1], devices[0][2])
	# end if

	# mqtt parameters
	mqttServer = str(options.server).strip()
	mqttPort = int(options.port)
	mqttKeepalive = int(options.keepalive)

	# debug output
	logger.debug("MQTT server: %s", mqttServer)
	logger.debug("MQTT port: %i", mqttPort)
	logger.debug("MQTT keepalive: %i", mqttKeepalive)
	logger.info("MQTT input topic: %s", userdata["in-topic"])

	# connect to mqttclient
	logger.debug("connect to mqtt client")
	client.connect(mqttServer, mqttPort, mqttKeepalive)

	if (len(devices) > 0):
		client.publishDevices(userdata["out-topic"] + "/devices", devices)

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
	client.publish(userdata["out-topic"] + "/state", payload="offline", qos=1, retain=True)
	logger.debug("disconnecting from MQTT server")
	client.loop_stop()
	client.disconnect()
# end main



if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		logging.error(str(e))
	# end try
# end if
