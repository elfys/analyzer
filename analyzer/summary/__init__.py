import click
from sqlalchemy import desc
from sqlalchemy.orm import Session

from analyzer.summary.cv import summary_cv
from analyzer.summary.eqe import summary_eqe
from analyzer.summary.iv import summary_iv
from orm import Wafer


@click.group(
    name="summary",
    help="Group of command to analyze and summarize the data",
    commands=[summary_iv, summary_cv, summary_eqe],
)
@click.pass_context
def summary_group(ctx: click.Context):
    session: Session = ctx.obj["session"]
    active_command = summary_group.commands[ctx.invoked_subcommand]
    
    try:
        wafer_option = next(
            (o for o in active_command.params if o.name == "wafer_name" and o.prompt)
        )
        last_wafer = session.query(Wafer).order_by(desc(Wafer.record_created_at)).first()
        default_wafer_name = last_wafer.name
        wafer_option.default = default_wafer_name
        ctx.obj["default_wafer"] = last_wafer
    except StopIteration:
        ...
