from celery import shared_task

from applications.complaint_system.api.services import check_slas_and_escalate


@shared_task(name='applications.complaint_system.tasks.run_complaint_sla_checks')
def run_complaint_sla_checks():
    check_slas_and_escalate()
    return 'ok'
