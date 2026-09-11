"""Repo paths for the Lab5.QMS customization product under QMS/."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CUSTOMIZATION_DIR = "QMS"
FRONTEND_SCREENS_REL = (
    Path(CUSTOMIZATION_DIR)
    / "FrontendSources"
    / "screen"
    / "src"
    / "development"
    / "screens"
)


def customization_root(root: Path | None = None) -> Path:
    return (REPO_ROOT if root is None else Path(root)) / CUSTOMIZATION_DIR


def cs_root(root: Path | None = None) -> Path:
    return customization_root(root) / "Lab5.QMS"


def pages_qm(root: Path | None = None) -> Path:
    return customization_root(root) / "Pages" / "QM"


def screens_root(root: Path | None = None) -> Path:
    return (REPO_ROOT if root is None else Path(root)) / FRONTEND_SCREENS_REL


def project_dir(root: Path | None = None) -> Path:
    return customization_root(root) / "_project"


def sql_file(root: Path | None = None) -> Path:
    return customization_root(root) / "SQL" / "CreateQMSTables.sql"


CUSTOMIZATION_ROOT = customization_root()
CS_ROOT = cs_root()
PAGES_QM = pages_qm()
SCREENS = screens_root()
PROJECT_DIR = project_dir()
SQL_FILE = sql_file()
