from celery import shared_task

from applications.complaint_system.api.services import check_slas_and_escalate


@shared_task(
    name='applications.complaint_system.tasks.run_complaint_sla_checks',
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5-minute delay between retries
)
def run_complaint_sla_checks(self):
    """WF-201/301 fix: Celery task with retry policy for SLA checks."""
    try:
        check_slas_and_escalate()
        return 'ok'
    except Exception as exc:
        raise self.retry(exc=exc)
