import click

from analyzer.context import (
    AnalyzerContext,
)
from analyzer.summary.cv import summary_cv
from analyzer.summary.eqe import summary_eqe
from analyzer.summary.iv import summary_iv
from orm import (
    WaferRepository,
)


@click.group(
    name="summary",
    help="Group of command to analyze and summarize the data",
    commands=[summary_iv, summary_cv, summary_eqe],
)
@click.pass_context
def summary_group(ctx: click.Context):
    active_command = summary_group.commands.get(ctx.invoked_subcommand)
    if active_command is None:
        return
    
    obj = ctx.find_object(AnalyzerContext)
    try:
        wafer_option = next(
            (o for o in active_command.params if o.name == "wafer_name" and o.prompt)
        )
        last_wafer = WaferRepository(obj.session).get_last()
        wafer_option.default = last_wafer.name
    except StopIteration:
        ...
