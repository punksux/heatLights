location = "84123"
on_pi = False
weather_test = 200
lights_start = None
job = None
heat_program_running = False
light_program_has_run = False
old_temp = 0.0
precip = False
lights_pin = 13
heat_pin = 7

templateData = {
    'temp': 0.0,
    'heat_on': True,
    'lights_on': False,
    'lights_on_time': 0,
    'log': {},
    'sunset_hour': 13,
    'sunset_minute': 58,
    'start_date': '8/20/2014',
    'lights_off_time': '22:30',
    'settings_set': False,
    'light_program_running': False,
    'message': "Everything OK",
}

# Imports
from flask import Flask, request, render_template, url_for, redirect
from datetime import datetime, timedelta
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
    global old_temp
    global precip
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
            old_temp = templateData['temp']
            templateData['temp'] = parsed_json['current_observation']['temp_f']
            print(str(old_temp) + " - " + str(templateData['temp']))
            templateData['sunset_hour'] = parsed_json['sun_phase']['sunset']['hour']
            templateData['sunset_minute'] = parsed_json['sun_phase']['sunset']['minute']
            print(parsed_json['current_observation']['weather'])

            weather = parsed_json['current_observation']['weather']
            precip_check = ['rain', 'snow', 'drizzle']
            if any(x in weather for x in precip_check):
                precip = True
            else:
                precip = False

            print(precip)
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

# **Start Heat


def turn_on_heat():
    check_weather()
    if (templateData['temp'] < 34 and old_temp > 38) or (templateData['temp'] < 34 and precip):
        if on_pi:
            GPIO.output(heat_pin, False)
        else:
            print('%s - Heat on: %s.\n' % (datetime.now().strftime('%m/%d/%Y %I:%M %p'), templateData['temp']))
        templateData['heat_on'] = True
        write_log(templateData['temp'], True)
    else:
        if on_pi:
            GPIO.output(heat_pin, True)
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

# **End Heat
# **Start Lights


def turn_on_lights():
    global light_program_has_run
    if on_pi:
        GPIO.output(lights_pin, False)
    else:
        print('%s - Lights on.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
    templateData['lights_on'] = True
    light_program_has_run = True
    split = templateData['off_time'].split(':')
    rand = split[1] + random.randint(0, 10)
    if rand > 59:
        split[0] += 1
        rand -= 60
    job = sched.add_date_job(turn_off_lights, datetime.now().replace(hour=split[0], minute=rand))


def turn_off_lights():
    if on_pi:
        GPIO.output(lights_pin, True)
    else:
        print('%s - Lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
    templateData['lights_on'] = False
    job = sched.add_date_job(pre_lights, datetime.now().replace(day=datetime.now().day+1,
                                                                hour=2, minute=00))


def pre_lights():
    get_start_time()
    job = sched.add_date_job(turn_on_lights, datetime.now().replace(hour=templateData['sunset_hour'],
                                                                    minute=templateData['sunset_minute']))


def manual_lights_off():
        if on_pi:
            GPIO.output(lights_pin, True)
        else:
            print('%s - Manual lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
        templateData['lights_on'] = False


def get_start_time():
    if random.randint(0, 1) == 1:
        pos_neg = -1
    else:
        pos_neg = 1
    templateData['sunset_minute'] = int(templateData['sunset_minute'])+(random.randint(1, 10)*pos_neg)
    if templateData['sunset_minute'] > 59:
        templateData['sunset_minute'] -= 60
        templateData['sunset_minute'] = '0' + str(templateData['sunset_minute'])
        templateData['sunset_hour'] += 1
    templateData['lights_on_time'] = str(templateData['sunset_hour']) + ":" + str(templateData['sunset_minute'])

#check_weather()
try:

    @app.route('/')
    def my_form():
        templateData['log'] = [log.rstrip('\n') for log in open('log.log')]
        return render_template("index.html", **templateData)

    @app.route('/', methods=['POST'])
    def my_form_post():
        if request.form['start_date'] != "" and datetime.strptime(request.form['start_date'] + " " +
                                                                  str(templateData['sunset_hour']) + " " +
                                                                  str(templateData['sunset_minute']),
                                                                  '%m/%d/%Y %H %M') > datetime.now():
            start_date = request.form['start_date']
            templateData['start_date'] = start_date
            templateData['settings_set'] = True
            templateData['message'] = ''
        else:
            templateData['message'] = "Set date for a day in the future"
        if request.form['off_time'] != "":
            templateData['lights_off_time'] = request.form['off_time']
            templateData['message'] = ''
        return render_template("index.html", **templateData)

    @app.route("/lightsStart")
    def start_program():
        if templateData['light_program_running'] is False:
            global lights_start
            get_start_time()
            split = templateData['start_date'].split('/')
            start_date = datetime(int(split[2]), int(split[0]), int(split[1]), int(templateData['sunset_hour']),
                                  int(templateData['sunset_minute']), 00)
            if start_date < datetime.now():
                start_date = datetime.now().replace(hour=int(templateData['sunset_hour']),
                                                    minute=int(templateData['sunset_minute']), second=00)

            try:
                lights_start = sched.add_date_job(turn_on_lights, start_date)
            except Exception as e:
                print(e)
                print('time has past')
            templateData['light_program_running'] = True

            return redirect(url_for('my_form'))

    @app.route("/lightsStop")
    def stop_program():
        if templateData['light_program_running']:
            global lights_start
            if light_program_has_run:
                sched.unschedule_job(job)
            else:
                sched.unschedule_job(lights_start)
            templateData['light_program_running'] = False
            return redirect(url_for('my_form'))

    @app.route("/lightsOn/<length>")
    def lights_on(length):
        if on_pi:
            GPIO.output(lights_pin, False)
        else:
             print('%s - Manual lights on. %s' % (datetime.now().strftime('%m/%d/%Y %I:%M %p'),
                                                 length if int(length) > 0 else ''))
        templateData['lights_on'] = True
        if int(length) > 0:
            temp = datetime.now() + timedelta(seconds=(int(length)*60))
            man_job = sched.add_date_job(manual_lights_off, temp)
        return redirect(url_for('my_form'))

    @app.route("/lightsOff")
    def lights_off():
        if on_pi:
            GPIO.output(lights_pin, True)
        else:
            print('%s - Manual lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
        templateData['lights_on'] = False
        return redirect(url_for('my_form'))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5001)

finally:
    print('Quitting')
    sched.shutdown()
    if on_pi:
        GPIO.cleanup()