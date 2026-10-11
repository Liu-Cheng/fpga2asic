from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tarfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import ServerConfig
from .utils import safe_artifact_path


@dataclass(slots=True)
class ExecutionJob:
    name: str
    workspace: Path
    result_dir: Path
    command: str
    artifacts: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 3600


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    exit_code: int
    result_dir: Path
    stdout: str = ""
    stderr: str = ""
    message: str = ""


class ExecutionError(RuntimeError):
    pass


class Runner:
    def run(self, job: ExecutionJob) -> ExecutionResult:
        raise NotImplementedError


class LocalRunner(Runner):
    def run(self, job: ExecutionJob) -> ExecutionResult:
        job.result_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(job.environment)
        try:
            completed = subprocess.run(
                job.command,
                cwd=job.workspace,
                env=env,
                shell=True,
                text=True,
                capture_output=True,
                timeout=job.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                success=False,
                exit_code=124,
                result_dir=job.result_dir,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                message=f"Local execution timed out after {job.timeout_seconds}s",
            )

        (job.result_dir / "runner.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (job.result_dir / "runner.stderr.log").write_text(completed.stderr, encoding="utf-8")
        for artifact in job.artifacts:
            source = job.workspace / artifact
            if source.is_file():
                destination = safe_artifact_path(job.result_dir, artifact)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        return ExecutionResult(
            success=completed.returncode == 0,
            exit_code=completed.returncode,
            result_dir=job.result_dir,
            stdout=completed.stdout,
            stderr=completed.stderr,
            message="" if completed.returncode == 0 else "Local command failed",
        )


class SSHRunner(Runner):
    """Run an isolated job on a POSIX remote host using system ssh/scp clients.

    The runner uploads a tar archive, executes the configured command without deleting
    remote data, and downloads requested artifacts plus runner logs.
    """

    def __init__(self, server: ServerConfig):
        if server.type != "ssh":
            raise ValueError("SSHRunner requires a server with type='ssh'")
        self.server = server

    def _ssh_base(self) -> list[str]:
        return [
            self.server.ssh_executable,
            *self.server.ssh_options,
            "-p",
            str(self.server.port),
            self.server.destination,
        ]

    def _scp_base(self) -> list[str]:
        return [
            self.server.scp_executable,
            *self.server.ssh_options,
            "-P",
            str(self.server.port),
        ]

    @staticmethod
    def _run_command(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)

    def run(self, job: ExecutionJob) -> ExecutionResult:
        job.result_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", job.name).strip(".-") or "job"
        job_token = f"{safe_name[:80]}-{uuid.uuid4().hex[:12]}"
        remote_dir = f"{self.server.work_root.rstrip('/')}/{job_token}"
        archive = job.result_dir / "job-input.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for path in sorted(job.workspace.rglob("*")):
                if path.is_file():
                    stream.add(path, arcname=path.relative_to(job.workspace).as_posix())

        setup_command = f"mkdir -p -- {shlex.quote(remote_dir)}"
        setup = self._run_command(self._ssh_base() + [setup_command], min(job.timeout_seconds, 120))
        if setup.returncode != 0:
            return self._failure(job, setup.returncode, setup.stdout, setup.stderr, "Remote directory setup failed")

        upload_target = f"{self.server.destination}:{remote_dir}/job-input.tar.gz"
        upload = self._run_command(self._scp_base() + [str(archive), upload_target], min(job.timeout_seconds, 600))
        if upload.returncode != 0:
            return self._failure(job, upload.returncode, upload.stdout, upload.stderr, "Remote upload failed")

        env_prefix = " ".join(
            f"{key}={shlex.quote(value)}" for key, value in sorted(job.environment.items())
        )
        remote_command = (
            f"cd {shlex.quote(remote_dir)} && "
            "tar -xzf job-input.tar.gz && "
            f"({env_prefix} {job.command}) > runner.stdout.log 2> runner.stderr.log; "
            "code=$?; printf '%s' \"$code\" > runner.exitcode; exit $code"
        )
        try:
            execute = self._run_command(self._ssh_base() + [remote_command], job.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return self._failure(
                job,
                124,
                exc.stdout or "",
                exc.stderr or "",
                f"Remote execution timed out after {job.timeout_seconds}s; remote files remain in {remote_dir}",
            )

        download_names = set(job.artifacts) | {"runner.stdout.log", "runner.stderr.log", "runner.exitcode"}
        download_errors: list[str] = []
        for artifact_name in sorted(download_names):
            local_path = safe_artifact_path(job.result_dir, artifact_name)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            remote_path = f"{self.server.destination}:{remote_dir}/{artifact_name}"
            result = self._run_command(
                self._scp_base() + [remote_path, str(local_path)],
                min(job.timeout_seconds, 600),
            )
            if result.returncode != 0 and artifact_name in job.artifacts:
                download_errors.append(f"{artifact_name}: {result.stderr.strip()}")

        message_parts = []
        if execute.returncode != 0:
            message_parts.append(f"Remote command failed; workspace retained at {remote_dir}")
        if download_errors:
            message_parts.append("Artifact download errors: " + "; ".join(download_errors))
        return ExecutionResult(
            success=execute.returncode == 0 and not download_errors,
            exit_code=execute.returncode,
            result_dir=job.result_dir,
            stdout=execute.stdout,
            stderr=execute.stderr,
            message=". ".join(message_parts),
        )

    @staticmethod
    def _failure(
        job: ExecutionJob,
        exit_code: int,
        stdout: str,
        stderr: str,
        message: str,
    ) -> ExecutionResult:
        (job.result_dir / "runner.stdout.log").write_text(stdout, encoding="utf-8")
        (job.result_dir / "runner.stderr.log").write_text(stderr, encoding="utf-8")
        return ExecutionResult(False, exit_code, job.result_dir, stdout, stderr, message)


def make_runner(server: ServerConfig) -> Runner:
    if server.type == "local":
        return LocalRunner()
    if server.type == "ssh":
        return SSHRunner(server)
    raise ValueError(f"Unsupported server type: {server.type}")
