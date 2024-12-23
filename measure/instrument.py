import logging
from random import random
from typing import cast, TypeAlias

import click
import pyvisa
from pyvisa.constants import (
    VI_ERROR_NLISTENERS,
    VI_ERROR_TMO,
)
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
    def __init__(
        self, resource_id: str, name: str, config: dict, rm: pyvisa.ResourceManager,
        logger: logging.Logger
    ):
        self.resource_id = resource_id
        self.name = name
        self.config = config
        self.rm = rm
        self.resource = None
        self.logger = logger
    
    def __enter__(self):
        self.resource = cast(MessageBasedResource, self.rm.open_resource(self.resource_id, **self.config))
        self.check_errors()
        try:
            real_name = self.resource.query('*IDN?')
            self.logger.info(f"Connected to {real_name}")
        except pyvisa.VisaIOError as e:
            self.handle_error(e)
        print(MessageBasedResource, self.resource.query('*IDN?'))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.check_errors()
        self.resource.close()
    
    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.name)
    
    def __eq__(self, other):
        return self.name == other.name and self.resource_id == other.resource_id
    
    def __getattr__(self, name):
        return getattr(self.resource, name)
    
    def check_errors(self):
        if 'SMU 2636' in self.name and isinstance(self.resource, MessageBasedResource):
            try:
                while int(float(self.resource.query("print(errorqueue.count)"))) > 0:
                    error = self.resource.query("print(errorqueue.next())")
                    self.logger.warning(f"Instrument error: {error}")
            except Exception as e:
                self.logger.error(f"Error checking {self} error queue: {e}")
        # TODO: check errors for other instruments
    
    def handle_error(self, e: pyvisa.VisaIOError):
        advice = ""
        if e.error_code == VI_ERROR_TMO:
            advice = ("Try to increase `kwargs.timeout`, `smub.measure.delay` or "
                      "`trigger.timer[1].delay` in the yaml config file.")
        elif e.error_code == VI_ERROR_NLISTENERS:
            advice = ("Check if the instrument is connected and powered on. "
                      "If the problem persists, try to restart or reconnect the instrument.")
        ctx = click.get_current_context()
        automatic = ctx.params.get('automatic', False)
        if automatic:
            raise RuntimeError(f"PyVisaError: {e}\n{advice}")
        click.confirm(f"PyVisaError error: {e}\n{advice}\nDo you want to continue?", abort=True, err=True, default=False)


class TemperatureInstrument:
    def __init__(self, sensor_id, logger: logging.Logger, simulate=False):
        self.sensor_id = sensor_id
        self.simulate = simulate
        self.sensor = None
        self.logger = logger
    
    def __enter__(self):
        if self.simulate:
            return self
        errmsg = YRefParam()
        if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
            raise RuntimeError(f"RegisterHub (temperature sensor) error: {errmsg.value}")
        
        sensor: YTemperature = YTemperature.FindTemperature(self.sensor_id)
        self.sensor = sensor
        if not self.sensor.isOnline():
            raise RuntimeError("Temperature sensor is not connected")
        else:
            self.logger.info(f"Temperature: {self.get_temperature()}°C")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        YAPI.FreeAPI()
    
    def get_temperature(self):
        if self.simulate:
            return random() * 10 + 20
        return self.sensor.get_currentValue()


InstrumentsTypes: TypeAlias = PyVisaInstrument | TemperatureInstrument


class InstrumentFactory:
    def __init__(self, logger: logging.Logger, simulate=False):
        self.logger = logger
        self.simulate = simulate
        if simulate:
            self.rm = pyvisa.ResourceManager("measure/tests/simulation.yaml@sim")
        else:
            self.rm = pyvisa.ResourceManager()
    
    def __call__(self, config) -> InstrumentsTypes:
        kind = config["kind"]
        name = config["name"]
        kwargs = {**DEFAULT_CONFIGS.get(name, {}), **config.get("kwargs", {})}
        resource_id = config["resource"]
        
        if kind == "pyvisa":
            if self.simulate:
                return PyVisaInstrument(
                    "GPIB0::9::INSTR",
                    f"{name} simulation",
                    {'read_termination': '\n', 'write_termination': '\n'},
                    self.rm,
                    self.logger,
                )
            else:
                return PyVisaInstrument(resource_id, name, kwargs, self.rm, self.logger)
        elif kind == "temperature":
            return TemperatureInstrument(resource_id, self.logger, self.simulate)
        else:
            raise ValueError(f"Unknown instrument kind: {kind}")
