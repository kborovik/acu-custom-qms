"""PATH `acu` CLI + local REST session (T18 / V11 / I.cli).

Released `acu` comes from `uv tool install acumatica-cli`. This module
invokes that binary (`acu config show`, `acu tenant list`) and speaks
CustomizationApi / contract REST over httpx. The CLI package is not a
Python import. acu is never launched through uv. Never prints ACU_PASSWORD.
"""

from __future__ import annotations

import base64
import html
import os
import re
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_API_VERSION = "25.200.001"
ACU_INSTANCE_PATH = r"C:\Acumatica\AcumaticaERP"
DB_NAME = "AcumaticaDB"
ACU_TIMEOUT = 60.0
HTTP_TIMEOUT = 30.0
SSH_TIMEOUT = 30.0


@dataclass(frozen=True)
class Instance:
    """Resolved target from `acu config show` plus ACU_PASSWORD out of band."""

    base_url: str
    ssh: str = ""
    tenant: str = ""
    api_version: str = DEFAULT_API_VERSION
    user: str = "admin"
    password: str = field(default="", repr=False)


@dataclass(frozen=True)
class Tenant:
    company_id: int
    login_name: str
    company_cd: str
    company_type: str


def run_acu(
    *args: str,
    timeout: float = ACU_TIMEOUT,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run PATH `acu` (never through uv). `.env` walk-up is acu's."""
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    try:
        return subprocess.run(
            ["acu", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "acu not on PATH — install the released CLI with "
            "`uv tool install acumatica-cli`"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"acu {' '.join(args)} timed out after {timeout:.0f}s"
        ) from exc


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_lines(text: str) -> dict[str, str]:
    """Parse `acu config show` (.env document). Drops ACU_PASSWORD if present."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.startswith("ACU_"):
            out[key] = _unquote(value)
    out.pop("ACU_PASSWORD", None)
    return out


def find_dotenv() -> Path | None:
    for directory in [Path.cwd(), *Path.cwd().parents]:
        path = directory / ".env"
        if path.is_file():
            return path
    return None


def _password_from_dotenv() -> str:
    path = find_dotenv()
    if path is None:
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("ACU_PASSWORD="):
            return _unquote(stripped.partition("=")[2])
    return ""


def load_instance() -> Instance:
    """Resolve via `acu config show`; password from env or walk-up .env."""
    result = run_acu("config", "show")
    if result.returncode != 0:
        raise RuntimeError(
            f"acu config show failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    fields = parse_env_lines(result.stdout)
    password = os.environ.get("ACU_PASSWORD") or _password_from_dotenv()
    if not password:
        raise RuntimeError(
            "password not set (put ACU_PASSWORD in .env or the environment)"
        )
    base_url = fields.get("ACU_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("acu config show did not emit ACU_BASE_URL")
    return Instance(
        base_url=base_url,
        ssh=fields.get("ACU_SSH", ""),
        tenant=fields.get("ACU_TENANT", ""),
        api_version=fields.get("ACU_API_VERSION") or DEFAULT_API_VERSION,
        user=fields.get("ACU_USER") or "admin",
        password=password,
    )


def parse_tenant_list(text: str) -> list[Tenant]:
    """Parse piped `acu tenant list` (ID Login CD Type)."""
    tenants: list[Tenant] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        tenants.append(
            Tenant(
                company_id=int(parts[0]),
                login_name=parts[1],
                company_cd=parts[2],
                company_type=parts[3] if len(parts) > 3 else "",
            )
        )
    return tenants


def list_tenants() -> list[Tenant]:
    result = run_acu("tenant", "list")
    if result.returncode != 0:
        raise RuntimeError(
            f"acu tenant list failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return parse_tenant_list(result.stdout)


def ssh_run(
    command: str, *, host: str | None = None, timeout: float | None = None
) -> str:
    """SSH PowerShell on the instance; host from `acu config show` when omitted."""
    target = host if host is not None else load_instance().ssh
    if not target:
        raise RuntimeError("ACU_SSH empty — hosted path has no ssh")
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                target,
                command + "\nexit $LASTEXITCODE",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ssh timed out after {timeout:.0f}s" if timeout else "ssh timed out"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"remote command failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def wrap(record: dict[str, Any]) -> dict[str, Any]:
    """Plain dict → contract-API body: {"Field": {"value": ...}}."""

    def _value(value: Any) -> Any:
        if isinstance(value, list):
            return [wrap(row) if isinstance(row, dict) else row for row in value]
        if isinstance(value, dict):
            return wrap(value)
        return {"value": value}

    return {k: v if k in ("id", "delete") else _value(v) for k, v in record.items()}


def unwrap(entity: dict[str, Any]) -> dict[str, Any]:
    """Contract-API entity → plain dict (value fields + detail arrays)."""
    out: dict[str, Any] = {}
    for key, value in entity.items():
        if isinstance(value, dict) and "value" in value:
            out[key] = value["value"]
        elif isinstance(value, dict):
            nested = unwrap(value)
            if nested:
                out[key] = nested
        elif (
            isinstance(value, list)
            and value
            and all(isinstance(row, dict) for row in value)
        ):
            rows = [unwrap(row) for row in value]
            if any(rows):
                out[key] = rows
    return out


def parse_entity_response(
    response: httpx.Response,
) -> tuple[list[tuple[str, str]], str | None]:
    """Parse GET /entity → (endpoints, optional build version)."""
    try:
        body = response.json()
    except Exception as exc:
        hint = response.text[:200].replace("\n", " ")
        raise RuntimeError(
            "GET /entity response not parseable as endpoint list "
            f"(status {response.status_code}; "
            f"content-type {response.headers.get('content-type', '?')}; "
            f"first 200 chars: {hint})"
        ) from exc
    rows = _entity_list_rows(body)
    if rows is None:
        hint = str(body)[:200]
        raise RuntimeError(
            "GET /entity response not parseable as endpoint list "
            f"(status {response.status_code}; expected non-empty JSON array "
            "or object with non-empty 'endpoints' array; "
            f"first 200 chars: {hint})"
        )
    out: list[tuple[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise RuntimeError(
                "GET /entity response not parseable as endpoint list "
                f"(row is not an object: {item!r})"
            )
        name = item.get("name")
        version = item.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise RuntimeError(
                "GET /entity response not parseable as endpoint list "
                f"(row missing string name/version: {item!r})"
            )
        out.append((name, version))
    return out, _entity_build_version(body)


def _entity_list_rows(body: Any) -> list[Any] | None:
    if isinstance(body, list) and body:
        return body
    if isinstance(body, dict):
        endpoints = body.get("endpoints")
        if isinstance(endpoints, list) and endpoints:
            return endpoints
    return None


def _entity_build_version(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    version = body.get("version")
    if not isinstance(version, dict):
        return None
    build = version.get("acumaticaBuildVersion")
    if isinstance(build, str) and build:
        return build
    return None


class AcumaticaClient:
    """Cookie-session client for the contract-based endpoint."""

    poll_interval: float = 1.0

    def __init__(self, instance: Instance, timeout: float = HTTP_TIMEOUT) -> None:
        self.instance = instance
        self._http = httpx.Client(base_url=instance.base_url, timeout=timeout)

    def __enter__(self) -> AcumaticaClient:
        if not self.instance.tenant:
            raise RuntimeError(
                f"no tenant set for {self.instance.base_url} - a session without "
                "an explicit tenant silently lands on the default tenant; "
                "set ACU_TENANT in .env"
            )
        try:
            self._login()
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            self._http.post("/entity/auth/logout", content=b"")
        finally:
            self._http.close()

    def _login(self) -> None:
        creds = {
            "name": self.instance.user,
            "password": self.instance.password,
            "tenant": self.instance.tenant,
        }
        self._checked(self._http.post("/entity/auth/login", json=creds))
        landed = self._landed_tenant()
        if landed.casefold() != self.instance.tenant.casefold():
            raise RuntimeError(
                f"tenant guard: asked for tenant {self.instance.tenant!r} "
                f"but the session landed on {landed!r} - check "
                "acu tenant list"
            )

    def relogin(self) -> None:
        self._http.post("/entity/auth/logout", content=b"")
        self._login()

    def _landed_tenant(self) -> str:
        response = self._checked(
            self._http.get("/Frames/Login.aspx", follow_redirects=True)
        )
        match = re.search(r'id="txtSingleCompany" value="([^"]*)"', response.text)
        if not match:
            raise RuntimeError(
                "tenant guard: /Frames/Login.aspx did not expose the landed "
                "tenant (txtSingleCompany missing); refusing the session"
            )
        return html.unescape(match.group(1))

    def _url(self, entity: str, endpoint: str | None = None) -> str:
        if endpoint is None or endpoint == "default":
            endpoint = f"Default/{self.instance.api_version}"
        return f"/entity/{endpoint}/{entity}"

    def list_endpoints(self) -> list[tuple[str, str]]:
        return self.entity_root()[0]

    def entity_root(self) -> tuple[list[tuple[str, str]], str | None]:
        return parse_entity_response(self._checked(self._http.get("/entity")))

    @staticmethod
    def _field_errors(body: object, *, prefix: str = "") -> list[str]:
        found: list[str] = []
        if isinstance(body, dict):
            err = body.get("error")
            keys = set(body.keys())
            is_field = "value" in keys or keys <= {"error", "value", "id", "delete"}
            if isinstance(err, str) and err.strip() and is_field and prefix:
                found.append(f"{prefix}: {err.strip()}")
            for key, child in body.items():
                if key in ("error", "exceptionMessage", "exceptionType", "message"):
                    continue
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                found.extend(AcumaticaClient._field_errors(child, prefix=child_prefix))
        elif isinstance(body, list):
            for i, child in enumerate(body):
                child_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
                found.extend(AcumaticaClient._field_errors(child, prefix=child_prefix))
        return found

    @staticmethod
    def _checked(response: httpx.Response) -> httpx.Response:
        if response.is_error:
            detail = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = (
                        body.get("exceptionMessage")
                        or body.get("message")
                        or body.get("error")
                        or ""
                    )
                    if not detail and isinstance(body.get("innerException"), dict):
                        inner = body["innerException"]
                        detail = (
                            inner.get("exceptionMessage") or inner.get("message") or ""
                        )
                    field_errs = AcumaticaClient._field_errors(body)
                    if field_errs:
                        joined = "; ".join(field_errs)
                        detail = f"{detail}; {joined}" if detail else joined
                    if not detail:
                        import json

                        detail = json.dumps(body, separators=(",", ":"))[:500]
                elif isinstance(body, list) and body:
                    detail = str(body[0])[:500]
            except Exception:
                detail = (response.text or "")[:500]
            raise RuntimeError(
                f"{response.request.method} {response.request.url.path} "
                f"-> {response.status_code}" + (f": {detail}" if detail else "")
            )
        return response

    def get_list(
        self,
        entity: str,
        params: dict[str, str] | None = None,
        endpoint: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._checked(
            self._http.get(self._url(entity, endpoint), params=params)
        ).json()

    def get_record(
        self,
        entity: str,
        keys: Sequence[Any],
        endpoint: str | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        path = "/".join(quote(str(k), safe="") for k in keys)
        response = self._http.get(
            f"{self._url(entity, endpoint)}/{path}", params=params
        )
        if response.status_code == 500:
            try:
                missing = "NoEntitySatisfiesTheCondition" in response.json().get(
                    "exceptionType", ""
                )
            except Exception:
                missing = False
            if missing:
                return None
        return self._checked(response).json()

    def put(
        self,
        entity: str,
        record: dict[str, Any],
        endpoint: str | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._checked(
            self._http.put(
                self._url(entity, endpoint), json=wrap(record), params=params
            )
        ).json()

    @staticmethod
    def _checked_log(response: httpx.Response) -> dict[str, Any]:
        AcumaticaClient._checked(response)
        try:
            body: dict[str, Any] = response.json()
        except ValueError:
            return {}
        log = body.get("log")
        errors = [
            str(entry.get("message", ""))
            for entry in (log if isinstance(log, list) else [])
            if isinstance(entry, dict) and entry.get("logType") == "error"
        ]
        if errors:
            raise RuntimeError(
                f"POST {response.request.url.path} reported: " + "; ".join(errors)
            )
        return body

    def customization_published(self) -> list[str]:
        body = self._checked_log(
            self._http.post("/CustomizationApi/getPublished", json={})
        )
        projects = body.get("projects") or []
        return [p["name"] for p in projects if isinstance(p, dict) and "name" in p]

    def customization_project_content(self, name: str) -> bytes | None:
        try:
            body = self._checked_log(
                self._http.post(
                    "/CustomizationApi/getProject", json={"projectName": name}
                )
            )
        except RuntimeError:
            return None
        content = body.get("projectContentBase64")
        if not isinstance(content, str) or not content:
            return None
        return base64.b64decode(content)

    def customization_import(
        self, name: str, zip_bytes: bytes, description: str = ""
    ) -> None:
        self._checked_log(
            self._http.post(
                "/CustomizationApi/import",
                json={
                    "projectLevel": 0,
                    "isReplaceIfExists": True,
                    "projectName": name,
                    "projectDescription": description,
                    "projectContentBase64": base64.b64encode(zip_bytes).decode("ascii"),
                },
            )
        )

    def customization_publish_end(self) -> dict[str, Any]:
        return self._checked(
            self._http.post("/CustomizationApi/publishEnd", json={})
        ).json()


@contextmanager
def client(timeout: float = HTTP_TIMEOUT) -> Iterator[AcumaticaClient]:
    with AcumaticaClient(load_instance(), timeout=timeout) as session:
        yield session
