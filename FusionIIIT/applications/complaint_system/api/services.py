from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import models
from datetime import timedelta
from django.utils import timezone
from applications.complaint_system.models import (
    Caretaker,
    ComplaintActivityLog,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintStatus,
    StudentComplain,
    Supervisor,
)
from applications.globals.services import get_extra_info_by_user
from notification.views import complaint_system_notif
from . import selectors
from .serializers import (
    CaretakerSerializer,
    ComplaintActivityLogSerializer,
    ExtraInfoSerializer,
    StudentComplainSerializer,
    SupervisorSerializer,
    UserSerializer,
    WorkerSerializer,
)


ATTACHMENT_ALLOWED_TYPES = {'.jpg', '.jpeg', '.png', '.pdf', '.docx'}
ATTACHMENT_MAX_MB = 5
REOPEN_WINDOW_DAYS = 30


def calculate_sla_deadline(priority):
    now = timezone.now()
    if priority == ComplaintPriority.URGENT:
        return now + timedelta(hours=24)
    if priority == ComplaintPriority.LOW:
        return now + timedelta(days=7)
    return now + timedelta(days=3)


def _log_activity(complaint, actor, action, old_status=None, new_status=None, details=''):
    ComplaintActivityLog.objects.create(
        complaint=complaint,
        actor=actor,
        action=action,
        previous_status=old_status,
        new_status=new_status,
        details=details,
    )


def _validate_attachment(file_obj):
    if not file_obj:
        return
    name = file_obj.name or ''
    ext = name[name.rfind('.'):].lower() if '.' in name else ''
    size_mb = file_obj.size / (1024 * 1024)
    if ext not in ATTACHMENT_ALLOWED_TYPES:
        raise ValidationError('Invalid attachment type.')
    if size_mb > ATTACHMENT_MAX_MB:
        raise ValidationError('Attachment exceeds size limit.')


def can_access_complaint(user, complaint):
    if user.is_superuser:
        return True
    if complaint.complainer.user_id == user.id:
        return True
    extra_info = get_extra_info_by_user(user)
    if Caretaker.objects.filter(staff_id=extra_info, area=complaint.location).exists():
        return True
    if Supervisor.objects.filter(sup_id=extra_info, area=complaint.location).exists():
        return True
    return False


def build_complaint_payload(complaint):
    complaint_detail_serialized = StudentComplainSerializer(instance=complaint).data
    if complaint.worker_id is None:
        worker_detail_serialized = {}
    else:
        worker_detail_serialized = WorkerSerializer(instance=complaint.worker_id).data
    complainer_serialized = UserSerializer(instance=complaint.complainer.user).data
    complainer_extra_info_serialized = ExtraInfoSerializer(instance=complaint.complainer).data
    activity_logs = ComplaintActivityLogSerializer(
        complaint.activity_logs.order_by('-timestamp'),
        many=True,
    ).data
    return {
        'complainer': complainer_serialized,
        'complainer_extra_info': complainer_extra_info_serialized,
        'complaint_details': complaint_detail_serialized,
        'worker_details': worker_detail_serialized,
        'activity_logs': activity_logs,
    }


def _auto_assign(complaint):
    caretaker = Caretaker.objects.filter(area=complaint.location).first()
    supervisor = Supervisor.objects.filter(area=complaint.location).first()
    complaint.assigned_caretaker = caretaker
    complaint.assigned_supervisor = supervisor
    return caretaker, supervisor


def _is_admin(user):
    return bool(user and user.is_superuser)


def _is_caretaker(extra_info):
    return Caretaker.objects.filter(staff_id=extra_info).exists()


def _is_supervisor(extra_info):
    return Supervisor.objects.filter(sup_id=extra_info).exists()


def _notify_admins(sender_user, complaint, notification_type, message):
    user_model = get_user_model()
    admin_users = user_model.objects.filter(is_superuser=True)
    for admin_user in admin_users:
        complaint_system_notif(
            sender_user,
            admin_user,
            notification_type,
            complaint.id,
            0,
            message,
        )


