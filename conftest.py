import keyring
import pytest  # noqa F401
from sqlalchemy import make_url


def pytest_addoption(parser):
    parser.addoption("--db-url", action="store", default="mysql://root:pwd@127.0.0.1:3306/test")


def set_keyring(user, password, host):
    def get_password(service, name):
        assert service == "ELFYS_DB"
        if name == "USER":
            return user
        if name == "PASSWORD":
            return password
        if name == "HOST":
            return host
        raise ValueError(f"Unexpected name: {name}")
    
    keyring.get_password = get_password


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "invoke: mark test to invoke commands",
    )
    config.addinivalue_line(
        "markers",
        "isolate_files: mark test to isolate files in a temporary directory",
    )
    url = make_url(config.getoption("db_url"))
    set_keyring(url.username, url.password, url.host)
