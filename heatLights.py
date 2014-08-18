location = "84123"
on_pi = False
weather_test = 100

templateData = {
    'temp': 0.0,
    'heat_on': False,
    'lights_on': False,
    'lights_on_time': 0,
}

# Imports
from flask import Flask, request, render_template, url_for, redirect
from datetime import datetime, timedelta
import time
import os
import platform
from apscheduler.scheduler import Scheduler
from socket import timeout
import logging
import logging.handlers
import json

sched = Scheduler()
sched.start()

if platform.uname()[0] != 'Windows':
    print(platform.uname()[0])
    on_pi = True
else:
    print(platform.uname()[0])

if on_pi:
    import urllib2
    import RPi.GPIO as GPIO
    import socket
else:
    from urllib.request import urlopen
    import urllib.error


#Set up Flask
app = Flask(__name__)

#Set up GPIO
if on_pi:
    GPIO.setup(7, GPIO.OUT)
    GPIO.setup(11, GPIO.OUT)
    GPIO.setup(13, GPIO.OUT)
    GPIO.output(7, True)
    GPIO.output(11, True)
    GPIO.output(13, True)

def check_weather():
    if weather_test == 100:
        global something_wrong
        global f
        weather_website = ('http://api.wunderground.com/api/c5e9d80d2269cb64/conditions/q/%s.json' % location)
        if on_pi:
            try:
                f = urllib2.urlopen(weather_website, timeout=3)
                something_wrong = False
            except urllib2.URLError as e:
                my_logger.error('%s - Data not retrieved because %s' % datetime.now().strftime('%m/%d/%Y %I:%M %p'),
                                    e)
                something_wrong = True
            except socket.timeout:
                my_logger.error('%s - Socket timed out' % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
                something_wrong = True
        else:
            try:
                f = urlopen(weather_website, timeout=3)
                something_wrong = False
            except urllib.error.URLError as e:
                my_logger.error('%s - Data not retrieved because %s' % datetime.now().strftime('%m/%d/%Y %I:%M %p'),
                                    e)
                something_wrong = True
            except timeout:
                my_logger.error('%s - Socket timed out' % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
                something_wrong = True

        if something_wrong:
            my_logger.error("%s - No Internet" % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
            templateData['rain'] = 0.0
        else:
            json_string = f.read()
            parsed_json = json.loads(json_string.decode("utf8"))
            templateData['rain'] = parsed_json['current_observation']['precip_today_in']
            f.close()
    else:
        templateData['rain'] = weather_test