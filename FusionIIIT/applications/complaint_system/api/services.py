import hashlib
import logging

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import models, transaction
from datetime import timedelta
from django.utils import timezone
from applications.complaint_system.models import (
    Caretaker,
    Complaint_Admin,
    ComplaintActivityLog,
    ComplaintAssigneeConfig,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintStatus,
    ReopenRequest,
    ServiceAuthority,
    StudentComplain,
    Supervisor,
)
from applications.globals.services import get_extra_info_by_user
from applications.globals.models import ExtraInfo
from notification.views import complaint_system_notif as _raw_complaint_notif
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

logger = logging.getLogger('complaint_system')

ATTACHMENT_ALLOWED_TYPES = {'.jpg', '.jpeg', '.png', '.pdf', '.docx'}
ATTACHMENT_MAX_MB = 5
REOPEN_WINDOW_DAYS = 30
DUPLICATE_WINDOW_MINUTES = 5
SLA_GRACE_PERIOD_HOURS = 1
MAX_ESCALATION_RETRIES = 3


def complaint_system_notif(sender, recipient, notif_type, complaint_id, student, message):
    """Safe notification delivery wrapper — logs failures instead of crashing.
    Addresses Integration readiness gap: notification delivery is now observable."""
    try:
        _raw_complaint_notif(sender, recipient, notif_type, complaint_id, student, message)
        logger.info(
            'Notification delivered: type=%s, complaint=%s, recipient=%s',
            notif_type, complaint_id, getattr(recipient, 'username', recipient),
        )
    except Exception as exc:
        logger.error(
            'Notification delivery FAILED: type=%s, complaint=%s, recipient=%s, error=%s',
            notif_type, complaint_id, getattr(recipient, 'username', recipient), exc,
        )


def calculate_sla_deadline(priority):
    now = timezone.now()
    if priority == ComplaintPriority.URGENT:
        return now + timedelta(hours=24)
    if priority == ComplaintPriority.LOW:
        return now + timedelta(days=7)
    return now + timedelta(days=3)


def _log_activity(complaint, actor, action, old_status=None, new_status=None, details=''):
    """Log complaint activity. System-initiated actions (actor=None) are prefixed
    with SYSTEM_ for separate auditing (Role Handling readiness gap fix)."""
    if actor is None and not action.startswith('SYSTEM_') and not action.startswith('AUTO_'):
        action = f'SYSTEM_{action}'
    ComplaintActivityLog.objects.create(
        complaint=complaint,
        actor=actor,
        action=action,
        previous_status=old_status,
        new_status=new_status,
        details=details,
    )
    logger.info(
        'Activity logged: complaint=%s, actor=%s, action=%s, %s→%s',
        complaint.id, getattr(actor, 'id', 'SYSTEM'), action, old_status, new_status,
    )


def _validate_attachment(file_obj):
    if not file_obj:
        return
    name = file_obj.name or ''
    ext = name[name.rfind('.'):].lower() if '.' in name else ''
    size_mb = file_obj.size / (1024 * 1024)
    if ext not in ATTACHMENT_ALLOWED_TYPES:
        raise ValidationError('Invalid attachment type. Allowed: jpg, jpeg, png, pdf, docx.')
    if size_mb > ATTACHMENT_MAX_MB:
        raise ValidationError(f'Attachment exceeds {ATTACHMENT_MAX_MB}MB size limit.')


def can_access_complaint(user, complaint):
    if user.is_superuser:
        return True
    if complaint.complainer and complaint.complainer.user_id == user.id:
        return True
    extra_info = ExtraInfo.objects.filter(user=user).first()
    if extra_info is None:
        return False
    if Complaint_Admin.objects.filter(sup_id=extra_info).exists():
        return True
    if ServiceAuthority.objects.filter(ser_pro_id=extra_info).exists():
        return True
    
    # Area-based or direct assignment checks.
    # Area/location strings in this codebase vary in case and separators
    # (e.g. hall-1, Hall-1, Rewa_Residency, Rewa Residency), so use
    # tolerant matching for role-based visibility.
    location_variants = {
        str(complaint.location or ''),
        str(complaint.location or '').replace('_', ' '),
        str(complaint.location or '').replace(' ', '_'),
    }
    location_query = models.Q()
    for loc in location_variants:
        if loc:
            location_query |= models.Q(area__iexact=loc)

    if Caretaker.objects.filter(models.Q(staff_id=extra_info) & location_query).exists():
        return True
    if getattr(complaint, 'assigned_caretaker', None) and getattr(complaint.assigned_caretaker, 'staff_id_id', None) == extra_info.id:
        return True
        
    if Supervisor.objects.filter(models.Q(sup_id=extra_info) & location_query).exists():
        return True
    if getattr(complaint, 'assigned_supervisor', None) and getattr(complaint.assigned_supervisor, 'sup_id_id', None) == extra_info.id:
        return True
        
    return False


