#!/usr/bin/env python3
from re import findall, M, search
from subprocess import Popen, PIPE, STDOUT
from sys import argv
from pprint import pprint


class Device(object):
    def __init__(self, path, timeout=3):
        self.path = path
        self.name = path.split('/')[-1]
        self.info = {}
        self.timeout = float(timeout)

        self.smart_data = {}
        self.smart_info = {}
        self.smart_health = 'UNKNOWN'
        self.smart_support = 'UNKNOWN'
        self.vendor_model = ''

    def fetch_smart(self):
        self.smart_data = {}
        self.smart_info = {}
        self.smart_health = 'UNKNOWN'
        self.smart_support = 'UNKNOWN'
        self.vendor_model = ''

        process = Popen(['smartctl', '-a', self.path], stdout=PIPE, stderr=STDOUT)
        returncode = process.wait(self.timeout)
        output = process.stdout.read().decode()

#        if returncode != 0:  # TODO: IMPROVE ERROR HANDLING!
#            raise FileNotFoundError(self.path)
        try:
            rex_support = search('SMART support is:\s*(Enabled|Disabled)', output)
            if rex_support:
                self.smart_support = rex_support.group(1)

            if 'Unknown USB bridge' in output:
                self.smart_health = 'USBB'

            if self.name.startswith('nvme'):
                info_data, smart_data = output.split('=== START OF SMART DATA SECTION ===')
            elif self.name.startswith('sr') or self.smart_support == 'Disabled':
                info_data = output.split('=== START OF INFORMATION SECTION ===')[1]
                smart_data = None
            else:
                info_data, smart_data = output.split('=== START OF READ SMART DATA SECTION ===')

            rex_health = search('(SMART overall-health self-assessment test result:|SMART Health Status:)\s*([\w\s\-!]+)\n', output)

            if rex_health:
                self.smart_health = rex_health.group(2).strip()


            for m in findall('^(.+):\s+(.*)', info_data, flags=M):
                self.smart_info[m[0]] = m[1]

            if self.name.startswith('sd') and self.smart_support == 'Enabled':
                for m in findall('^\s*(\d+)\s*([\w-]+)\s+(\w*)\s*(\w*)\s*(\w*)\s*([\w-]+)\s*([\w-]*)\s*(\w*)\s*([\w\-!]*)\s*(\d+)', smart_data, flags=M):
                    self.smart_data[m[0]] = {
                        'attribute_name': m[1],
                        'flag': m[2],
                        'value': m[3],
                        'worst': m[4],
                        'thresh': m[5],
                        'type': m[6],
                        'updated': m[7],
                        'when_failed': m[8],
                        'raw_value': m[9]
                    }

            elif self.name.startswith('nvme'):
                for m in findall('^(.+):\s+(.*)', smart_data, flags=M):
                    self.smart_data[m[0]] = m[1]

            if 'Vendor' in self.smart_info:
                self.vendor_model += self.smart_info['Vendor'].lower()
            if 'Model Family' in self.smart_info:
                self.vendor_model += self.smart_info['Model Family'].lower()
            if 'Product' in self.smart_info:
                self.vendor_model += self.smart_info['Product'].lower()

        except ValueError:
            pass

    def analyse(self, mode):
        if mode == 'lifetime':
            return self._lifetime()
        elif mode == 'runtime':
            return self._runtime()
        elif mode == 'rotation':
            return self._rotation()
        elif mode == 'size':
            return self._size()
        elif mode == 'health':
            return self._health()
        elif mode == 'written':
            return self._written()
        else:
            raise AttributeError('Unknown mode: {}'.format(mode))

    def _lifetime(self):
        if self.smart_data is {} or self.smart_info is {}:
            raise Exception('Please fetch smart data first')

        lifetime = None

        if self.name.startswith('nvme'):
            if 'Percentage Used' in self.smart_data:
                used = int(self.smart_data['Percentage Used'].split('%')[0])
                lifetime = 100 - used

        elif self.name.startswith('sd'):
            if 'samsung' in self.vendor_model:
                if '177' in self.smart_data:  # Wear_Leveling_Count
                    lifetime = int(self.smart_data['177']['value'])
				
                elif '173' in self.smart_data:  # Wear_Leveling_Count
                    lifetime = int(self.smart_data['173']['value'])
                
                if '179' in self.smart_data:  # Used_Reserve_Block_Count
                    smart_179 = int(self.smart_data['179']['raw_value'])

                    if lifetime:
                        if lifetime > smart_179:
                            lifetime = smart_179
                    else:
                        lifetime = smart_179

            elif 'crucial' in self.vendor_model:
                if '202' in self.smart_data:  # Remaining_lifetime_Perc or Percent_Lifetime_Used
                    lifetime = int(self.smart_data['202']['raw_value'])

            elif 'ocz' in self.vendor_model:
                if '209' in self.smart_data:  # Remaining_Lifetime_Perc
                    lifetime = int(self.smart_data['209']['raw_value'])

        return lifetime

    def _health(self):
        health = self.smart_health
        sector_sum = 0

        if self.smart_support == 'Disabled':
            health = 'DSBLD'

        elif self.name.startswith('sd'):
            if 'SMART support is' in self.smart_info and self.smart_info['SMART support is'] == 'Disabled':
                health = 'DSBLD'

            if health == 'PASSED':
                if '199' in self.smart_data:  # UDMA_CRC_Error_Count
                    if int(self.smart_data['199']['raw_value']) >= 500:
                        health = 'UDMA'

                if '5' in self.smart_data:  # Reallocated_Sector_Ct
                    sector_sum += int(self.smart_data['5']['raw_value'])

                if '197' in self.smart_data:  # Current_Pending_Sector
                    sector_sum += int(self.smart_data['197']['raw_value'])

                #: TODO -> INCORRECT!
                if 'crucial' in self.vendor_model and '172' in self.smart_data:  # Erase_Fail_Count
                    sector_sum += int(self.smart_data['172']['raw_value'])

        elif self.name.startswith('nvme'):
            if 'Critical Warning' in self.smart_data and self.smart_data['Critical Warning'] != '0x00':
                health = 'WARN'
            elif 'Warning  Comp. Temperature Time' in self.smart_data and self.smart_data['Warning  Comp. Temperature Time'] != '0':
                health = 'TEMP E'
            elif 'Warning  Comp. Temperature Time' in self.smart_data and self.smart_data['Warning  Comp. Temperature Time'] != '0':
                health = 'TEMP W'
            elif 'Media and Data Integrity Errors' in self.smart_data:
                sector_sum += int(self.smart_data['Media and Data Integrity Errors'])

        if sector_sum > 0:
            health = str(sector_sum)

        return health

    def _size(self):
        size = None
        raw_size = None

        if 'Total NVM Capacity' in self.smart_info:
            raw_size = self.smart_info['Total NVM Capacity']

        elif 'User Capacity' in self.smart_info:
            raw_size = self.smart_info['User Capacity']

        if raw_size:
            rex = search('\s*([\d\.]*)', raw_size.replace('.', '').replace(',', ''))
            if rex:
                size = rex.group(1)
            return size

    def _rotation(self):
        if self.name.startswith('nvme'):
            return 'NVME'
        elif 'Rotation Rate' in self.smart_info:
            if self.smart_info['Rotation Rate'] == 'Solid State Device':
                return 'SSD'
            elif ' rpm' in self.smart_info['Rotation Rate']:
                return self.smart_info['Rotation Rate'].split(' rpm', 1)[0]
        return False

    def _runtime(self):
        hours = False

        if self.name.startswith('sd') and '9' in self.smart_data:
            hours = int(self.smart_data['9']['raw_value'])

        elif self.name.startswith('nvme') and 'Power On Hours' in self.smart_data:
            hours = int(self.smart_data['Power On Hours'])

        if hours:
            if hours < 24:
                if hours == 1:
                    hours = '{} hour'.format(hours)
                else:
                    hours = '{} hours'.format(hours)
            elif hours < 365 * 24:
                hours = '{:.1f} days'.format(hours / 24)
            else:
                hours = '{:.1f} years'.format(hours / 24 / 365)

        return hours

    def _written(self):
        raw_written = None
        if self.name.startswith('sd'):
            if '241' in self.smart_data:
                return self.smart_data['241']['raw_value']  # Total_LBAs_Written
        elif self.name.startswith('nvme'):
            if 'Data Units Written' in self.smart_data:
                raw_written = self.smart_data['Data Units Written']
                rex = search('\s*([\d\.]*)', raw_written)
                if rex:
                    return rex.group(1)



if __name__ == '__main__':
    dev = Device(argv[1])
    dev.fetch_smart()
    pprint(dev.smart_info)
    #print(dev.analyse('lifetime'))
    pprint(dev.smart_data)
    #print(dev.health.encode())
    #print(dev.support.encode())
