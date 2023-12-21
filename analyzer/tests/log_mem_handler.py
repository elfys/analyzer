from logging import (
    Handler,
    LogRecord,
)


class LogMemHandler(Handler):
    def __init__(self):
        self.records = []
        super().__init__()
    
    def handle(self, record: LogRecord) -> bool:
        self.records.append(record)
        return True
    
    def handleError(self, record: LogRecord) -> None:
        self.handle(record)