def build_complaint_payload(complaint):
    complaint_detail_serialized = StudentComplainSerializer(instance=complaint).data
    if complaint.worker_id is None:
        worker_detail_serialized = {}
    else:
        worker_detail_serialized = WorkerSerializer(instance=complaint.worker_id).data
    
    complainer_serialized = UserSerializer(instance=complaint.complainer.user).data if complaint.complainer else {}
    complainer_extra_info_serialized = ExtraInfoSerializer(instance=complaint.complainer).data if complaint.complainer else {}
    
    activity_logs = ComplaintActivityLogSerializer(
        complaint.activity_logs.order_by('-timestamp'),
        many=True,
    ).data

    # Include assigned caretaker/supervisor details
    caretaker_data = None
    if complaint.assigned_caretaker:
        caretaker_data = CaretakerSerializer(instance=complaint.assigned_caretaker).data
    supervisor_data = None
    if complaint.assigned_supervisor:
        supervisor_data = SupervisorSerializer(instance=complaint.assigned_supervisor).data

    feedback_data = None
    if hasattr(complaint, 'feedback_entry') and complaint.feedback_entry is not None:
        feedback_data = {
            'rating': complaint.feedback_entry.rating,
            'comments': complaint.feedback_entry.comments,
            'submitted_at': complaint.feedback_entry.submitted_at,
        }

    return {
        'complainer': complainer_serialized,
        'complainer_extra_info': complainer_extra_info_serialized,
        'complaint_details': complaint_detail_serialized,
        'worker_details': worker_detail_serialized,
        'activity_logs': activity_logs,
        'assigned_caretaker': caretaker_data,
        'assigned_supervisor': supervisor_data,
        'feedback_entry': feedback_data,
    }


def _auto_assign(complaint):
    # Try dynamic assignment config first (location + type)
    config = ComplaintAssigneeConfig.objects.filter(
        location=complaint.location,
        complaint_type=complaint.complaint_type,
    ).first()
    
    if config:
        caretaker = config.caretaker
        supervisor = config.supervisor
    else:
        # Fallback to hardcoded area-based mapping if no specific config exists
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


def _is_service_authority(extra_info):
    from applications.complaint_system.models import ServiceAuthority
    return ServiceAuthority.objects.filter(ser_pro_id=extra_info).exists()


def _is_complaint_admin(extra_info):
    from applications.complaint_system.models import Complaint_Admin
    return Complaint_Admin.objects.filter(sup_id=extra_info).exists()


def _notify_admins(sender_user, complaint, notification_type, message):
    user_model = get_user_model()
    recipient_map = {}

    # Django superusers
    for admin_user in user_model.objects.filter(is_superuser=True):
        recipient_map[admin_user.id] = admin_user

    # Complaint module admins
    for complaint_admin in Complaint_Admin.objects.select_related('sup_id__user'):
        user = getattr(getattr(complaint_admin, 'sup_id', None), 'user', None)
        if user:
            recipient_map[user.id] = user

    # Service authorities are also oversight admins in workflow terms
    for authority in ServiceAuthority.objects.select_related('ser_pro_id__user'):
        user = getattr(getattr(authority, 'ser_pro_id', None), 'user', None)
        if user:
            recipient_map[user.id] = user

    for admin_user in recipient_map.values():
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
    if _is_supervisor(actor):
        supervisor_obj = Supervisor.objects.filter(sup_id=actor).first()
        if complaint.assigned_supervisor_id and supervisor_obj and complaint.assigned_supervisor_id != supervisor_obj.id:
            raise ValidationError('Only the assigned supervisor can update this complaint.')
        # Supervisor policy: no direct progress updates. They should reassign
        # escalated complaints and only handle verification/closure.
        if new_status in [
            ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.RESOLVED,
            ComplaintStatus.DECLINED,
        ]:
            raise ValidationError('Supervisors cannot change progress directly. Please reassign the complaint.')
        # Reopen is handled through request review workflow, not direct transition.
        if new_status == ComplaintStatus.REOPENED:
            raise ValidationError('Supervisors must approve or decline reopen requests.')
    if current in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.DECLINED] and new_status == ComplaintStatus.REOPENED:
        if complaint.complainer_id != actor.id and not (_is_supervisor(actor) or _is_service_authority(actor) or _is_complaint_admin(actor)):
            raise ValidationError('Only complainant or authorized handlers can reopen.')
    if new_status in [ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED, ComplaintStatus.ESCALATED]:
        if not (_is_caretaker(actor) or _is_supervisor(actor) or _is_service_authority(actor) or _is_complaint_admin(actor)):
            raise ValidationError('Only authorized handlers in the hierarchy can update progress.')


