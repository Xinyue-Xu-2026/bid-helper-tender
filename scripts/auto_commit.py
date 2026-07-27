#!/usr/bin/env python3
"""
自动版本管理脚本

监控项目源码目录，当文件发生变化时自动执行 git add + commit + push。

用法：
    python -u scripts/auto_commit.py

按 Ctrl+C 停止监控。
"""

import os
import subprocess
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


WATCH_PATHS = ["src", "tests", "main.py", "pyproject.toml", "requirements.txt", "README.md"]
DEBOUNCE_SECONDS = 3.0


class AutoCommitHandler(FileSystemEventHandler):
    def __init__(self):
        self._last_event_time = 0
        self._pending = False

    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.event_type == "opened":
            return
        # 忽略 pycache 和临时文件
        if "__pycache__" in event.src_path or event.src_path.endswith(".tmp"):
            return
        self._pending = True
        self._last_event_time = time.time()

    def check_commit(self):
        if not self._pending:
            return
        if time.time() - self._last_event_time < DEBOUNCE_SECONDS:
            return
        self._pending = False
        self._commit()

    def _commit(self):
        # 先检查是否有变更
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            return

        # 添加变更
        subprocess.run(["git", "add", "-A"], check=True)

        # 生成提交信息
        changed = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        files = ", ".join(line.split()[-1] for line in changed.splitlines())
        message = f"auto: sync changes ({files[:80]})"

        subprocess.run(["git", "commit", "-m", message], check=True)
        print(f"[{time.strftime('%H:%M:%S')}] Auto committed: {message}")

        # 如果配置了远程仓库，自动推送
        try:
            subprocess.run(["git", "push"], check=True, capture_output=True)
            print(f"[{time.strftime('%H:%M:%S')}] Auto pushed to remote")
        except subprocess.CalledProcessError as e:
            print(f"[{time.strftime('%H:%M:%S')}] Auto push failed: {e.stderr.decode()}")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    # 确保是 git 仓库
    if not (repo_root / ".git").exists():
        print("Error: not a git repository")
        return

    handler = AutoCommitHandler()
    observer = Observer()

    for relative_path in WATCH_PATHS:
        target = repo_root / relative_path
        if target.exists():
            observer.schedule(handler, str(target), recursive=True)
            print(f"Watching: {relative_path}")

    observer.start()
    print("Auto-commit watcher started. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            handler.check_commit()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
