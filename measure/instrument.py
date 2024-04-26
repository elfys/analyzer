import logging

from pyvisa import ResourceManager
from pyvisa.resources import MessageBasedResource


class Instrument:
    resource: MessageBasedResource = None
    
    def __init__(self, rm: ResourceManager, config):
        self.name = config["name"]
        self.rm = rm
        self.config = config
    
    def __enter__(self):
        self.resource = self.rm.open_resource(self.config["resource"], **self.config["kwargs"])
        
        if 'SMU 2636' in self.name:
            self.check_errors(self.resource)
        # TODO: clear errors for other instruments
        
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
        logger = logging.getLogger("analyzer")
        while int(float(instrument.query("print(errorqueue.count)"))) > 0:
            error = instrument.query("print(errorqueue.next())")
            logger.warning(f"Instrument error: {error}")
