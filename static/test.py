import os, time

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
long_temp_sensor = '/sys/bus/w1/devices/28-00047858c5ff/w1_slave'
short_temp_sensor = '/sys/bus/w1/devices/28-00047355a1ff/w1_slave'


def get_temps_from_probes():

    y = open(long_temp_sensor, 'r')
    lines = y.readlines()
    y.close()

    r = open(short_temp_sensor, 'r')
    lines2 = r.readlines()
    r.close()

    if lines[0].strip()[-3:] != 'YES':
        print('No temp from sensor.')
        get_temps_from_probes()
    else:
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            in_temp = temp_c * 9.0 / 5.0 + 32.0
            print('Long: ' + str(in_temp))

    if lines2[0].strip()[-3:] != 'YES':
        print('No temp from sensor.')
        get_temps_from_probes()
    else:
        equals_pos = lines2[1].find('t=')
        if equals_pos != -1:
            temp_string = lines2[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            in_temp = temp_c * 9.0 / 5.0 + 32.0
            print('Short: ' + str(in_temp))

while True:
    get_temps_from_probes()
    time.sleep(10)