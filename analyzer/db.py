import os
import subprocess
import time
from typing import Optional

import click
import keyring
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url

from utils import get_db_url


@click.command(name="set", help="Set database credentials.")
@click.option("--username", "-u", help="Database username.")
@click.option("--password", "-p", help="Database password.")
@click.option("--host", "-h", help="Database host.")
@click.pass_context
def set_db(
    ctx: click.Context, username: Optional[str], password: Optional[str], host: Optional[str]
):
    if username:
        keyring.set_password("ELFYS_DB", "USER", username)
    if password:
        keyring.set_password("ELFYS_DB", "PASSWORD", password)
    if host:
        keyring.set_password("ELFYS_DB", "HOST", host)

    if username or password or host:
        ctx.exit()

    username = click.prompt("Username")
    password = click.prompt("Password")
    host = click.prompt("Host")

    db_url = get_db_url(username=username, password=password, host=host)
    engine = create_engine(db_url)
    try:
        engine.connect().close()
        keyring.set_password("ELFYS_DB", "PASSWORD", password)
        keyring.set_password("ELFYS_DB", "USER", username)
        keyring.set_password("ELFYS_DB", "HOST", host)
        ctx.obj["logger"].info("Database credentials are set. Now you can use analyzer commands.")
    except OperationalError:
        ctx.obj["logger"].warning(
            "Cannot connect to the database with given credentials. Saving credentials is rejected."
        )


@click.command(name="dump", help="Dump database to .sql.gz file.")
@click.pass_context
@click.option("--limit", "-l", type=int, help="Limit number of rows in each table.")
def dump_db(ctx: click.Context, limit: Optional[int]):
    db_url = make_url(find_in_ctx(ctx, "db_url") or get_db_url())
    ctx.obj["logger"].info("Saving database dump... This may take a while.")

    dump_file = f'dump_{time.strftime("%Y%m%d_%H%M%S")}.sql.gz'
    command = f"docker run --rm -i mysql:latest \
        mysqldump --no-tablespaces --host={db_url.host} --port={db_url.port} \
        --user={db_url.username} -p {db_url.database}"
    if limit:
        command = f'{command} --where="1 limit {limit}"'
    mysqldump = subprocess.Popen(
        command,
        shell=True,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mysqldump.stdin.write(db_url.password + os.linesep)
    mysqldump.stdin.flush()

    gzip = subprocess.Popen(
        f"gzip -9 > {dump_file}",
        shell=True,
        text=True,
        stdin=mysqldump.stdout,
        stderr=subprocess.PIPE,
    )

    mysqldump.wait()
    output, error = mysqldump.communicate()
    error = error.replace("Enter password: ", "")
    if error:
        ctx.obj["logger"].warning(error)
    if mysqldump.returncode != 0:
        ctx.obj["logger"].error("Error while dumping database")
        ctx.exit(mysqldump.returncode)

    output, error = gzip.communicate()
    if error:
        ctx.obj["logger"].warning(error)
    if gzip.returncode != 0:
        ctx.obj["logger"].error("Error while compressing dump")
        ctx.exit(gzip.returncode)

    ctx.obj["logger"].info(f"Database dumped to {dump_file}")
    return db_url


@click.group(
    name="db",
    help="Set of commands to manage related database",
    commands=[set_db, dump_db],
)
def db_group():
    ...


def find_in_ctx(ctx: click.Context, key: str):
    if key in ctx.params:
        return ctx.params[key]
    elif key in ctx.obj:
        return ctx.obj[key]
    elif ctx.parent:
        return find_in_ctx(ctx.parent, key)
    else:
        return None
