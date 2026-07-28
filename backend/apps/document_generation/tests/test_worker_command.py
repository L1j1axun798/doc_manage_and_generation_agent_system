from unittest.mock import Mock

from apps.document_generation.management.commands import (
    run_document_generation_worker as worker_command,
)


def test_windows_uses_simple_worker_and_other_platforms_use_default_worker():
    assert worker_command.worker_class_for_platform("win32") == "rq.worker.SimpleWorker"
    assert worker_command.worker_class_for_platform("linux") == "rq.worker.Worker"


def test_worker_command_enables_scheduler(monkeypatch):
    call_command = Mock()
    monkeypatch.setattr(worker_command, "call_command", call_command)
    monkeypatch.setattr(
        worker_command,
        "recover_generation_tasks",
        lambda: {"recovered": 0, "queued": 1, "queue_failures": 0},
    )

    worker_command.Command().handle(burst=True)

    call_command.assert_called_once_with(
        "rqworker",
        "document-generation",
        burst=True,
        with_scheduler=True,
        worker_class=worker_command.worker_class_for_platform(),
    )
