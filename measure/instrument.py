import logging
from random import random

import pyvisa
from pyvisa.resources import (
    MessageBasedResource,
)
from yoctopuce.yocto_api import (
    YAPI,
    YRefParam,
)
from yoctopuce.yocto_temperature import YTemperature

DEFAULT_CONFIGS = {
    'Scanner 705': {
        'read_termination': '\n',
        'write_termination': '\n',
        'timeout': 500,
    },
}


class PyVisaInstrument:
    def __init__(self, resource_id, name, config, rm):
        self.resource_id = resource_id
        self.name = name
        self.config = config
        self.rm = rm
        self.resource = None
    
    def __enter__(self):
        try:
            self.resource = self.rm.open_resource(self.resource_id, **self.config)
        except pyvisa.Error as e:
            try:
                self.resource.close()
            except Exception:
                pass
            logger = logging.getLogger("measure")
            logger.error(f"PYVISA error: {e}")
        
        if 'SMU 2636' in self.name:
            self.check_errors(self.resource)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if 'SMU 2636' in self.name:
            self.check_errors(self.resource)
        # TODO: check errors for other instruments
        self.resource.close()
    
    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.name)
    
    def __eq__(self, other):
        return self.name == other.name and self.config["resource"] == other.config["resource"]
    
    def __getattr__(self, name):
        return getattr(self.resource, name)
    
    def check_errors(self, instrument: MessageBasedResource):
        logger = logging.getLogger("measure")
        while int(float(instrument.query("print(errorqueue.count)"))) > 0:
            error = instrument.query("print(errorqueue.next())")
            logger.warning(f"Instrument error: {error}")


class TemperatureInstrument:
    def __init__(self, sensor_id, simulate=False):
        self.sensor_id = sensor_id
        self.simulate = simulate
        self.sensor = None
    
    def __enter__(self):
        if self.simulate:
            return self
        errmsg = YRefParam()
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            raise RuntimeError("RegisterHub (temperature sensor) error: " + errmsg.value)
        
        # TODO: does it work with simple 'temperature' instead of sensor_id?
        sensor: YTemperature = YTemperature.FindTemperature(self.sensor_id)
        if not (sensor.isOnline()):
            raise RuntimeError("Temperature sensor is not connected")
        self.sensor = sensor
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        YAPI.FreeAPI()
    
    def get_temperature(self):
        if self.simulate:
            return random() * 10 + 20
        return self.sensor.get_currentValue()


type InstrumentsTypes = PyVisaInstrument | TemperatureInstrument


class InstrumentFactory:
    def __call__(self, config, simulate=False) -> InstrumentsTypes:
        kind = config["kind"]
        name = config["name"]
        kwargs = {**DEFAULT_CONFIGS.get(name, {}), **config.get("kwargs", {})}
        resource_id = config["resource"]
        
        if kind == "pyvisa":
            if simulate:
                rm = pyvisa.ResourceManager("measure/tests/simulation.yaml@sim")
                return PyVisaInstrument(
                    "GPIB0::9::INSTR",
                    f"{name} simulation",
                    {'read_termination': '\n', 'write_termination': '\n'},
                    rm,
                )
            else:
                rm = pyvisa.ResourceManager()
                return PyVisaInstrument(resource_id, name, kwargs, rm)
        elif kind == "temperature":
            return TemperatureInstrument(resource_id, simulate)
        else:
            raise ValueError(f"Unknown instrument kind: {kind}")
