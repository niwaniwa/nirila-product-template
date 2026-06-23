"""subagent supervisor.

inotify (or poll fallback) で /shared/requests/*.json を監視し、policy 検証後に
docker compose run でサブエージェントコンテナを固定テンプレで起動する。

設計の唯一の真実: docs/adr/0004-subagent-execution-pattern.md の ER 図 /
状態遷移図 / シーケンス図。
"""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import queue
import re
import select
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from inotify_simple import INotify, flags

LOG = logging.getLogger("supervisor")
logging.basicConfig(
    level=os.environ.get("SUPERVISOR_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

SHARED_DIR = Path(os.environ["SUPERVISOR_SHARED_DIR"])
POLICY_FILE = Path(os.environ["SUPERVISOR_POLICY_FILE"])
WORK_DIR = Path(os.environ["SUPERVISOR_WORK_DIR"])
COMPOSE_FILE = os.environ["SUPERVISOR_COMPOSE_FILE"]
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_SUBAGENTS", "4"))
REQUIRE_APPROVAL = os.environ.get("SUPERVISOR_REQUIRE_APPROVAL", "0") == "1"
APPROVAL_TIMEOUT_SEC = int(os.environ.get("SUPERVISOR_APPROVAL_TIMEOUT_SEC", "60"))
POLL_MS = int(os.environ.get("SUPERVISOR_POLL_MS", "0"))

REQUESTS_DIR = SHARED_DIR / "requests"
RESULTS_DIR = SHARED_DIR / "results"
AUDIT_DIR = SHARED_DIR / "audit"
WORKTREES_DIR = SHARED_DIR / "worktrees"

AGENT_UID = 1000
AGENT_GID = 1000

audit_lock = threading.Lock()
audit_seq = 0


@dataclass
class Policy:
    allowed_image: str
    fixed_service: str
    allowed_request_fields: list[str]
    forbidden_env: list[str]
    forbidden_volume_patterns: list[str]
    max_prompt_length: int
    task_id_pattern: re.Pattern[str]


def load_policy() -> Policy:
    raw = yaml.safe_load(POLICY_FILE.read_text())
    return Policy(
        allowed_image=raw["allowed_image"],
        fixed_service=raw["fixed_service"],
        allowed_request_fields=list(raw["allowed_request_fields"]),
        forbidden_env=list(raw.get("forbidden_env", [])),
        forbidden_volume_patterns=list(raw.get("forbidden_volume_patterns", [])),
        max_prompt_length=int(raw["max_prompt_length"]),
        task_id_pattern=re.compile(raw["task_id_pattern"]),
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_audit_path() -> Path:
    return AUDIT_DIR / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")


def write_audit(task_id: str, event: str, payload: dict[str, Any]) -> None:
    global audit_seq
    with audit_lock:
        audit_seq += 1
        entry = {
            "seq": audit_seq,
            "task_id": task_id,
            "event": event,
            "at": now_iso(),
            "payload": payload,
        }
        path = today_audit_path()
        with path.open("a") as h:
            h.write(json.dumps(entry, ensure_ascii=False) + "\n")
        chown_agent(path)


def chown_agent(path: Path) -> None:
    """agent UID で読めるよう所有権を整える(supervisor は root で動く)。"""
    try:
        os.chown(path, AGENT_UID, AGENT_GID)
    except PermissionError:
        # root でなければスキップ (ローカル開発時)
        pass


def write_result(task_id: str, body: dict[str, Any]) -> None:
    path = RESULTS_DIR / f"{task_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2))
    tmp.replace(path)
    chown_agent(path)


def validate(request: dict[str, Any], policy: Policy) -> tuple[bool, str | None]:
    extra = set(request) - set(policy.allowed_request_fields)
    if extra:
        return False, f"unexpected fields: {sorted(extra)}"

    task_id = request.get("task_id")
    if not isinstance(task_id, str) or not policy.task_id_pattern.match(task_id):
        return False, "invalid task_id"

    prompt = request.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return False, "prompt missing"
    if len(prompt) > policy.max_prompt_length:
        return False, f"prompt too long (max {policy.max_prompt_length})"

    workspace_ref = request.get("workspace_ref", "HEAD")
    if not isinstance(workspace_ref, str):
        return False, "workspace_ref must be string"

    return True, None


def wait_for_approval(task_id: str) -> bool:
    print(f"[supervisor] approve task '{task_id}'? (y/n) ", flush=True)
    rlist, _, _ = select.select([sys.stdin], [], [], APPROVAL_TIMEOUT_SEC)
    if not rlist:
        LOG.warning("approval timeout for %s", task_id)
        return False
    answer = sys.stdin.readline().strip().lower()
    return answer in {"y", "yes"}


def git_worktree_add(task_id: str, ref: str) -> Path:
    path = WORKTREES_DIR / task_id
    if path.exists():
        raise RuntimeError(f"worktree already exists: {path}")
    branch = f"agent/{task_id}"
    # supervisor は root で動くが、リポジトリは agent UID 1000 所有。
    # git の所有者検証を緩めて bind mount したリポジトリを扱えるようにする。
    subprocess.run(
        [
            "git", "-C", str(WORK_DIR),
            "-c", "safe.directory=*",
            "worktree", "add", "-B", branch, str(path), ref,
        ],
        check=True,
        capture_output=True,
    )
    # 子コンテナの agent (UID 1000) が rw できるよう所有権を変える
    for root, dirs, files in os.walk(path):
        for d in dirs:
            chown_agent(Path(root) / d)
        for f in files:
            chown_agent(Path(root) / f)
    chown_agent(path)
    return path


def git_worktree_remove(path: Path) -> None:
    try:
        subprocess.run(
            [
                "git", "-C", str(WORK_DIR),
                "-c", "safe.directory=*",
                "worktree", "remove", "--force", str(path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        LOG.warning("worktree remove failed: %s", e.stderr.decode(errors="replace"))


def docker_compose_run(policy: Policy, worktree: Path, prompt: str) -> int:
    # WORKSPACE env を子の workspace に書き換えて compose の ${WORKSPACE}:/workspace
    # を override する。host-path-matching によりこのパスはホストと一致する前提。
    env = dict(os.environ)
    env["WORKSPACE"] = str(worktree)
    cmd = [
        "docker", "compose",
        "-f", COMPOSE_FILE,
        "run", "--rm",
        "--entrypoint", "claude",
        policy.fixed_service,
        "-p", prompt,
    ]
    LOG.info("spawning: %s (WORKSPACE=%s)", " ".join(cmd), env["WORKSPACE"])
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.stdout:
        LOG.info("child stdout: %s", proc.stdout[-500:])
    if proc.stderr:
        LOG.info("child stderr: %s", proc.stderr[-500:])
    return proc.returncode


def handle_request(req_path: Path, policy: Policy, semaphore: threading.BoundedSemaphore) -> None:
    try:
        raw = req_path.read_text()
        request = json.loads(raw)
    except Exception as e:
        LOG.error("failed to parse %s: %s", req_path, e)
        return

    task_id = str(request.get("task_id", req_path.stem))
    write_audit(task_id, "issued", {"source": str(req_path)})

    # 既に results がある = 重複 task_id
    if (RESULTS_DIR / f"{task_id}.json").exists():
        write_audit(task_id, "rejected", {"reason": "duplicate task_id"})
        write_result(task_id, {
            "task_id": task_id, "status": "rejected",
            "rejected_reason": "duplicate task_id",
            "finished_at": now_iso(),
        })
        return

    ok, reason = validate(request, policy)
    if not ok:
        write_audit(task_id, "rejected", {"reason": reason})
        write_result(task_id, {
            "task_id": task_id, "status": "rejected",
            "rejected_reason": reason,
            "finished_at": now_iso(),
        })
        return
    write_audit(task_id, "validated", {})

    if REQUIRE_APPROVAL and not wait_for_approval(task_id):
        write_audit(task_id, "rejected", {"reason": "approval denied or timeout"})
        write_result(task_id, {
            "task_id": task_id, "status": "rejected",
            "rejected_reason": "approval denied or timeout",
            "finished_at": now_iso(),
        })
        return

    with semaphore:
        started_at = now_iso()
        try:
            worktree = git_worktree_add(task_id, request.get("workspace_ref", "HEAD"))
        except Exception as e:
            write_audit(task_id, "rejected", {"reason": f"worktree: {e}"})
            write_result(task_id, {
                "task_id": task_id, "status": "rejected",
                "rejected_reason": f"worktree: {e}",
                "finished_at": now_iso(),
            })
            return

        write_audit(task_id, "spawned", {"worktree": str(worktree)})

        exit_code = -1
        try:
            exit_code = docker_compose_run(policy, worktree, request["prompt"])
        except Exception as e:
            LOG.exception("docker run failed: %s", e)
        finished_at = now_iso()

        if exit_code == 0:
            git_worktree_remove(worktree)

        write_audit(task_id, "completed", {"exit_code": exit_code})
        write_result(task_id, {
            "task_id": task_id,
            "status": "done" if exit_code == 0 else "rejected",
            "exit_code": exit_code,
            "worktree_path": None if exit_code == 0 else str(worktree),
            "rejected_reason": None if exit_code == 0 else f"child exit {exit_code}",
            "started_at": started_at,
            "finished_at": finished_at,
        })


def request_iter_inotify():
    notifier = INotify()
    watch_flags = flags.CLOSE_WRITE | flags.MOVED_TO
    notifier.add_watch(str(REQUESTS_DIR), watch_flags)
    LOG.info("inotify watching %s", REQUESTS_DIR)
    while True:
        for event in notifier.read():
            if event.name and event.name.endswith(".json"):
                yield REQUESTS_DIR / event.name


def request_iter_poll(interval_sec: float):
    LOG.info("poll-mode watching %s every %.2fs", REQUESTS_DIR, interval_sec)
    seen: set[str] = set()
    while True:
        for p in sorted(REQUESTS_DIR.glob("*.json")):
            key = p.name
            if key in seen:
                continue
            seen.add(key)
            yield p
        time.sleep(interval_sec)


def main() -> None:
    for d in (REQUESTS_DIR, RESULTS_DIR, AUDIT_DIR, WORKTREES_DIR):
        d.mkdir(parents=True, exist_ok=True)
        chown_agent(d)

    policy = load_policy()
    LOG.info(
        "policy loaded: image=%s service=%s max_concurrent=%d approval=%s",
        policy.allowed_image, policy.fixed_service, MAX_CONCURRENT, REQUIRE_APPROVAL,
    )

    semaphore = threading.BoundedSemaphore(MAX_CONCURRENT)
    work_q: queue.Queue[Path] = queue.Queue()

    def worker() -> None:
        while True:
            req = work_q.get()
            try:
                handle_request(req, policy, semaphore)
            except Exception:
                LOG.exception("handler crashed for %s", req)

    # 受け取り側はキューに積む。実処理はワーカー群。
    for _ in range(MAX_CONCURRENT):
        threading.Thread(target=worker, daemon=True).start()

    iterator = (
        request_iter_poll(POLL_MS / 1000.0)
        if POLL_MS > 0
        else request_iter_inotify()
    )
    for req in iterator:
        work_q.put(req)


if __name__ == "__main__":
    main()
