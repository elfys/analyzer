from typing import cast

import pandas as pd
import pyvisa

# Initialize the VISA resource manager and open instruments
rm = pyvisa.ResourceManager()
iv = cast(pyvisa.resources.MessageBasedResource, rm.open_resource("GPIB0::1::INSTR"))  # Master tool
iv.timeout = 10000


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


def sweep_voltage_and_collect_data(vlist):
    data = {"Voltage": vlist}
    
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
    
    iv.write("node[1].smua.nvbuffer1.clear()")
    iv.write("node[1].smub.nvbuffer2.clear()")
    iv.write("node[2].smua.nvbuffer1.clear()")
    iv.write("node[2].smub.nvbuffer2.clear()")
    iv.write("node[3].smua.nvbuffer1.clear()")
    iv.write("node[3].smub.nvbuffer2.clear()")
    return data


def save_to_excel(data1, data2, data3):
    with pd.ExcelWriter("jig3.xlsx") as writer:
        df1 = pd.DataFrame(data1)
        df1.to_excel(writer, sheet_name="Sweep 1", index=False)
        
        df2 = pd.DataFrame(data2)
        df2.to_excel(writer, sheet_name="Sweep 2", index=False)
        
        df3 = pd.DataFrame(data3)
        df3.to_excel(writer, sheet_name="Sweep 3", index=False)
    
    print("Data saved to jig4.xlsx")


reset_queue()
iv.write("tsplink.reset()")

set_node_id(1, 1)
set_node_id(2, 2)
set_node_id(3, 3)

configure_master()  # No current limit for the first sweep
configure_other_channels()

# First sweep
vlist1 = [0.01, 0.008, 0.006, 0.004, 0.002, 0, -0.002, -0.004, -0.006, -0.008, -0.01]
data1 = sweep_voltage_and_collect_data(vlist1)

# Second sweep (No current limit)
vlist2 = [-2, -1, 0]
data2 = sweep_voltage_and_collect_data(vlist2)

# Reconfigure with current limit for the third sweep
# configure_master(current_limit=10e-6)
# configure_other_channels()

# Third sweep (With current limit)
vlist3 = list(range(5, 205, 5))
data3 = sweep_voltage_and_collect_data(vlist3)

# Save all sweeps to the same Excel file but in different sheets
save_to_excel(data1, data2, data3)

# Turn off all outputs
iv.write("node[1].smua.source.output = node[1].smua.OUTPUT_OFF")
iv.write("node[1].smub.source.output = node[1].smub.OUTPUT_OFF")
iv.write("node[2].smua.source.output = node[2].smua.OUTPUT_OFF")
iv.write("node[2].smub.source.output = node[2].smub.OUTPUT_OFF")
iv.write("node[3].smua.source.output = node[3].smua.OUTPUT_OFF")
iv.write("node[3].smub.source.output = node[3].smub.OUTPUT_OFF")

iv.close()
rm.close()
