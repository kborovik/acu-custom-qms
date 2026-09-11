"""acuqms Click console script (T14 / T15 / T16 / T25 / T41 / T47 / I.cmd / V8 / V10 / V14 / V18).

Packs Lab5_QMS_Customization.zip, publishes via CustomizationApi, and
seeds post-publish Role Quality Manager + RolesInGraph Delete on QM*
screens + UsrQMSSetup (QORD QNCR) per company when missing.
Zip never includes Role, UsersInRoles, or RolesInGraph.
ACU_USER Quality Manager attach stays e2e-only.
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

from pathlib import Path

import click

from acuqms import pack, publish
from acuqms.progress import progress


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Build Lab5_QMS_Customization.zip, publish via CustomizationApi, seed Role Quality Manager."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


def _write_zip(output: Path | None) -> Path:
    with progress("pack zip", str(output or pack.PACKAGE_ZIP)) as p:
        path = pack.write_package(output, ensure_dll=True)
        p.target = str(path)
        return path


@cli.command("build")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="output zip path (default: ./Lab5_QMS_Customization.zip)",
)
def build_cmd(output: Path | None) -> None:
    """Write Lab5_QMS_Customization.zip (no Role / UsersInRoles / RolesInGraph)."""
    click.echo(str(_write_zip(output)))


@cli.command("publish")
@click.option("--timeout", type=float, default=900.0, show_default=True)
def publish_cmd(timeout: float) -> None:
    """Import and publish Lab5.QMS via CustomizationApi (merge with existing)."""
    status = publish.publish_package(pack.package_zip(ensure_dll=True), timeout=timeout)
    click.echo(status)


@cli.command("seed")
def seed_cmd() -> None:
    """Post-publish Role Quality Manager, RolesInGraph Delete on QM*, EntityMapping Tests/Results, UsrQMSSetup."""
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
@click.option("--timeout", type=float, default=900.0, show_default=True)
def deploy(output: Path | None, timeout: float) -> None:
    """Build zip, CustomizationApi publish, and post-publish Role + EntityMapping + UsrQMSSetup seed."""
    path = _write_zip(output)
    click.echo(str(path))
    zip_bytes = path.read_bytes()
    status = publish.publish_package(zip_bytes, timeout=timeout)
    click.echo(status)
    with publish.client() as session:
        publish.seed_qm_rights(session)
    with publish.client() as session:
        live = publish.qms_endpoint_live(session)
    if not live:
        status = publish.publish_package(zip_bytes, timeout=timeout)
        click.echo(status)
        with publish.client() as session:
            publish.seed_qm_rights(session)
    click.echo("seeded")


def main() -> None:
    cli()
