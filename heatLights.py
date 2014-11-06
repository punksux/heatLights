location = "84123"
on_pi = False
weather_test = 200
lights_start = None
job = None
heat_program_running = False
light_program_has_run = False
old_temp = 0.0
precip = False
#GPIO Pin Setup
lights_pin = 13
heat_pin = 7

templateData = {
    'temp': 0.0,
    'heat_on': False,
    'lights_on': False,
    'lights_on_time': 0,
    'log': '',
    'sunset_hour': 20,
    'sunset_minute': 00,
    'start_date': '8/20/2014',
    'lights_off_time': '22:30',
    'settings_set': False,
    'light_program_running': False,
    'message': '',
    'timer': 0,
}

# Imports
from flask import Flask, request, render_template, url_for, redirect, jsonify
from datetime import datetime, timedelta
import os
import platform
from apscheduler.scheduler import Scheduler
from socket import timeout
import logging
import logging.handlers
import json
import random
from urllib.request import urlopen
import urllib.error
import time

sched = Scheduler()
sched.start()

# Set up logging
#open('errors.log', 'w').close()
logging.basicConfig(filename='errors.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

if platform.uname()[0] != 'Windows':
    print(platform.uname()[0])
    on_pi = True
else:
    print(platform.uname()[0])

if on_pi:
    import RPi.GPIO as GPIO

#Set up Flask
app = Flask(__name__)

#Set up GPIO
if on_pi:
    GPIO.setup(lights_pin, GPIO.OUT)
    GPIO.setup(heat_pin, GPIO.OUT)
    GPIO.output(lights_pin, True)
    GPIO.output(heat_pin, True)


def check_weather():
    global old_temp
    global precip
    if weather_test == 200:
        global something_wrong
        global f
        weather_website = ('http://api.wunderground.com/api/c5e9d80d2269cb64/conditions/astronomy/q/%s.json' % location)
        try:
            f = urlopen(weather_website, timeout=3)
            something_wrong = False
        except urllib.error.URLError as e:
            logging.error('Data not retrieved because %s' % e)
            something_wrong = True
        except timeout:
            logging.error('Socket timed out')
            something_wrong = True

        if something_wrong:
            logging.error("No Internet")
            templateData['temp'] = 0.0
        else:
            json_string = f.read()
            parsed_json = json.loads(json_string.decode("utf8"))
            old_temp = templateData['temp']
            templateData['temp'] = get_temps_from_probes()
            print(str(old_temp) + " - " + str(templateData['temp']))

            templateData['sunset_hour'] = parsed_json['sun_phase']['sunset']['hour']
            templateData['sunset_minute'] = parsed_json['sun_phase']['sunset']['minute']

            print(parsed_json['current_observation']['weather'])
            weather = parsed_json['current_observation']['weather'].lower()
            precip_check = ['rain', 'snow', 'drizzle']
            if any(x in weather for x in precip_check):
                precip = True
            else:
                precip = False

            print(precip)
            f.close()
    else:
        templateData['temp'] = weather_test
        precip = True

#######  --== Get Temps ==--  #######
if on_pi:
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
temperature_file = '/sys/bus/w1/devices/28-0004749a3dff/w1_slave'


def get_temps_from_probes():
    if on_pi:
        y = open(temperature_file, 'r')
        lines = y.readlines()
        y.close()

        if lines[0].strip()[-3:] != 'YES':
            print('No temp from sensor.')
            time.sleep(5)
            get_temps_from_probes()
        else:
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                in_temp = temp_c * 9.0 / 5.0 + 32.0
                return in_temp

    else:
        return str(random.randrange(-32, 104))


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
    if (templateData['temp'] < 34 and old_temp > 38) or (templateData['temp'] < 36 and precip):
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
    templateData['off_time'] = datetime.strptime(templateData['off_time'], '%H:%M') + timedelta(
        seconds=(random.randint(0, 10)*random.randint(-1, 1))*60)

    templateData['off_time'] = templateData['off_time'].strftime('%H:%M')
    split = templateData['off_time'].split(':')
    job = sched.add_date_job(turn_off_lights, datetime.now().replace(hour=split[0], minute=split[1]))


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
    job = sched.add_date_job(turn_on_lights, datetime.now().replace(hour=int(templateData['sunset_hour']),
                                                                    minute=int(templateData['sunset_minute'])))


def manual_lights_off():
        if on_pi:
            GPIO.output(lights_pin, True)
        else:
            print('%s - Manual lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
        templateData['timer'] = 0
        templateData['lights_on'] = False


def get_start_time():
    start_time = datetime.strptime(str(templateData['sunset_hour']) + ":" + str(templateData['sunset_minute']), '%H:%M')
    print(start_time.strftime('%H:%M'))
    random_time = random.randint(1, 10)*random.randint(-1, 1)
    start_time += timedelta(seconds=random_time*60)
    print(start_time.strftime('%H:%M'))
    templateData['sunset_hour'] = start_time.strftime('%H')
    templateData['sunset_minute'] = start_time.strftime('%M')
    templateData['lights_on_time'] = start_time.strftime('%I:%M %p')
    print(templateData['lights_on_time'])

# **End Lights

if on_pi:
    check_weather()

try:
    @app.route('/')
    def my_form():
        log = [log.rstrip('\n') for log in open('log.log')]
        templateData['log'] = json.dumps(log[len(log)-17:])
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
            if templateData['light_program_running']:
                return redirect(url_for('stop_program'))
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
            templateData['timer'] = 0
            return redirect(url_for('my_form'))

    @app.route("/lightsOn", methods=['POST'])
    def lights_on():
        length = request.form.get('length', 'something is wrong', type=str)
        if length == '': length = '0'
        print(length)
        if on_pi:
            GPIO.output(lights_pin, False)
        else:
            print('%s - Manual lights on. %s' % (datetime.now().strftime('%m/%d/%Y %I:%M %p'),
                                                 length if int(length) > 0 else ''))
        templateData['lights_on'] = True
        if int(length) > 0:
            temp = datetime.now() + timedelta(seconds=(int(length)*60))
            man_job = sched.add_date_job(manual_lights_off, temp)
        return jsonify({'length': length})

    @app.route("/lightsOff")
    def lights_off():
        if on_pi:
            GPIO.output(lights_pin, True)
        else:
            print('%s - Manual lights off.' % (datetime.now().strftime('%m/%d/%Y %I:%M %p')))
        templateData['lights_on'] = False
        templateData['timer'] = 0
        return redirect(url_for('my_form'))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5001)

finally:
    print('Quitting')
    sched.shutdown(wait=False)
    if on_pi:
        GPIO.setup(lights_pin, GPIO.IN)
        GPIO.setup(heat_pin, GPIO.IN)
