#!/usr/bin/env python3
from argparse import ArgumentParser
from os import listdir, getuid
from shutil import copyfile, move
from subprocess import TimeoutExpired
from urllib.request import urlretrieve

from devices import Device

__version__ = '6.3.3'
__versionDate__ = '2025-02-10'

supported = ('sd', 'mmcblk', 'sr', 'vd', 'nvme')

cols = [('Vendor / Model', 26),  # 25
        ('Serial', 21),  # 16
        ('Firmware', 10),  # 7
        ('Size', 9),  # 7
        ('Runtime', 12),  # PoH 6
        ('Written', 10),
        ('Rpm', 6),  # 5
        ('Life', 6),  # 5
        ('S.M.A.R.T.', 10)]

alternatives = {'model': ['/sys/block/{}/device/model', '/sys/block/{}/device/name'],
                'serial': ['/sys/block/{}/device/serial'],
                'firmware': ['/sys/block/{}/device/rev', '/sys/block/{}/device/fwrev'],
                'size': ['/sys/block/{}/size'],
                'vendor': ['/sys/block/{}/device/vendor']}

# hdparmRex = {'model': r'\sModel=([\w\s\-]*)[\,\n]',
#              'firmware': r'\s*FwRev=([\w\s\-\.]*)[\,\n]',
#              'serial': r'\s*SerialNo=([\w\s\-]*)[\,\n]'}

updateSmartUrl = 'https://raw.githubusercontent.com/mirror/smartmontools/master/drivedb.h'

parser = ArgumentParser(description=f'List all conntected drives and monitore the S.M.A.R.T.-status', epilog='Baba {__version__} ({__version__}) by Schluggi')
parser.add_argument('device', help='only show specific device', nargs='?')
parser.add_argument('-m', '--mib', help='show sizes in KiB, MiB, GiB, TiB and PiB', action='store_true')
parser.add_argument('-u', '--update-drivedb', help='updating drivedb.h to increase the S.M.A.R.T. compatibility. This is equal to "update-smart-drivedb"', action='store_true')
parser.add_argument('-t', '--timeout', help='the time to wait for a timeout in seconds (default 4)', nargs='?', default=4)
parser.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
parser.add_argument('-w', '--written', help='use 32 KB LBAs instead of the default 512 Bytes to calculate the "written" value (only for non-nvme devices)', action='store_true')

args = parser.parse_args()


def get_device_info_from_file(devname: str, keys: str or list) -> str:
    rv = ''
    if type(keys) is str:
        keys = [keys]

    for key in keys:
        for filename in alternatives[key]:
            try:
                with open(filename.format(devname)) as f:
                    if rv:
                        rv += ' '
                    rv += f.read().rstrip()
            except FileNotFoundError:
                pass
    if rv:
        return rv
    return '-'


def update_drivedb():
    """Downloading and update the drivedb.h"""
    print('Downloading new drivedb...', flush=True, end='')
    urlretrieve(updateSmartUrl, '/var/lib/smartmontools/drivedb/drivedb.h.new')

    print('OK\nBackuping current drivedb...', flush=True, end='')
    copyfile('/var/lib/smartmontools/drivedb/drivedb.h', '/var/lib/smartmontools/drivedb/drivedb.h.old')

    print('OK\nActivate new drivedb...', flush=True, end='')
    move('/var/lib/smartmontools/drivedb/drivedb.h.new', '/var/lib/smartmontools/drivedb/drivedb.h')

    print('OK\nFinish!')


def convert_bytes(size: int, precision: int = 0) -> str:
    if args.mib:
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
        conversion = 1024
    else:
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        conversion = 1000

    for unit in units:
        if size < conversion:
            return f'{size:.{precision}f} {unit}'
        size /= conversion

    return size


def grabber(d, attributes):
    rv = ''
    for attr in attributes:
        if attr in d:
            if rv:
                rv += ' '
            rv += d[attr]
    if rv:
        return rv
    return '-'