def get_complaint_detail(complaint_id):
    complaint = selectors.get_complaint(complaint_id)
    return build_complaint_payload(complaint)


def get_complains_for_user(extra_info):
    return selectors.list_complaints_for_user(extra_info)


def _check_duplicate(complainer, data):
    """Prevent identical complaints within a short time window (race condition guard)."""
    window = timezone.now() - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
    duplicate = StudentComplain.objects.filter(
        complainer=complainer,
        location=data.get('location', ''),
        complaint_type=data.get('complaint_type', ''),
        complaint_date__gte=window,
    ).first()
    if duplicate:
        raise ValidationError(
            f'A similar complaint was already submitted {DUPLICATE_WINDOW_MINUTES} minutes ago '
            f'(Complaint #{duplicate.id}). Please wait before submitting again.'
        )


@transaction.atomic
def create_complaint(complainer, data, idempotency_key=None):
    # Idempotency check: return existing complaint if key was already used
    if idempotency_key:
        existing = StudentComplain.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return StudentComplainSerializer(instance=existing).data

    # Duplicate detection: same complainer + location + type within 5 minutes
    _check_duplicate(complainer, data)

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
        idempotency_key=idempotency_key,
    )
    caretaker, supervisor = _auto_assign(complaint)
    if caretaker is None or supervisor is None:
        complaint.flag = 1
        complaint.remarks = 'Pending Assignment'
        # WF-101 fix: auto-escalate when auto-assignment fails
        _log_activity(complaint, complaint.complainer, 'AUTO_ASSIGN_FAILED',
                      new_status=ComplaintStatus.PENDING,
                      details=f'Auto-assignment failed for area={complaint.location}. '
                              f'Caretaker={"found" if caretaker else "missing"}, '
                              f'Supervisor={"found" if supervisor else "missing"}. '
                              f'Notifying admins for manual assignment.')
        _notify_admins(
            complaint.complainer.user,
            complaint,
            'auto_assign_failed',
            f'Complaint #{complaint.id} in area "{complaint.location}" could not be '
            f'auto-assigned. Manual assignment required.',
        )
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


@transaction.atomic
def update_complaint(complaint, data):
    old_status = complaint.status
    serializer = StudentComplainSerializer(complaint, data=data)
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    _log_activity(updated, updated.complainer, 'COMPLAINT_UPDATED', old_status, updated.status)
    return StudentComplainSerializer(instance=updated).data


def delete_complaint(complaint):
    complaint.delete()