def _validate_transition(complaint, new_status, actor):
    current = complaint.status
    allowed = {
        ComplaintStatus.PENDING: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.ESCALATED},
        ComplaintStatus.IN_PROGRESS: {ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED, ComplaintStatus.ESCALATED},
        ComplaintStatus.ESCALATED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED},
        ComplaintStatus.RESOLVED: {ComplaintStatus.CLOSED, ComplaintStatus.REOPENED},
        ComplaintStatus.CLOSED: {ComplaintStatus.REOPENED},
        ComplaintStatus.REOPENED: {ComplaintStatus.IN_PROGRESS, ComplaintStatus.ESCALATED},
        ComplaintStatus.DECLINED: {ComplaintStatus.REOPENED},
    }
    if new_status not in allowed.get(current, set()):
        raise ValidationError('Invalid status transition.')

    if actor is None:
        return
    if _is_admin(actor.user):
        return
    if current in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.DECLINED] and new_status == ComplaintStatus.REOPENED:
        if complaint.complainer_id != actor.id and not _is_supervisor(actor):
            raise ValidationError('Only complainant or supervisor can reopen.')
    if new_status in [ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED, ComplaintStatus.ESCALATED]:
        if not (_is_caretaker(actor) or _is_supervisor(actor)):
            raise ValidationError('Only caretakers or supervisors can update progress.')


def get_complaint_detail(complaint_id):
    complaint = selectors.get_complaint(complaint_id)
    return build_complaint_payload(complaint)


def get_complains_for_user(extra_info):
    return selectors.list_complaints_for_user(extra_info)


def create_complaint(complainer, data):
    upload = data.get('upload_complaint')
    _validate_attachment(upload)
    payload = dict(data)
    payload['complainer'] = complainer.id
    serializer = StudentComplainSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    priority = serializer.validated_data.get('priority') or ComplaintPriority.STANDARD
    complaint = serializer.save(
        priority=priority,
        sla_deadline=calculate_sla_deadline(priority),
        status=ComplaintStatus.PENDING,
        complaint_finish=calculate_sla_deadline(priority).date(),
    )
    caretaker, supervisor = _auto_assign(complaint)
    if caretaker is None or supervisor is None:
        complaint.flag = 1
        complaint.remarks = 'Pending Assignment'
    complaint.save()
    _log_activity(complaint, complaint.complainer, 'COMPLAINT_SUBMITTED', new_status=ComplaintStatus.PENDING)
    complaint_system_notif(
        complaint.complainer.user,
        complaint.complainer.user,
        'complaint_submitted',
        complaint.id,
        0,
        'Your complaint has been submitted.',
    )
    return StudentComplainSerializer(instance=complaint).data


def update_complaint(complaint, data):
    old_status = complaint.status
    serializer = StudentComplainSerializer(complaint, data=data)
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    _log_activity(updated, updated.complainer, 'COMPLAINT_UPDATED', old_status, updated.status)
    return StudentComplainSerializer(instance=updated).data


def delete_complaint(complaint):
    complaint.delete()


def update_progress(complaint, actor, status_value, note='', resolved_file=None):
    old_status = complaint.status
    _validate_transition(complaint, status_value, actor)
    if status_value == ComplaintStatus.RESOLVED and not note:
        raise ValidationError('Resolution note required.')
    if resolved_file:
        _validate_attachment(resolved_file)
        complaint.upload_resolved = resolved_file
    complaint.status = status_value
    if status_value == ComplaintStatus.RESOLVED:
        complaint.resolved_at = timezone.now()
    complaint.save()
    _log_activity(complaint, actor, 'PROGRESS_UPDATE', old_status, status_value, details=note)
    if status_value == ComplaintStatus.RESOLVED:
        complaint_system_notif(
            actor.user,
            complaint.complainer.user,
            'complaint_resolved',
            complaint.id,
            0,
            'Your complaint has been marked resolved.',
        )
    else:
        complaint_system_notif(
            actor.user,
            complaint.complainer.user,
            'complaint_progress_updated',
            complaint.id,
            0,
            'Complaint progress has been updated.',
        )


