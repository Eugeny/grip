import grip.ui as ui

ui.info('asd')
ui.warn('asd')
ui.error('asd')

print('1.2.3', ui.yellow('->'), '4.5.6')

print(ui.yn('yeah, nope?'))

#print(ui.prompt('Name', validate=lambda x: int(x)))