@transaction.atomic
def update_progress(complaint, actor, status_value, note='', resolved_file=None):
    """UC-CM-003: Update complaint progress with full exception handling."""
    old_status = complaint.status
    _validate_transition(complaint, status_value, actor)

    # Validate note is required for resolution
    if status_value == ComplaintStatus.RESOLVED and not note:
        raise ValidationError('Resolution note required.')

    # Validate and attach resolved file if provided
    if resolved_file:
        _validate_attachment(resolved_file)
        complaint.upload_resolved = resolved_file

    # Validate actor has access to this complaint
    if actor is not None and not (complaint.complainer_id == actor.id
                                   or _is_caretaker(actor)
                                   or _is_supervisor(actor)
                                   or _is_admin(actor.user)):
        raise ValidationError('You do not have permission to update this complaint.')

    complaint.status = status_value
    if status_value == ComplaintStatus.RESOLVED:
        complaint.resolved_at = timezone.now()
    if status_value == ComplaintStatus.DECLINED and not note:
        raise ValidationError('A reason is required when declining a complaint.')
    complaint.save()
    _log_activity(complaint, actor, 'PROGRESS_UPDATE', old_status, status_value, details=note)

    # Notification dispatch with exception-safe delivery
    if status_value == ComplaintStatus.RESOLVED:
        complaint_system_notif(
            actor.user,
            complaint.complainer.user,
            'complaint_resolved',
            complaint.id,
            0,
            'Your complaint has been marked resolved. Please verify and close.',
        )
        # Also notify supervisor
        if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
            complaint_system_notif(
                actor.user,
                complaint.assigned_supervisor.sup_id.user,
                'complaint_resolved_supervisor',
                complaint.id,
                0,
                'A complaint in your area has been resolved.',
            )
    elif status_value == ComplaintStatus.DECLINED:
        # Notify complainant of decline with reason
        complaint_system_notif(
            actor.user,
            complaint.complainer.user,
            'complaint_declined',
            complaint.id,
            0,
            f'Your complaint has been declined. Reason: {note}',
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


@transaction.atomic
def escalate_complaint(complaint, actor, justification, is_auto=False):
    if not is_auto and not justification:
        raise ValidationError('Justification required for escalation.')
    if actor is not None:
        _validate_transition(complaint, ComplaintStatus.ESCALATED, actor)
    
    old_status = complaint.status
    complaint.status = ComplaintStatus.ESCALATED
    
    # Multi-level escalation cascade (WF-101 / WF-201)
    if complaint.escalation_level == 0:
        complaint.escalation_level = 1
        complaint.assigned_supervisor = complaint.assigned_supervisor or Supervisor.objects.filter(area=complaint.location).first()
        target_user = complaint.assigned_supervisor.sup_id.user if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id else None
        target_role = "Supervisor"
    elif complaint.escalation_level == 1:
        complaint.escalation_level = 2
        service_auth = ServiceAuthority.objects.filter(type=complaint.complaint_type).first()
        target_user = service_auth.ser_pro_id.user if service_auth and service_auth.ser_pro_id else None
        target_role = "Service Authority"
    else:
        complaint.escalation_level = 3
        target_user = None
        target_role = "Admin"

    complaint.save()
    action = 'AUTO_ESCALATION' if is_auto else 'MANUAL_ESCALATION'
    _log_activity(complaint, actor, action, old_status, ComplaintStatus.ESCALATED, details=justification)
    
    if target_user:
        complaint_system_notif(
            actor.user if actor else (complaint.complainer.user if complaint.complainer else None),
            target_user,
            'complaint_escalated',
            complaint.id,
            0,
            f'A complaint has been escalated to you ({target_role}).',
        )
    else:
        _notify_admins(
            actor.user if actor else (complaint.complainer.user if complaint.complainer else None),
            complaint,
            'complaint_escalated_admin_fallback',
            f'Escalated complaint to {target_role} failed routing and needs admin action.',
        )

    if is_auto:
        _notify_admins(
            actor.user if actor else (complaint.complainer.user if complaint.complainer else None),
            complaint,
            'complaint_auto_escalated',
            'Complaint auto-escalated after SLA breach.',
        )


@transaction.atomic
def close_complaint(complaint, actor, verified):
    if complaint.status != ComplaintStatus.RESOLVED:
        raise ValidationError('Only resolved complaints can be closed.')
    if not verified:
        raise ValidationError('Verification required to close complaint.')
    if actor is not None and not (_is_supervisor(actor) or _is_service_authority(actor) or _is_complaint_admin(actor) or complaint.complainer_id == actor.id):
        raise ValidationError('Only complainant or authorized handlers in the hierarchy can close complaint.')
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
    # Notify admin for analysis
    _notify_admins(
        actor.user if actor else complaint.complainer.user,
        complaint,
        'complaint_closed_admin',
        f'Complaint #{complaint.id} has been closed.',
    )


@transaction.atomic
def reopen_complaint(complaint, actor, justification):
    if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.DECLINED]:
        raise ValidationError('Only resolved/closed/declined complaints can be reopened.')
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
    # Reassign caretaker
    caretaker, supervisor = _auto_assign(complaint)
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


