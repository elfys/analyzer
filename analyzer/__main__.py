import os
import pathlib
import sys

import sentry_sdk

if __name__ == "__main__":
    # frozen is True when running as a PyInstaller executable
    FROZEN = getattr(sys, "frozen", False)
    
    if FROZEN:
        ENV = "pyinstaller"
        os.environ["MPLCONFIGDIR"] = str(pathlib.Path(__file__).parent / "matplotlib" / "appdata")
    elif os.getenv("DEV") == "True":
        ENV = "development"
    else:
        ENV = "pipenv"
    
    if not ENV == "development":
        sentry_sdk.init(
            dsn="https://11a7db21d98f44e8b5c66bf16c463149@o121277.ingest.sentry.io/6630216",
            traces_sample_rate=1.0,
            environment=ENV,
        )
    
    from analyzer import analyzer
    
    analyzer(windows_expand_args=False)
