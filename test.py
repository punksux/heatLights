weather = 'chancerain'

precip_check = ['rain', 'snow', 'drizzle', 'hail', 'ice', 'thunderstorm']
if any(m in weather for m in precip_check):
    if m == 'snow':
        print('snow')
    print('precip')
else:
    print('no precip')