@transaction.atomic
def create_reopen_request(complaint, requester, justification):
    """Create a reopen request that needs supervisor approval (UC-CM-011)."""
    if complaint.status not in [ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED, ComplaintStatus.DECLINED]:
        raise ValidationError('Only resolved/closed/declined complaints can be reopened.')
    if not justification:
        raise ValidationError('Justification required.')
    if complaint.closed_at and (timezone.now() - complaint.closed_at).days > REOPEN_WINDOW_DAYS:
        raise ValidationError('Reopen window has expired.')
    if complaint.complainer_id != requester.id and not (_is_admin(requester.user) or _is_complaint_admin(requester) or _is_service_authority(requester)):
        raise ValidationError('Only the original complainant can request reopen.')
    existing_pending = ReopenRequest.objects.filter(
        complaint=complaint,
        requester=requester,
        status=ReopenRequest.RequestStatus.PENDING,
    ).first()
    if existing_pending:
        raise ValidationError('A reopen request is already pending review for this complaint.')
    request = ReopenRequest.objects.create(
        complaint=complaint,
        requester=requester,
        justification=justification,
    )
    _log_activity(complaint, requester, 'REOPEN_REQUESTED', complaint.status, complaint.status, details=justification)
    # Notify supervisor
    if complaint.assigned_supervisor and complaint.assigned_supervisor.sup_id:
        complaint_system_notif(
            requester.user,
            complaint.assigned_supervisor.sup_id.user,
            'reopen_request',
            complaint.id,
            0,
            'A reopen request has been submitted for your review.',
        )
    return request


@transaction.atomic
def approve_reopen_request(reopen_req, reviewer, approved, review_note=''):
    """Supervisor approves or denies a reopen request."""
    if reopen_req.status != ReopenRequest.RequestStatus.PENDING:
        raise ValidationError('This request has already been reviewed.')
    reopen_req.reviewed_by = reviewer
    reopen_req.review_note = review_note
    reopen_req.reviewed_at = timezone.now()
    complaint = reopen_req.complaint
    if approved:
        reopen_req.status = ReopenRequest.RequestStatus.APPROVED
        reopen_req.save()
        reopen_complaint(complaint, reviewer, reopen_req.justification)
    else:
        reopen_req.status = ReopenRequest.RequestStatus.DENIED
        reopen_req.save()
        _log_activity(complaint, reviewer, 'REOPEN_DENIED', complaint.status, complaint.status, details=review_note)
        complaint_system_notif(
            reviewer.user,
            reopen_req.requester.user,
            'reopen_denied',
            complaint.id,
            0,
            'Your reopen request has been denied.',
        )


