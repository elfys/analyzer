import os
import pathlib
import sys

import sentry_sdk

FROZEN = getattr(sys, "frozen", False)

sentry_sdk.init(
    dsn="https://11a7db21d98f44e8b5c66bf16c463149@o121277.ingest.sentry.io/6630216",
    traces_sample_rate=1.0,
    environment="pyinstaller" if FROZEN else "development" if os.getenv("DEV", None) else "pipenv",
)

if FROZEN:
    os.environ["MPLCONFIGDIR"] = str(pathlib.Path(__file__).parent / "matplotlib" / "appdata")

from analyzer import analyzer  # noqa: E402

if __name__ == "__main__":
    analyzer(windows_expand_args=False)
