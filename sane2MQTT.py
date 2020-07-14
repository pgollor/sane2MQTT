#!/usr/bin/python3

# \brief sane2MQTT
# \author Pascal Gollor
# \copyright cc 2020 by-sa

import optparse, logging, signal, time, re, argparse
import paho.mqtt.client as mqtt


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


def on_connect(client, userdata, flags, rc):
	userdata['logger'].info("Connected with result code: %i", rc)
# end on_connect


def on_disconnect(client, userdata, rc):
	msg = "Disconnected with result code: %i"
	if (rc):
		userdata['logger'].error(msg, rc)
	else:
		userdata['logger'].info(msg, rc)
	# end if
# end on_disconnect


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

	# add infos to userdata
	userdata = dict()
	userdata["topic"] = options.topic
	
	# init logging
	loglevel = int(options.loglevel)
	if (options.verbose):
		loglevel = logging.DEBUG
	# end if
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
	client = mqtt.Client()
	
	# set user data for callbacks
	client.user_data_set(userdata)

	# register callbacks
	client.on_connect = on_connect
	client.on_disconnect = on_disconnect
	client.on_message = on_message

	# check username and password
	if (len(options.username) > 0):
		if (len(options.password) == 0):
			raise ValueError("please do not use username without password")
		# end if
		
		client.username_pw_set(options.username, options.password)
	# end if

	# debug output
	logger.debug("server: %s" ,options.server)
	logger.debug("port: %i", options.port)
	logger.debug("topic: %s", options.topic)

	# connect to mqttclient
	logger.debug("connect to mqtt client")
	client.connect(options.server, options.port, options.keepalive)

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
