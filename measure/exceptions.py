class InvalidMeasurementError(RuntimeError):
    def __init__(self, message: str = "Measurement is invalid"):
        super().__init__(message)