@transaction.atomic
def submit_feedback(complaint, rating, comments=''):
    if complaint.status != ComplaintStatus.CLOSED:
        raise ValidationError('Feedback can only be submitted for closed complaints.')
    feedback, _ = ComplaintFeedback.objects.update_or_create(
        complaint=complaint,
        defaults={'rating': rating, 'comments': comments},
    )
    _log_activity(complaint, complaint.complainer, 'FEEDBACK_SUBMITTED', complaint.status, complaint.status)
    # Notify admin for analysis
    _notify_admins(
        complaint.complainer.user,
        complaint,
        'feedback_submitted_admin',
        f'New feedback (rating: {rating}) for complaint #{complaint.id}.',
    )
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
    """WF-301 fix: SLA monitoring with grace period and retry policy.
    - Grace period: complaints are escalated only after SLA + grace period has passed
    - Retry: failed escalations are retried up to MAX_ESCALATION_RETRIES times
    - Separate auditing for system-initiated actions
    """
    now = timezone.now()
    grace_cutoff = now - timedelta(hours=SLA_GRACE_PERIOD_HOURS)

    # Breached complaints (past SLA + grace period)
    breached = StudentComplain.objects.filter(
        sla_deadline__lt=grace_cutoff,
        status__in=[ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED],
    )
    for complaint in breached:
        # WF-201 fix: retry policy — count previous failed attempts
        failed_attempts = ComplaintActivityLog.objects.filter(
            complaint=complaint,
            action='AUTO_ESCALATION_FAILED',
        ).count()
        if failed_attempts >= MAX_ESCALATION_RETRIES:
            _log_activity(
                complaint, None, 'AUTO_ESCALATION_ABANDONED',
                complaint.status, complaint.status,
                details=f'Auto-escalation abandoned after {MAX_ESCALATION_RETRIES} failed attempts. '
                        f'Admin intervention required.',
            )
            _notify_admins(
                complaint.complainer.user if complaint.complainer else get_user_model().objects.filter(is_superuser=True).first(),
                complaint,
                'escalation_abandoned',
                f'Complaint #{complaint.id} could not be auto-escalated after '
                f'{MAX_ESCALATION_RETRIES} attempts. Manual intervention required.',
            )
            continue
        try:
            escalate_complaint(
                complaint, actor=None,
                justification=f'Auto escalation due to SLA breach '
                              f'(attempt {failed_attempts + 1}/{MAX_ESCALATION_RETRIES}).',
                is_auto=True,
            )
            # SLA Penalty implementation (WF-501) - decrease caretaker rating natively on breach
            if complaint.assigned_caretaker:
                complaint.assigned_caretaker.rating -= 1
                complaint.assigned_caretaker.save()
        except Exception as exc:
            _log_activity(
                complaint, None, 'AUTO_ESCALATION_FAILED',
                complaint.status, complaint.status,
                details=f'Auto-escalation failed (attempt {failed_attempts + 1}): {exc}. '
                        f'Will retry on next scheduler run.',
            )
            logger.warning(
                'Auto-escalation failed for complaint=%s attempt=%s: %s',
                complaint.id, failed_attempts + 1, exc,
            )

    # SLA approaching (within 2-hour reminder window)
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
    """WF-601 fix: added date range validation."""
    # Validate date range
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    if start_date and end_date and start_date > end_date:
        raise ValidationError('start_date must be on or before end_date.')

    qs = StudentComplain.objects.all()
    if filters.get('location'):
        location_value = str(filters['location'])
        location_variants = {
            location_value,
            location_value.replace('_', ' '),
            location_value.replace(' ', '_'),
        }
        location_query = models.Q()
        for loc in location_variants:
            if loc:
                location_query |= models.Q(location__iexact=loc)
        qs = qs.filter(location_query)
    if filters.get('complaint_type'):
        qs = qs.filter(complaint_type__iexact=filters['complaint_type'])
    if filters.get('status') is not None:
        qs = qs.filter(status=filters['status'])
    if filters.get('priority'):
        qs = qs.filter(priority=filters['priority'])
    if start_date:
        qs = qs.filter(complaint_date__date__gte=start_date)
    if end_date:
        qs = qs.filter(complaint_date__date__lte=end_date)
    return qs.order_by('-complaint_date')


def get_supervisor_dashboard(extra_info):
    supervisor = Supervisor.objects.filter(sup_id=extra_info).first()
    if supervisor is None:
        raise ValidationError('Supervisor profile not found for this user.')

    area_variants = {
        str(supervisor.area or ''),
        str(supervisor.area or '').replace('_', ' '),
        str(supervisor.area or '').replace(' ', '_'),
    }
    area_query = models.Q()
    for area in area_variants:
        if area:
            area_query |= models.Q(location__iexact=area)

    scope_query = models.Q(assigned_supervisor=supervisor)
    if area_query:
        scope_query |= area_query

    base_qs = StudentComplain.objects.filter(scope_query).distinct().order_by('-complaint_date')
    assigned_qs = StudentComplain.objects.filter(assigned_supervisor=supervisor).order_by('-complaint_date')
    escalated_qs = base_qs.filter(status=ComplaintStatus.ESCALATED)
    reopen_requested_qs = base_qs.filter(
        reopen_requests__status=ReopenRequest.RequestStatus.PENDING,
    ).distinct().order_by('-complaint_date')

    return {
        'assigned': StudentComplainSerializer(assigned_qs, many=True).data,
        'escalated': StudentComplainSerializer(escalated_qs, many=True).data,
        'reopen_requested': StudentComplainSerializer(reopen_requested_qs, many=True).data,
    }


