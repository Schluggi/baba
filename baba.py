#!/usr/bin/python3
from argparse import ArgumentParser
from os import listdir, getuid
from re import search
from shutil import copyfile, move
from subprocess import TimeoutExpired, Popen, PIPE, STDOUT
from sys import argv
from urllib.request import urlretrieve
from smartvalues import Device


__version__ = '6.1.3'
__versionDate__ = '2018-06-14'

supported = ('sd', 'mmcblk', 'sr', 'vd', 'nvme')

cols = [ ('Vendor / Model', 26), #25
         ('Serial', 21), #16
         ('Firmware', 10), #7
         ('Size', 9), #7
         ('Runtime', 12), #PoH 6
         ('Written', 10),
         ('Rpm', 6), # 5
         ('Life', 6), # 5
         ('S.M.A.R.T.', 10)]

paths = { 'model': ['/sys/block/{}/device/model', '/sys/block/{}/device/name'],
          'serial': ['/sys/block/{}/device/serial'],
          'firmware': ['/sys/block/{}/device/rev', '/sys/block/{}/device/fwrev'],
          'size': ['/sys/block/{}/size'],
          'vendor': ['/sys/block/{}/device/vendor']}

hdparmRex = { 'model': b'\sModel=([\w\s\-]*)[\,\n]',
              'firmware': b'\s*FwRev=([\w\s\-\.]*)[\,\n]',
              'serial': b'\s*SerialNo=([\w\s\-]*)[\,\n]'}

updateSmartUrl = 'https://raw.githubusercontent.com/mirror/smartmontools/master/drivedb.h'

parser = ArgumentParser(description='List all conntected drives and monitore the S.M.A.R.T.-status', epilog='Baba {} ({}) by Schluggi'.format(__version__, __versionDate__))
parser.add_argument('device', help='only show specific device', nargs='?')
parser.add_argument('-m', '--mib', help='show sizes in KiB, MiB, GiB, TiB and PiB', action='store_true')
parser.add_argument('-u', '--update-drivedb', help='updating drivedb.h to increase the S.M.A.R.T. compatibility. This is equal to "update-smart-drivedb"', action='store_true')
parser.add_argument('-s', '--self-update', help='installs the newest version of baba', action='store_true')
parser.add_argument('-t', '--timeout', help='the time to wait for a timeout in seconds (default 4)', nargs='?', default=4)
parser.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
parser.add_argument('-w', '--written', help='use 32 KB LBAs instead of the default 512 Bytes to calculate the "written" value', action='store_true')

args = parser.parse_args()

def update_drivedb():
    """Downloading and update the drivedb.h"""
    print('Downloading new drivedb...', flush=True, end='')
    urlretrieve(updateSmartUrl, '/var/lib/smartmontools/drivedb/drivedb.h.new')

    print('OK\nBackuping current drivedb...', flush=True, end='')
    copyfile('/var/lib/smartmontools/drivedb/drivedb.h', '/var/lib/smartmontools/drivedb/drivedb.h.old')    

    print('OK\nActivate new drivedb...', flush=True, end='')
    move('/var/lib/smartmontools/drivedb/drivedb.h.new', '/var/lib/smartmontools/drivedb/drivedb.h')

    print('OK\nFinish!')


def calc_size(bytes, unit):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

    if unit == 1024:
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
        
    if bytes is 0:
        rv = '-'

    elif bytes < unit:
        rv = '{} {}'.format(bytes, units[0])

    elif bytes < unit**2:
        rv = '{:.0f} {}'.format(bytes/unit, units[1])

    elif bytes < unit**3:
        rv = '{:.0f} {}'.format(bytes/unit**2, units[2])

    elif bytes < unit**4:
        rv = '{:.0f} {}'.format(bytes/unit**3, units[3])

    elif bytes < unit**5:
        rv = '{:.0f} {}'.format(bytes/unit**4, units[4])

    elif bytes < unit**6:
        rv = '{:.0f} {}'.format(bytes/unit**5, units[5])

    return rv
    

