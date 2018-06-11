#!/usr/bin/env python3
from re import search
from subprocess import Popen, PIPE, STDOUT
from sys import argv


class Device(object):
    def __init__(self, dev_path, timeout):
        self.dev_path = dev_path
        self.info = {}
        self.timeout = float(timeout)
    
    def _smart_analyse(self):
        rex_db = { 'family'  : b'Model Family:\s*([\w\s-]*)\n',
                   'model'   : b'Device Model:\s*([\w\s-]*)\n',
                   'product' : b'Product:\s*([\w\s-]*)\n',
                   'vendor'  : b'Vendor:\s*([\w\s-]*)\n',
                   'serial'  : b'Serial Number:\s*([\w\s-]*)\n',
                   'revision': b'Revision:\s*([\w\s-]*)\n',
                   'firmware': b'Firmware Version:\s*([\w\s\.\-]*)\n',
                   'size'    : b'User Capacity:\s*([\d\.]*) bytes',
                   'rotation': b'Rotation Rate:\s*([\w\s-]*)\n',
                   
                   'support'  : b'SMART support is:\s*(Enabled|Disabled)',
                   'health'   : b'SMART overall-health self-assessment test result:\s*([\w\s\-\!]*)\n',
                   'usbbridge': b'\s+?Unknown USB bridge\s+?\[(.*)\]',
                   
                   #'Raw_Read_Error_Rate'     : b'Raw_Read_Error_Rate\s+\w*\s*\w*\s*\w*\s*\w*\s*[\w-]*\s*\w*\s*[\w-]*\s*(\d*)',
                   'Reallocated_Sector_Ct'   : b'Reallocated_Sector_Ct\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Power_On_Hours'          : b'Power_On_Hours\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Reallocated_Event_Count' : b'Reallocated_Event_Count\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Current_Pending_Sector'  : b'Current_Pending_Sector\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   #'Offline_Uncorrectable'   : b'Offline_Uncorrectable\s+\w*\s*\w*\s*\w*\s*\w*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'UDMA_CRC_Error_Count'    : b'UDMA_CRC_Error_Count\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Total_LBAs_Written'      : b'Total_LBAs_Written\s+\w*\s*\w*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',

                   'Wear_Leveling_Count'     : b'Wear_Leveling_Count\s+\w*\s*(\d*)\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*\d*',
                   'Remaining_lifetime_Perc' : b'Remaining_lifetime_Perc\s+\w*\s*(\d*)\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*\d*',
                   'Percent_Lifetime_Used'   : b'Percent_Lifetime_Used\s+\w*\s*(\d*)\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*\d*',
                   'Total_Bad_Block_Count'   : b'Total_Bad_Block_Count\s+\w*\s*\d*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Erase_Fail_Count'        : b'Erase_Fail_Count\s+\w*\s*\d*\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*(\d*)',
                   'Used_Reserve_Block_Count': b'Used_Reserve_Block_Count\s+\w*\s*(\d*)\s*\w*\s*[\w\-]*\s*[\w-]*\s*\w*\s*[\w\-\!]*\s*\d*'
                   }
        proc = Popen(['smartctl', '-a', self.dev_path], stdout=PIPE, stderr=STDOUT)
        if self.timeout:
            proc.wait(self.timeout)
        else:
            proc.wait()
        
        data = proc.stdout.read()
        
        for rex in rex_db:
            try:
                self.info[rex] = search(rex_db[rex], data).group(1).rstrip().decode()
            except (AttributeError, IndexError):
                pass
       
    def smart_values(self):
        if self.info == {}:
            self._smart_analyse()
        return self.info
        
    def smart_result(self):
        if self.info == {}:
            self._smart_analyse()

        vendor = '-'   # ok
        model = '-'    # ok
        serial = '-'   # ok, hdparm better
        firmware = '-' # ok
        size = '-'     # ok
        runtime = '-'  # S(tunden), T(age) J(ahre)
        smart = 'OK'
        rotation = '-' # ok
        written = '-'
        lifetime = '-'
        
        if 'family' in self.info:
            vendor = self.info['family']
        elif 'vendor' in self.info:
            vendor = self.info['vendor']
        
        if 'model' in self.info:
            model = self.info['model']
        elif 'product' in self.info:
            model = self.info['product']

        if 'serial' in self.info:
            serial = self.info['serial']
        
        if 'firmware' in self.info:
            firmware = self.info['firmware']

        elif 'revision' in self.info:
            firmware = self.info['revision']
        
        if 'size' in self.info:
            bytes = self.info['size']
            size = ''.join(bytes.split('.'))
        
        if 'Power_On_Hours' in self.info:
            runtime = int(self.info['Power_On_Hours'])
            if runtime < 24:
                runtime =  '{} hours'.format(runtime)
            elif runtime < 365*24:
                runtime =  '{:.1f} days'.format(runtime/24)
            else:
                runtime = '{:.1f} years'.format(runtime/24/365)
                
        if 'rotation' in self.info:
            rotation = self.info['rotation']
            if rotation == 'Solid State Device':
               rotation = 'SSD'
            elif ' rpm' in rotation:
                rotation = rotation.split(' rpm',1)[0]
        
        if 'support' in self.info:
            support = self.info['support']
            if support == 'Disabled':
                smart = 'DSBLD'

            elif 'health' in self.info:
                health = self.info['health']
                sector_sum = 0
                
                if 'UDMA_CRC_Error_Count' in self.info:
                    error_count = int(self.info['UDMA_CRC_Error_Count'])
                    if error_count > 2000:
                        smart = 'UDMA'

                
                if 'Reallocated_Sector_Ct' in self.info:
                    sector_count = self.info['Reallocated_Sector_Ct']
                    if sector_count != '0':
                        sector_sum += int(sector_count)
                        
                    
                if 'Current_Pending_Sector' in self.info:
                    sector_count = self.info['Current_Pending_Sector']
                    if sector_count != '0':
                        sector_sum += int(sector_count)

                if 'crucial' in ' '.join((vendor.lower(), model.lower())) and 'Erase_Fail_Count' in self.info:
                    error_count = self.info['Erase_Fail_Count']
                    if error_count != '0':
                        sector_sum += int(error_count)
            
                if sector_sum > 0:  
                    smart = str(sector_sum)
                
                if health != 'PASSED':
                    smart = health

        elif 'usbbridge' in self.info:
                smart = 'USBB'
           
        else:
            smart = '-'
        
        vendor_model = ' '.join((vendor, model)).lower()
        
        if 'Total_LBAs_Written' in self.info:
            written = self.info['Total_LBAs_Written']
                        
        if 'samsung' in vendor_model:
            if 'Wear_Leveling_Count' in self.info:
                lifetime = int(self.info['Wear_Leveling_Count'])

            if 'Used_Reserve_Block_Count' in self.info and lifetime > int(self.info['Used_Reserve_Block_Count']):
                lifetime = int(self.info['Used_Reserve_Block_Count'])

        elif 'crucial' in vendor_model:
            if 'Remaining_lifetime_Perc' in self.info:
                lifetime = self.info['Remaining_lifetime_Perc']
            
            if 'Percent_Lifetime_Used' in self.info and lifetime > int(self.info['Percent_Lifetime_Used']):
                lifetime = self.info['Percent_Lifetime_Used']
                
        elif 'ocz' in vendor_model and 'Total_Bad_Block_Count' in self.info:
            lifetime = self.info['Total_Bad_Block_Count']
            
        return {'vendor': vendor,
                'model': model,
                'serial': serial,
                'firmware': firmware,
                'size': size,
                'runtime': runtime,
                'written': written,
                'rotation': rotation,
                'lifetime':  lifetime,
                'smart': smart}

