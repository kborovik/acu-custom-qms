"""lab5-qms Click console script (T14 / I.cmd / V8 / V10).

Packs Lab5_QMS_Customization.zip, publishes via CustomizationApi, and
seeds post-publish Role Quality Manager + RolesInGraph Delete on QM*
screens. Zip never includes Role, UsersInRoles, or RolesInGraph.
ACU_USER Quality Manager attach stays e2e-only.
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

from pathlib import Path

import click

from lab5_qms import pack, publish


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Pack Lab5_QMS_Customization.zip, publish via CustomizationApi, seed Role Quality Manager."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(deploy)


@cli.command("pack")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="output zip path (default: ./Lab5_QMS_Customization.zip)",
)
def pack_cmd(output: Path | None) -> None:
    """Write Lab5_QMS_Customization.zip (no Role / UsersInRoles / RolesInGraph)."""
    path = pack.write_package(output)
    click.echo(str(path))


@cli.command("publish")
@click.option("--timeout", type=float, default=600.0, show_default=True)
def publish_cmd(timeout: float) -> None:
    """Import and publish Lab5.QMS via CustomizationApi (merge with existing)."""
    status = publish.publish_package(pack.package_zip(), timeout=timeout)
    click.echo(status)


@cli.command("seed")
def seed_cmd() -> None:
    """Post-publish Role Quality Manager + RolesInGraph Delete on QM* screens."""
    with publish.client() as session:
        publish.seed_qm_rights(session)
    click.echo("seeded")


@cli.command("deploy")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="output zip path (default: ./Lab5_QMS_Customization.zip)",
)
@click.option("--timeout", type=float, default=600.0, show_default=True)
def deploy(output: Path | None, timeout: float) -> None:
    """Pack, CustomizationApi publish, and post-publish Role seed."""
    path = pack.write_package(output)
    click.echo(str(path))
    status = publish.publish_package(path.read_bytes(), timeout=timeout)
    click.echo(status)
    with publish.client() as session:
        publish.seed_qm_rights(session)
    click.echo("seeded")


def main() -> None:
    cli()
