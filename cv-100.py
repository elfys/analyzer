from typing import cast

import numpy as np
import pandas as pd
import pyvisa

rm = pyvisa.ResourceManager()


cv = cast(pyvisa.resources.MessageBasedResource, rm.open_resource('GPIB0::17::INSTR'))
cv.timeout = 15000
iv = cast(pyvisa.resources.MessageBasedResource, rm.open_resource('GPIB0::1::INSTR'))
iv.timeout = 10000

cv.write('*RST; *CLS')
cv.write(':FUNC:IMP:TYPE CSD')
cv.write(':FREQ:CW 100000')
cv.write(':VOLT:LEVEL 0.02')
cv.write(':CORR:OPEN:STAT ON')
cv.write(':FUNC:IMP:RANGE:AUTO ON')
cv.write(':FORM:DATA ASC')
cv.write(':LIST:MODE SEQ')
cv.write(':MMEM EXT')

iv.write("reset()")
iv.write("smua.source.func = smua.OUTPUT_DCVOLTS")
iv.write("smua.source.autorangev = smua.AUTORANGE_ON")
iv.write("smua.source.autorangei = smua.AUTORANGE_ON")
# iv.write("smua.source.limiti = 10e-3") #add complience limit
iv.write('smua.measure.nplc = 1')
iv.write('smua.measure.autozero = smua.AUTOZERO_ONCE')
iv.write('smua.measure.lowrangei=1e-9')
iv.write('smua.measure.delay = 5')
iv.write("smua.source.output = smua.OUTPUT_ON")
iv.write('smua.nvbuffer1.clear()')

voltages = np.arange(-100, 1, 1)
capacitance_values = []
voltages_to_write = []
threshold = 100e-12
for i, voltage in enumerate(voltages):
    iv.write(f'smua.source.levelv = {voltage}')
    cv.write('TRIG:SOUR BUS')
    cv.write('DISP:PAGE MEAS')
    cv.write(':MEM:DIM DBUF, 1')
    cv.write(':MEM:FILL DBUF')
    cv.write('TRIGGER:IMMEDIATE')
    output = cv.query_ascii_values(':MEM:READ? DBUF')
    capacitance = output[::4]
    
    if len(capacitance_values) > 1:
        deviation = abs(capacitance[0] - capacitance_values[-1])
        if deviation > threshold:
            break
    
    capacitance_values.append(capacitance[0])
    cv.write(':MEM:CLE DBUF')
    iv.write('smua.nvbuffer1.clear()')

data = {'Voltage': voltages[:len(capacitance_values)], 'Capacitance': capacitance_values}
df = pd.DataFrame(data)
df.to_excel('capacitance_data.xlsx', index=False)