def valuechecker(dev: str) -> list:
    rv = {'vendor': '-',
          'model': '-',
          'serial': '-',
          'firmware': '-',
          'size': '-',
          'runtime': '-',
          'written': '-',
          'rotation': '-',
          'lifetime': '-',
          'smart': '-'}

    device = Device(dev, args.timeout)

    try:
        device.fetch_smart()
    except TimeoutExpired:
        rv['smart'] = 'TIMEOUT'
        rv['lifetime'] = '?'
        rv['rotation'] = '?'
        rv['runtime'] = '?'
        rv['written'] = '?'

    if device.name.startswith(('nvme', 'sd', 'sr', 'vd')) and rv['smart'] != 'TIMEOUT':

        if device.name.startswith('nvme'):
            rv['model'] = grabber(device.smart_info, ['Model Number', 'Device Model'])

        elif device.name.startswith(('sd', 'vd')):
            rv['model'] = grabber(device.smart_info, ['Model Family', 'Vendor', 'Device Model', 'Product'])

        elif device.name.startswith('sr'):
            rv['model'] = grabber(device.smart_info, ['Vendor', 'Product'])

        rv['firmware'] = grabber(device.smart_info, ['Firmware Version', 'Revision'])
        rv['serial'] = grabber(device.smart_info, ['Serial Number', 'Serial number'])

        if device.name.startswith('sr') is False:
            rv['smart'] = device.analyse('health')

        size = device.analyse('size')
        if size:
            rv['size'] = convert_bytes(int(size))

        rv['runtime'] = device.analyse('runtime') or rv['runtime']
        rv['rotation'] = device.analyse('rotation') or rv['rotation']
        rv['lifetime'] = device.analyse('lifetime') or rv['lifetime']

        written = device.analyse('written')
        if written:
            written = int(written.split(' [')[0].replace('.', ''))
            if device.name.startswith('nvme'):
                rv['written'] = convert_bytes(written * 512 * 1000, precision=1)
            else:
                if args.written:
                    rv['written'] = convert_bytes(written * 32000, precision=1)
                else:
                    rv['written'] = convert_bytes(written * 512, precision=1)

    if rv['model'] == '-':
        rv['model'] = get_device_info_from_file(device.name, ['vendor', 'model'])

    if rv['serial'] == '-':
        rv['serial'] = get_device_info_from_file(device.name, 'serial')

    if rv['firmware'] == '-':
        rv['firmware'] = get_device_info_from_file(device.name, 'firmware')

    if rv['size'] == '-' and device.name.startswith('sr') is False:
        size = int(get_device_info_from_file(device.name, 'size')) * 512
        rv['size'] = convert_bytes(size)

    return [rv['model'],
            rv['serial'],
            rv['firmware'],
            rv['size'],
            rv['runtime'],
            rv['written'],
            rv['rotation'],
            rv['lifetime'],
            rv['smart']]


def short(s, max_len):
    if args.verbose:
        return f'{s} | '

    elif len(s) > max_len:
        split_str = '[..]'
        split_len = int(max_len / 2 - len(split_str) / 2)
        return f'{s[:split_len]}{split_str}{s[-split_len:]}'

    else:
        return s


def colorize(color, text):
    match color:
        case 'red':
            return '\x1b[0m\x1b[41m\x1b[1m{text}\x1b[0m'
        case 'green':
            return f'\x1b[0m\x1b[42m\x1b[1m{text}\x1b[0m'
        case 'purple':
            return f'\x1b[0m\x1b[45m\x1b[1m{text}\x1b[0m'
        case 'blue':
            return f'\x1b[0m\x1b[44m\x1b[1m{text}\x1b[0m'
        case 'dark':
            return f'\x1b[0m\x1b[40m\x1b[1m{text}\x1b[0m'
        case 'turkey':
            return f'\x1b[0m\x1b[46m\x1b[1m{text}\x1b[0m'
        case 'yellow':
            return f'\x1b[0m\x1b[1m\x1b[43m\x1b[30m{text}\x1b[0m'


if getuid() != 0:
    exit('Please run as root!')

elif args.update_drivedb:
    update_drivedb()
    exit()

elif args.device:
    if args.device.startswith('/dev/'):
        devices = [args.device.split('/')[-1]]
    else:
        devices = [args.device]
else:
    devices = [f for f in sorted(listdir('/sys/block/'), key=lambda x: (len(x), x)) if f.startswith(supported)]

print('\x1b[1m{}'.format('Device'.ljust(8)), end='', flush=False)

for c in cols:
    print(c[0].ljust(c[1]), end='', flush=False)
print('\x1b[0m')

for lno, filename in enumerate(devices):
    #: colorize lines
    if lno % 2:
        print('\x1b[33m', end='')
    else:
        print('\x1b[36m', end='')

    #: print device name
    print(filename.ljust(8), flush=True, end='')

    #: get and print the other values
    for i, value in enumerate(valuechecker(f'/dev/{filename}')):
        if value is None:
            value = '-'

        if i == 8:  # smart
            if value in ('PASSED', 'OK'):
                value = colorize('green', '    OK    ')

            elif value == 'DSBLD':
                value = colorize('red', ' DISABLED ')

            elif value == 'UDMA':
                value = colorize('red', ' UltraDMA')

            elif value == 'TIMEOUT':
                value = colorize('purple', ' TIME-OUT ')

            elif value == 'UNKNOWN':
                value = colorize('blue', ' UNKNOWN  ')

            elif value == 'USBB':
                value = colorize('blue', 'USB-BRIDGE')

            elif value == '-':
                value = colorize('dark', ' NO SMART ')

            elif value != '-':
                value = colorize('red', value.ljust(cols[i][1]))

            print(value, end='')

        elif i == 7 and value not in ['-', '?']:  # lifetime
            value_str = str(value)
            just = cols[i][1] - len(value_str) - 1

            if value <= 45:
                value = colorize('red', f'{value}%')

            elif value < 80:
                value = colorize('yellow', f'{value}%')

            else:
                value = colorize('green', f'{value}%')

            print(value.ljust(len(value) + just), end='')

        else:
            print(short(value, cols[i][1] - 1).ljust(cols[i][1]), end='')

    print('\x1b[0m')
exit()
