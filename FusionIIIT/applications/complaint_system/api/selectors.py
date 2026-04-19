from django.shortcuts import get_object_or_404
from applications.complaint_system.models import Caretaker, ComplaintStatus, StudentComplain, Supervisor, Workers


def get_complaint(complaint_id):
    return get_object_or_404(StudentComplain, id=complaint_id)


def list_complaints_for_user(extra_info):
    if extra_info.user_type == 'student':
        return StudentComplain.objects.filter(complainer=extra_info)
    if extra_info.user_type == 'staff':
        caretaker = get_object_or_404(Caretaker, staff_id=extra_info)
        return StudentComplain.objects.filter(location=caretaker.area)
    if extra_info.user_type == 'faculty':
        supervisor = get_object_or_404(Supervisor, sup_id=extra_info)
        return StudentComplain.objects.filter(location=supervisor.area)
    return StudentComplain.objects.none()


def list_assigned_complaints(extra_info):
    caretaker = Caretaker.objects.filter(staff_id=extra_info).first()
    if caretaker:
        return StudentComplain.objects.filter(assigned_caretaker=caretaker)
    supervisor = Supervisor.objects.filter(sup_id=extra_info).first()
    if supervisor:
        return StudentComplain.objects.filter(assigned_supervisor=supervisor)
    return StudentComplain.objects.none()


def list_unresolved():
    return StudentComplain.objects.filter(status__in=[
        ComplaintStatus.PENDING,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.ESCALATED,
        ComplaintStatus.REOPENED,
    ])


def get_worker(worker_id):
    return get_object_or_404(Workers, id=worker_id)


def list_workers():
    return Workers.objects.all()


def get_caretaker(caretaker_id):
    return get_object_or_404(Caretaker, id=caretaker_id)


def list_caretakers():
    return Caretaker.objects.all()


def get_supervisor(supervisor_id):
    return get_object_or_404(Supervisor, id=supervisor_id)


def list_supervisors():
    return Supervisor.objects.all()