def escalate_complaint(complaint, actor, justification, is_auto=False):
    if not is_auto and not justification:
        raise ValidationError('Justification required for escalation.')
    if actor is not None:
        _validate_transition(complaint, ComplaintStatus.ESCALATED, actor)
    old_status = complaint.status
    complaint.status = ComplaintStatus.ESCALATED
    complaint.assigned_supervisor = complaint.assigned_supervisor or Supervisor.objects.filter(area=complaint.location).first()
    complaint.save()
    action = 'AUTO_ESCALATION' if is_auto else 'MANUAL_ESCALATION'
    _log_activity(complaint, actor, action, old_status, ComplaintStatus.ESCALATED, details=justification)
    if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
        complaint_system_notif(
            actor.user if actor else complaint.complainer.user,
            complaint.assigned_supervisor.sup_id.user,
            'complaint_escalated',
            complaint.id,
            0,
            'A complaint has been escalated to you.',
        )
    else:
        _notify_admins(
            actor.user if actor else complaint.complainer.user,
            complaint,
            'complaint_escalated_admin_fallback',
            'Escalated complaint has no mapped supervisor and needs admin action.',
        )

    if is_auto:
        _notify_admins(
            actor.user if actor else complaint.complainer.user,
            complaint,
            'complaint_auto_escalated',
            'Complaint auto-escalated after SLA breach.',
        )


def close_complaint(complaint, actor, verified):
    if complaint.status != ComplaintStatus.RESOLVED:
        raise ValidationError('Only resolved complaints can be closed.')
    if not verified:
        raise ValidationError('Verification required to close complaint.')
    if actor is not None and not (_is_supervisor(actor) or complaint.complainer_id == actor.id):
        raise ValidationError('Only complainant or supervisor can close complaint.')
    old_status = complaint.status
    complaint.status = ComplaintStatus.CLOSED
    complaint.closed_at = timezone.now()
    complaint.save()
    _log_activity(complaint, actor, 'COMPLAINT_CLOSED', old_status, ComplaintStatus.CLOSED)
    complaint_system_notif(
        actor.user if actor else complaint.complainer.user,
        complaint.complainer.user,
        'complaint_closed',
        complaint.id,
        0,
        'Your complaint has been closed. Please provide feedback.',
    )


def reopen_complaint(complaint, actor, justification):
    if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]:
        raise ValidationError('Only resolved/closed complaints can be reopened.')
    if not justification:
        raise ValidationError('Justification required to reopen complaint.')
    if complaint.closed_at and (timezone.now() - complaint.closed_at).days > REOPEN_WINDOW_DAYS:
        raise ValidationError('Reopen window has expired.')
    if actor is not None and not (_is_supervisor(actor) or complaint.complainer_id == actor.id):
        raise ValidationError('Only complainant or supervisor can reopen complaint.')
    old_status = complaint.status
    complaint.status = ComplaintStatus.REOPENED
    complaint.resolved_at = None
    complaint.closed_at = None
    complaint.save()
    _log_activity(complaint, actor, 'COMPLAINT_REOPENED', old_status, ComplaintStatus.REOPENED, details=justification)
    if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
        complaint_system_notif(
            actor.user,
            complaint.assigned_supervisor.sup_id.user,
            'complaint_reopened',
            complaint.id,
            0,
            'A complaint has been reopened.',
        )


def submit_feedback(complaint, rating, comments=''):
    if complaint.status != ComplaintStatus.CLOSED:
        raise ValidationError('Feedback can only be submitted for closed complaints.')
    feedback, _ = ComplaintFeedback.objects.update_or_create(
        complaint=complaint,
        defaults={'rating': rating, 'comments': comments},
    )
    _log_activity(complaint, complaint.complainer, 'FEEDBACK_SUBMITTED', complaint.status, complaint.status)
    if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
        complaint_system_notif(
            complaint.complainer.user,
            complaint.assigned_supervisor.sup_id.user,
            'feedback_submitted',
            complaint.id,
            0,
            'New feedback submitted for a complaint.',
        )
    return feedback


