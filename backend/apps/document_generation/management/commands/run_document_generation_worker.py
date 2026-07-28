import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.document_generation.queues import QUEUE_NAME
from apps.document_generation.recovery import recover_generation_tasks


def worker_class_for_platform(platform: str = sys.platform) -> str:
    if platform == "win32":
        return "rq.worker.SimpleWorker"
    return "rq.worker.Worker"


class Command(BaseCommand):
    help = "先恢复遗留任务，再启动唯一的四措两案RQ Worker"

    def add_arguments(self, parser):
        parser.add_argument(
            "--burst",
            action="store_true",
            help="处理完当前队列后退出，用于部署前连通性验证",
        )

    def handle(self, *args, **options):
        result = recover_generation_tasks()
        worker_class = worker_class_for_platform()
        self.stdout.write(
            "recovered={recovered} queued={queued} queue_failures={queue_failures}".format(**result)
        )
        self.stdout.write(f"worker_class={worker_class} scheduler=enabled")
        call_command(
            "rqworker",
            QUEUE_NAME,
            burst=options["burst"],
            with_scheduler=True,
            worker_class=worker_class,
        )
