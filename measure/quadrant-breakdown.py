from typing import cast

import pandas as pd
import pyvisa

from yoctopuce.yocto_api import (
    YAPI,
    YRefParam,
)
from yoctopuce.yocto_temperature import YTemperature

# Initialize the VISA resource manager and open instruments
rm = pyvisa.ResourceManager()
iv = cast(pyvisa.resources.MessageBasedResource, rm.open_resource("GPIB0::1::INSTR"))  # Master tool
iv.timeout = 10000





errmsg = YRefParam()
if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
    raise RuntimeError(f"RegisterHub (temperature sensor) error: {errmsg.value}")
t = YTemperature.FirstTemperature()
if t is None : sys.exit("No temperature sensor found")       

temp = t.get_currentValue()


def reset_queue():
    try:
        iv.write("*CLS")
    except Exception as e:
        print(f"Error resetting queue: {e}")


def set_node_id(current_node, new_node_id):
    try:
        iv.write(f"node[{current_node}].tsplink.node = {new_node_id}")
    except Exception as e:
        print(f"Error setting node ID {new_node_id} for node {current_node}: {e}")


def configure_master():
    iv.write("reset()")
    iv.write("smua.source.func = smua.OUTPUT_DCVOLTS")
    iv.write("smua.source.autorangev = smua.AUTORANGE_ON")
    iv.write("smua.source.autorangei = smua.AUTORANGE_ON")


def configure_other_channels():
    channels = [
        "node[1].smua",
        "node[1].smub",
        "node[2].smua",
        "node[2].smub",
        "node[3].smua",
        "node[3].smub",
    ]
    for channel in channels:
        iv.write(f"{channel}.source.output = {channel}.OUTPUT_ON")
        iv.write(f"{channel}.measure.nplc = 0.1")
        iv.write(f"{channel}.measure.autozero = {channel}.AUTOZERO_ONCE")
        iv.write(f"{channel}.measure.lowrangei = 1e-9")
        iv.write(f"{channel}.nvbuffer1.clear()")
        iv.write(f"{channel}.nvbuffer2.clear()")
        iv.write(f"{channel}.nvbuffer1.appendmode = 1")
        iv.write(f"{channel}.nvbuffer2.appendmode = 1")
        iv.write(f"{channel}.source.limiti = 2e-5")
        iv.write(f"{channel}.source.levelv = -200")
        

def check_compliance():
    # channels = [
    #     "node[1].smua",
    #     "node[1].smub",
    #     "node[2].smua",
    #     "node[2].smub",
    #     "node[3].smua",
    #     "node[3].smub",
    # ]
    # for channel in channels:
    # result = iv.query(f"print(node[1].smua.source.compliance)")
    # print(type(result))
    if 'true' in iv.query("print(node[1].smua.source.compliance)"):
        return True
    return False


def sweep_voltage_and_collect_data(vlist):
    
    measured_v = []
    
    for voltage in vlist:
        iv.write(f"node[1].smua.source.levelv = {voltage}")
        # Collect data from other channels
        iv.write("node[1].smua.measure.i(node[1].smua.nvbuffer1)")
        iv.write("node[1].smub.measure.i(node[1].smub.nvbuffer2)")
        iv.write("node[2].smua.measure.i(node[2].smua.nvbuffer1)")
        iv.write("node[2].smub.measure.i(node[2].smub.nvbuffer2)")
        iv.write("node[3].smua.measure.i(node[3].smua.nvbuffer1)")
        iv.write("node[3].smub.measure.i(node[3].smub.nvbuffer2)")
        
        iv.query("print(waitcomplete(0))")  # wait all nodes in tsplink to complete
        measured_v.append(voltage)
        if check_compliance() == True:
            bd = -200 - voltage
            print(f'Breakdown detected at {bd} V!')
            break
    data = {"Voltage": measured_v}
    data["Cathode (U1 A)"] = iv.query_ascii_values(
        "printbuffer(1, node[1].smua.nvbuffer1.n, node[1].smua.nvbuffer1.readings)")
    data["Guard (U1 B)"] = iv.query_ascii_values(
        "printbuffer(1, node[1].smub.nvbuffer2.n, node[1].smub.nvbuffer2.readings)")
    data["Q1 (U2 A)"] = iv.query_ascii_values(
        "printbuffer(1, node[2].smua.nvbuffer1.n, node[2].smua.nvbuffer1.readings)")
    data["Q2 (U2 B)"] = iv.query_ascii_values(
        "printbuffer(1, node[2].smub.nvbuffer2.n, node[2].smub.nvbuffer2.readings)")
    data["Q3 (U3 A)"] = iv.query_ascii_values(
        "printbuffer(1, node[3].smua.nvbuffer1.n, node[3].smua.nvbuffer1.readings)")
    data["Q4 (U3 B)"] = iv.query_ascii_values(
        "printbuffer(1, node[3].smub.nvbuffer2.n, node[3].smub.nvbuffer2.readings)")
    
    data["Cathode corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Cathode (U1 A)"))
    data["Guard corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Guard (U1 B)"))
    data["Q1 corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Q1 (U2 A)"))
    data["Q2 corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Q2 (U2 B)"))
    data["Q3 corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Q3 (U3 A)"))
    data["Q4 corrected"] = compute_corrected_current(t.get_currentValue(), data.get("Q4 (U3 B)"))


    iv.write("node[1].smua.nvbuffer1.clear()")
    iv.write("node[1].smub.nvbuffer2.clear()")
    iv.write("node[2].smua.nvbuffer1.clear()")
    iv.write("node[2].smub.nvbuffer2.clear()")
    iv.write("node[3].smua.nvbuffer1.clear()")
    iv.write("node[3].smub.nvbuffer2.clear()")
    return data

