location = "84123"
on_pi = False
weather_test = 200

templateData = {
    'temp': 0.0,
    'heat_on': False,
    'lights_on': False,
    'lights_on_time': 0,
    'log': {},
    'sunset_hour': 0,
    'sunset_minute': 0,
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
import random

sched = Scheduler()
sched.start()

# Set up logging
my_logger = logging.getLogger('MyLogger')
handler = logging.handlers.RotatingFileHandler('errors.log', maxBytes=1000000, backupCount=3)
handler.setLevel(logging.DEBUG)
my_logger.addHandler(handler)

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
    if weather_test == 200:
        global something_wrong
        global f
        weather_website = ('http://api.wunderground.com/api/c5e9d80d2269cb64/conditions/astronomy/q/%s.json' % location)
        if on_pi:
            try:
                f = urllib2.urlopen(weather_website, timeout=3)
                something_wrong = False
            except urllib2.URLError as e:
                my_logger.error('%s - Data not retrieved because %s' % datetime.now().strftime('%m/%d/%Y %I:%M %p'), e)
                something_wrong = True
            except socket.timeout:
                my_logger.error('%s - Socket timed out' % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
                something_wrong = True
        else:
            try:
                f = urlopen(weather_website, timeout=3)
                something_wrong = False
            except urllib.error.URLError as e:
                my_logger.error('%s - Data not retrieved because %s' % datetime.now().strftime('%m/%d/%Y %I:%M %p'), e)
                something_wrong = True
            except timeout:
                my_logger.error('%s - Socket timed out' % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
                something_wrong = True

        if something_wrong:
            my_logger.error("%s - No Internet" % datetime.now().strftime('%m/%d/%Y %I:%M %p'))
            templateData['temp'] = 0.0
        else:
            json_string = f.read()
            parsed_json = json.loads(json_string.decode("utf8"))
            templateData['temp'] = parsed_json['current_observation']['temp_f']
            templateData['sunset_hour'] = parsed_json['sun_phase']['sunset']['hour']
            templateData['sunset_minute'] = parsed_json['sun_phase']['sunset']['minute']
            f.close()
    else:
        templateData['temp_f'] = weather_test


def write_log(message, on_off):
    if on_off:
        on_off = "1"
    else:
        on_off = "0"
    if os.path.getsize('log.log') > 1000000:
        r = open('log.log', 'w')
    else:
        r = open('log.log', 'a')
    r.write(datetime.now().strftime('%Y,%m,%d,%H,%M') + "|" + str(message) + "|" + on_off + '\n')
    r.close()


def turn_on_heat():
    check_weather()
    if templateData['temp'] < 34:
        if on_pi:
            GPIO.output(7, False)
        else:
            print('%s - Heat on: %s.\n' % (datetime.now().strftime('%m/%d/%Y %I:%M %p'), templateData['temp']))
        templateData['heat_on'] = True
        write_log(templateData['temp'], True)
    else:
        if on_pi:
            GPIO.output(7, True)
        else:
            print('%s - Heat off: %s.\n' % (datetime.now().strftime('%m/%d/%Y %I:%M %p'), templateData['temp']))
        templateData['heat_on'] = False
        write_log(templateData['temp'], False)


s = datetime.now()
if s.minute > 30:
    sched.add_interval_job(turn_on_heat, seconds=1800, start_date=s.replace(hour=s.hour+1, minute=00,
                                                                            second=00, microsecond=0))
else:
    sched.add_interval_job(turn_on_heat, seconds=1800, start_date=s.replace(minute=30, second=00, microsecond=0))




def turn_on_lights():
    if on_pi:
        GPIO.output(13, False)
    else:
        print ('%s - Lights on.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
    templateData['lights_on'] = True
    job = sched.add_date_job(turn_off_lights, datetime.now().replace(hour=10, minute=(30+random.randint(0, 20))))


def turn_off_lights():
    if on_pi:
        GPIO.output(13, True)
    else:
        print ('%s - Lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
    templateData['lights_on'] = False
    job = sched.add_date_job(get_start_time, datetime.now().replace(day=datetime.now().day+1,
                                                                    hour=2, minute=00))

check_weather()


def get_start_time():
    #check_weather()
    if random.randint(0,1) == 1:
        pos_neg = -1
    else:
        pos_neg = 1
    templateData['sunset_minute'] = int(templateData['sunset_minute'])+(random.randint(1, 20)*pos_neg)
    templateData['lights_on_time'] = str(templateData['sunset_hour']) + ":" + str(templateData['sunset_minute'])
    job = sched.add_date_job(turn_on_lights, datetime.now().replace(hour=templateData['sunset_hour'],
                                                                    minute=templateData['sunset_minute']))
get_start_time()


try:

    @app.route('/')
    def my_form():
        templateData['log'] = [log.rstrip('\n') for log in open('log.log')]
        return render_template("index.html", **templateData)

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5001)

finally:
    sched.shutdown()
    if on_pi:
        GPIO.cleanup()