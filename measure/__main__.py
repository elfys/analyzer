import os

import sentry_sdk

sentry_sdk.init(
    dsn="https://11a7db21d98f44e8b5c66bf16c463149@o121277.ingest.sentry.io/6630216",
    traces_sample_rate=1.0,
    environment="development" if os.getenv("DEV", False) else "pipenv",
)

from measure import measure_group  # noqa: E402

if __name__ == "__main__":
    measure_group()
