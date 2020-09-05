#!/usr/bin/python3

import sane

sane.init()

# modes: 'Lineart', 'Gray', 'Color'
# source: 'Flatbed', 'Automatic Document Feeder'

devices = sane.get_devices()
print('devices:', devices)

dev = sane.open(devices[0][0])

params = dev.get_parameters()
print('parameters:', params)

options = dev.get_options()
#print('options:', options)
print('options:')
for option in options:
	print(option)

try:
	dev.depth = 1
except:
	print('Cannot set depth, defaulting to', params[3])

try:
	dev.mode = 'Lineart'
except:
	print('Cannot set mode, defaulting to', params[0])

try:
	dev.resolution = 300
except:
	print('Cannot set resolution')

try:
	dev.source = 'Flatbed'
except:
	print('Cannot set source')

if (0):
	#dev.wait-for-button = True
	dev.start()
	im = dev.snap()
	im.save('/tmp/test.png')


dev.close()