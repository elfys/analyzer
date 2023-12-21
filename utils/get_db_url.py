import keyring
from sqlalchemy import engine


def get_db_url(username=None, password=None, host=None) -> engine.URL:
    if username is None:
        username = keyring.get_password("ELFYS_DB", "USER")
    if password is None:
        password = keyring.get_password("ELFYS_DB", "PASSWORD")
    if host is None:
        host = keyring.get_password("ELFYS_DB", "HOST")
    
    return engine.URL.create(
        "mysql",
        username=username,
        password=password,
        host=host,
        database="elfys",
        port=3306,
    )