def check_slas_and_escalate():
    now = timezone.now()
    breached = StudentComplain.objects.filter(
        sla_deadline__lt=now,
        status__in=[ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED],
    )
    for complaint in breached:
        escalate_complaint(complaint, actor=None, justification='Auto escalation due to SLA breach.', is_auto=True)

    reminder_window = now + timedelta(hours=2)
    approaching = StudentComplain.objects.filter(
        sla_deadline__gte=now,
        sla_deadline__lte=reminder_window,
        status__in=[ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED],
    )
    for complaint in approaching:
        _log_activity(complaint, None, 'SLA_REMINDER', complaint.status, complaint.status)
        if complaint.assigned_caretaker and complaint.assigned_caretaker.staff_id:
            complaint_system_notif(
                complaint.complainer.user,
                complaint.assigned_caretaker.staff_id.user,
                'sla_reminder',
                complaint.id,
                0,
                'SLA deadline approaching for an assigned complaint.',
            )
        if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
            complaint_system_notif(
                complaint.complainer.user,
                complaint.assigned_supervisor.sup_id.user,
                'sla_reminder',
                complaint.id,
                0,
                'SLA deadline approaching for an assigned complaint.',
            )


def generate_report(filters):
    qs = StudentComplain.objects.all()
    if filters.get('location'):
        qs = qs.filter(location=filters['location'])
    if filters.get('complaint_type'):
        qs = qs.filter(complaint_type=filters['complaint_type'])
    if filters.get('status') is not None:
        qs = qs.filter(status=filters['status'])
    if filters.get('priority'):
        qs = qs.filter(priority=filters['priority'])
    if filters.get('start_date'):
        qs = qs.filter(complaint_date__date__gte=filters['start_date'])
    if filters.get('end_date'):
        qs = qs.filter(complaint_date__date__lte=filters['end_date'])
    return qs.order_by('-complaint_date')


def build_report_summary(queryset):
    status_counts = {str(k): 0 for k, _ in ComplaintStatus.choices}
    for item in queryset.values('status').order_by().annotate(total=models.Count('id')):
        status_counts[str(item['status'])] = item['total']

    return {
        'total': queryset.count(),
        'status_counts': status_counts,
        'by_priority': {
            'URGENT': queryset.filter(priority=ComplaintPriority.URGENT).count(),
            'STANDARD': queryset.filter(priority=ComplaintPriority.STANDARD).count(),
            'LOW': queryset.filter(priority=ComplaintPriority.LOW).count(),
        },
    }


def admin_assign(complaint, caretaker=None, supervisor=None, actor=None):
    old_status = complaint.status
    if caretaker is not None:
        complaint.assigned_caretaker = caretaker
    if supervisor is not None:
        complaint.assigned_supervisor = supervisor
    complaint.status = ComplaintStatus.IN_PROGRESS
    complaint.remarks = 'Admin Assigned'
    complaint.flag = 0
    complaint.save()
    _log_activity(complaint, actor, 'ADMIN_ASSIGN', old_status, complaint.status)


def list_workers():
    return selectors.list_workers()


def create_worker(data):
    serializer = WorkerSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def update_worker(worker, data):
    serializer = WorkerSerializer(worker, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def delete_worker(worker):
    worker.delete()


def list_caretakers():
    return selectors.list_caretakers()


def create_caretaker(data):
    serializer = CaretakerSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def update_caretaker(caretaker, data):
    serializer = CaretakerSerializer(caretaker, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def delete_caretaker(caretaker):
    caretaker.delete()


def list_supervisors():
    return selectors.list_supervisors()


def create_supervisor(data):
    serializer = SupervisorSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def update_supervisor(supervisor, data):
    serializer = SupervisorSerializer(supervisor, data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.data


def delete_supervisor(supervisor):
    supervisor.delete()
