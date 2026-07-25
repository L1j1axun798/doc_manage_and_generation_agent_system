from django.core.management.base import BaseCommand

from apps.document_generation.recovery import recover_generation_tasks


class Command(BaseCommand):
    help = "恢复遗留的四措两案生成任务并重新入队"

    def handle(self, *args, **options):
        result = recover_generation_tasks()
        self.stdout.write(
            self.style.SUCCESS(
                "recovered={recovered} queued={queued} queue_failures={queue_failures}".format(
                    **result
                )
            )
        )