def valuechecker(dev):
    devname = dev.split('/')[-1]

    try:
        device = Device(dev, args.timeout)
        smart_info = device.smart_result()
        
    except TimeoutExpired:
         smart_info = {'vendor': '-',
                       'model': '-',
                       'serial': '-',
                       'firmware': '-',
                       'size': '-',
                       'runtime': '?',
                       'written': '?',
                       'rotation': '?',
                       'lifetime':  '?',
                       'smart': 'TIMEOUT'}

        
    for key in smart_info:
        if smart_info[key] is '-' and key in paths:

            for path in paths[key]:
                try:
                    data = open(path.format(devname), 'r').read().rstrip()
                    
                    if key == 'size':
                        if devname.startswith('sr'):
                            data = '-'
                        else:
                            data = str(int(data)*512)

                    if data.rstrip():
                        smart_info[key] = data

                except FileNotFoundError:
                    pass
    
    hdparm_result = b''
    
    for key in smart_info:
        if smart_info[key] is '-' and key in hdparmRex:

            if hdparm_result not in [b'', b'TIMEOUT']:
                try:
                    proc = Popen(['hdparm', '-i', device.dev_path], stdout=PIPE, stderr=STDOUT)
                    proc.wait(2)
                    hdparm_result = proc.stdout.read()

                except TimeoutExpired:
                    hdparm_result = 'TIMEOUT'

            try:
                smart_info[key] = search(hdparmRex[key], hdparm_result).group(1).rstrip().decode()
                
            except (AttributeError, IndexError):
                pass
    
    
    unit = 1000

    if args.mib:
        unit = 1024

    
    if smart_info['size'] != '-':
        smart_info['size'] = calc_size(int(smart_info['size']), unit)
    
    if smart_info['written'] not in ['-', '?']:
        multiplicator = 512
        
        if args.written:
            multiplicator = 32*1000*1000 # 32 MB
        
        smart_info['written'] = calc_size(int(smart_info['written']) * multiplicator, unit)

    
    if smart_info['vendor'] != '-':
        vendor_model = '{} {}'.format(smart_info['vendor'], smart_info['model'])
    else:
        vendor_model = smart_info['model']
    
    return [vendor_model,
            smart_info['serial'],
            smart_info['firmware'],
            smart_info['size'],
            smart_info['runtime'],
            smart_info['written'],
            smart_info['rotation'],
            smart_info['lifetime'],
            smart_info['smart']]


def short(s, max_len):
    if args.verbose:
        return '{} | '.format(s)
        
    elif len(s) > max_len:
        split_str = '[..]'
        split_len = int(max_len/2 - len(split_str)/2)
        return '{}{}{}'.format(s[:split_len], split_str, s[-split_len:])
        
    else:
        return s


def colored(color, s):
    if color == 'red':
        return '\x1b[0m\x1b[41m\x1b[1m{}\x1b[0m'.format(s)

    elif color == 'green':
        return '\x1b[0m\x1b[42m\x1b[1m{}\x1b[0m'.format(s)

    elif color == 'purple':
        return '\x1b[0m\x1b[45m\x1b[1m{}\x1b[0m'.format(s)

    elif color == 'blue':
        return '\x1b[0m\x1b[44m\x1b[1m{}\x1b[0m'.format(s)    

    elif color == 'dark':
        return '\x1b[0m\x1b[40m\x1b[1m{}\x1b[0m'.format(s)    

    elif color == 'turkey':
        return '\x1b[0m\x1b[46m\x1b[1m{}\x1b[0m'.format(s)

    elif color == 'yellow':
        return '\x1b[0m\x1b[1m\x1b[43m\x1b[30m{}\x1b[0m'.format(s)



if getuid() != 0:
    exit('Please run as root!')

elif args.update_drivedb:
    update_drivedb()
    exit()

elif args.self_update:
    proc = Popen('/usr/share/baba/update.sh')
    if proc.wait() != 0:
        print('Oops. Please run /usr/share/baba/update.sh manually!') 
    exit('Update finish!')
     
elif args.device:
    if args.device.startswith('/dev/'):
        devices = [args.device.split('/')[-1]]
    else:
        devices = [args.device]
else:
    devices = [f for f in sorted(listdir('/sys/block/')) if f.startswith(supported)]
    

print('\x1b[1m{}'.format('Device'.ljust(8)), end='', flush=False)

for c in cols:
    print(c[0].ljust(c[1]), end='',flush=False)
print('\x1b[0m')


for lno, filename in enumerate(devices):
    #: colored lines
    if lno % 2:
        print('\x1b[33m', end='')
    else:
        print('\x1b[36m', end='') 
    
    #: print device name
    print(filename.ljust(8), flush=True, end='')

    #: get and print the other values
    for i, value in enumerate(valuechecker('/dev/{}'.format(filename))):
        
        if i is 8: # smart
            if value is 'OK':
                value = colored('green', '    OK    ')
            
            elif value is 'DSBLD':
                value = colored('red', ' DISABLED ')

            elif value is 'UDMA':
                value = colored('red', ' UltraDMA')
            
            elif value is 'TIMEOUT':
                value = colored('purple', ' TIME-OUT ')
            
            elif value is 'USBB':
                value = colored('blue', 'USB-BRIDGE')
            
            elif value is '-':
                value = colored('dark', ' NO SMART ')
            
            elif value != '-':
                value = colored('red', value.ljust(cols[i][1]))
                
            print(value, end='')

        elif i is 7 and value not in ['-', '?']: # life
            value_str = str(value)
            just = cols[i][1] - len(value_str) - 1
            
            if value <= 45:
                value = colored('red', '{}%'.format(value))
                
            elif value < 80:
                value = colored('yellow', '{}%'.format(value))

            else:
                value = colored('green', '{}%'.format(value))
            
            print(value.ljust(len(value) + just), end='')

        else:
            print(short(value, cols[i][1]-1).ljust(cols[i][1]), end='')
        
    print('\x1b[0m')
exit()