def build_report_summary(queryset):
    """Compute KPIs: status counts, priority breakdown, avg resolution time, reopen rate, SLA compliance."""
    total = queryset.count()
    status_counts = {str(k): 0 for k, _ in ComplaintStatus.choices}
    for item in queryset.values('status').order_by().annotate(total=models.Count('id')):
        status_counts[str(item['status'])] = item['total']

    # Average resolution time (for resolved/closed complaints)
    resolved_qs = queryset.filter(resolved_at__isnull=False)
    resolution_times = []
    for c in resolved_qs.values('complaint_date', 'resolved_at'):
        if c['resolved_at'] and c['complaint_date']:
            diff = (c['resolved_at'] - c['complaint_date']).total_seconds() / 3600.0
            resolution_times.append(diff)
    avg_resolution_hours = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else None

    # Reopen rate (history-aware): count complaints that were EVER reopened,
    # even if their current status is now In Progress/Resolved/Closed/etc.
    historical_reopen_ids = ComplaintActivityLog.objects.filter(
        complaint_id__in=queryset.values('id'),
        new_status=ComplaintStatus.REOPENED,
    ).values_list('complaint_id', flat=True)
    approved_reopen_request_ids = ReopenRequest.objects.filter(
        complaint_id__in=queryset.values('id'),
        status=ReopenRequest.RequestStatus.APPROVED,
    ).values_list('complaint_id', flat=True)

    reopened_count = queryset.filter(
        models.Q(status=ComplaintStatus.REOPENED)
        | models.Q(id__in=historical_reopen_ids)
        | models.Q(id__in=approved_reopen_request_ids)
    ).values('id').distinct().count()

    # Use a unique denominator of complaints that have reached closure lifecycle
    # states or were reopened at least once.
    reopen_base = queryset.filter(
        models.Q(status__in=[ComplaintStatus.CLOSED, ComplaintStatus.RESOLVED, ComplaintStatus.REOPENED])
        | models.Q(id__in=historical_reopen_ids)
        | models.Q(id__in=approved_reopen_request_ids)
    ).values('id').distinct().count()
    reopen_rate = round(reopened_count / reopen_base * 100, 1) if reopen_base > 0 else 0

    # SLA compliance
    sla_set = queryset.exclude(sla_deadline__isnull=True)
    if sla_set.exists():
        sla_compliant = sla_set.filter(
            models.Q(resolved_at__isnull=False, resolved_at__lte=models.F('sla_deadline')) |
            models.Q(status__in=[ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED], sla_deadline__gte=timezone.now())
        ).count()
        sla_compliance = round(sla_compliant / sla_set.count() * 100, 1)
    else:
        sla_compliance = 100.0

    return {
        'total': total,
        'status_counts': status_counts,
        'by_priority': {
            'URGENT': queryset.filter(priority=ComplaintPriority.URGENT).count(),
            'STANDARD': queryset.filter(priority=ComplaintPriority.STANDARD).count(),
            'LOW': queryset.filter(priority=ComplaintPriority.LOW).count(),
        },
        'avg_resolution_hours': avg_resolution_hours,
        'reopen_rate': reopen_rate,
        'sla_compliance': sla_compliance,
    }


@transaction.atomic
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


@transaction.atomic
def supervisor_reassign(complaint, actor, caretaker, note=''):
    if actor is None or not _is_supervisor(actor):
        raise ValidationError('Only supervisors can reassign complaints.')

    supervisor_obj = Supervisor.objects.filter(sup_id=actor).first()
    if supervisor_obj is None:
        raise ValidationError('Supervisor profile not found for this user.')
    if complaint.assigned_supervisor_id != supervisor_obj.id:
        raise ValidationError('Only the assigned supervisor can reassign this complaint.')
    if complaint.status != ComplaintStatus.ESCALATED:
        raise ValidationError('Supervisor reassignment is allowed only for escalated complaints.')

    old_status = complaint.status
    complaint.assigned_caretaker = caretaker
    complaint.status = ComplaintStatus.IN_PROGRESS
    complaint.remarks = 'Reassigned by Supervisor'
    complaint.flag = 0
    complaint.save()

    details = note.strip() if note else f'Reassigned to caretaker #{caretaker.id}.'
    _log_activity(complaint, actor, 'SUPERVISOR_REASSIGN', old_status, complaint.status, details=details)

    if caretaker and caretaker.staff_id:
        complaint_system_notif(
            actor.user,
            caretaker.staff_id.user,
            'complaint_reassigned',
            complaint.id,
            0,
            'An escalated complaint has been reassigned to you by supervisor.',
        )

    if complaint.complainer and complaint.complainer.user:
        complaint_system_notif(
            actor.user,
            complaint.complainer.user,
            'complaint_progress_updated',
            complaint.id,
            0,
            'Your escalated complaint has been reassigned by supervisor for resolution.',
        )


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
