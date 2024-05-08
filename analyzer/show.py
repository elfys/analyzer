import click
import pandas as pd
from sqlalchemy import (
    func,
    select,
)

from orm import (
    Chip,
    Wafer,
)
from .context import (
    AnalyzerContext,
    pass_analyzer_context,
)


@click.command(
    name="wafers",
    help="""Show all wafers.

\b Batch id is a unique identifier decoding the batch production information.

\b Example 1: PFM2236, where P - PD product, F - Topsil method (Fz), M - medium resistivity
(700-1200ohm-cm), 22 - year, 36 - week, A - parent (if applicable)

\b Example 2: SFM2236, where S - SM product, C - Okmetic method (Cz), H - high resistivity
(>1200ohm-cm), 22 - year, 36 - week, B - split batch (if applicable)
""",
)
@click.option("--json", is_flag=True, help="Output as JSON.")
@pass_analyzer_context
def show_wafers(ctx: AnalyzerContext, json: bool):
    wafers_query = (
        select(
            Wafer,
            func.count(Chip.id).label("chips_count"),
        )
        .join(Wafer.chips)
        .group_by(Wafer.id)
        .order_by(Wafer.record_created_at.desc())
    )
    wafers_df = pd.read_sql(wafers_query, ctx.session.connection(), index_col="id")
    
    if json:
        click.echo(wafers_df.to_json(orient="index", indent=4))
    else:
        wafers_df.rename(
            columns={
                "chips_count": "Chips",
                "record_created_at": "Created at",
                "batch_id": "Batch",
                "type": "Type",
                "name": "Name",
            },
            inplace=True,
        )
        wafers_df.fillna("", inplace=True)
        click.echo_via_pager(
            wafers_df.to_string(
                formatters={
                    "Created at": lambda x: x.strftime("%Y-%m-%d"),
                },
                col_space=[10, 15, 15, 10, 8],
            )
        )


@click.group(name="show", commands=[show_wafers], help="Show data from database")
def show_group():
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_rows", None)
    pd.set_option("styler.format.formatter", lambda: print("called"))