def compute_corrected_current(temp: float, current: float):
    target_temperature = 25
    correction_factor = 1.15 ** (target_temperature - temp)
    corrected_current = [i*correction_factor for i in current]
    return  corrected_current


#def save_to_excel(data1, data2, data3):
def save_to_excel(data2, temp):
    filename = f"temperature {temp}.xlsx"
    with pd.ExcelWriter(filename) as writer:
        #df1 = pd.DataFrame(data1)
        #df1.to_excel(writer, sheet_name="Sweep 1", index=False)
        
        df2 = pd.DataFrame(data2)
        df2.to_excel(writer, sheet_name="Sweep 2", index=False)
        
        # df3 = pd.DataFrame(data3)
        # df3.to_excel(writer, sheet_name="Sweep 3", index=False)
    
    print(f"Data saved to {filename}")


reset_queue()
iv.write("tsplink.reset()")

set_node_id(1, 1)
set_node_id(2, 2)
set_node_id(3, 3)

configure_master()  # No current limit for the first sweep
configure_other_channels()

# # First sweep
# #vlist1 = [0.01, 0.008, 0.006, 0.004, 0.002, 0, -0.002, -0.004, -0.006, -0.008, -0.01]
# #data1 = sweep_voltage_and_collect_data(vlist1)

# Second sweep (No current limit)
# vlist2 = [-2, -1, 0]
# data2 = sweep_voltage_and_collect_data(vlist2)

# Reconfigure with current limit for the third sweep
# configure_master(current_limit=10e-6)
# configure_other_channels()

# Third sweep (With current limit)
vlist3 = list(range(-200, 200, 10))
# vlist3 = [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3,3.1,3.2,3.3,3.4,3.5,3.6,3.7,3.8,3.9,4,4.1,4.2,4.3,4.4,4.5,4.6,4.7,4.8,4.9,5,5.1,5.2,5.3,5.4,5.5,5.6,5.7,5.8,5.9,6,6.1,6.2,6.3,6.4,6.5,6.6,6.7,6.8,6.9,7,7.1,7.2,7.3,7.4,7.5,7.6,7.7,7.8,7.9,8,8.1,8.2,8.3,8.4,8.5,8.6,8.7,8.8,8.9,9,9.1,9.2,9.3,9.4,9.5,9.6,9.7,9.8,9.9,10]
data3 = sweep_voltage_and_collect_data(vlist3)

# # Save all sweeps to the same Excel file but in different sheets
# #save_to_excel(data1, data2, data3)

# save_to_excel(data2, data3)
# save_to_excel(data2, data3, temp)
save_to_excel(data3, temp)

# # Turn off all outputs
iv.write("node[1].smua.source.output = node[1].smua.OUTPUT_OFF")
iv.write("node[1].smub.source.output = node[1].smub.OUTPUT_OFF")
iv.write("node[2].smua.source.output = node[2].smua.OUTPUT_OFF")
iv.write("node[2].smub.source.output = node[2].smub.OUTPUT_OFF")
iv.write("node[3].smua.source.output = node[3].smua.OUTPUT_OFF")
iv.write("node[3].smub.source.output = node[3].smub.OUTPUT_OFF")

iv.close()
rm.close()
