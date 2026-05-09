from django.contrib.auth import get_user_model
from rest_framework import serializers
from applications.complaint_system.models import (
    Caretaker,
    ComplaintActivityLog,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintStatus,
    ReopenRequest,
    StudentComplain,
    Supervisor,
    Workers,
)
from applications.globals.models import ExtraInfo


class StudentComplainSerializer(serializers.ModelSerializer):
    has_pending_reopen_request = serializers.SerializerMethodField()
    latest_reopen_request_status = serializers.SerializerMethodField()
    has_feedback = serializers.SerializerMethodField()
    feedback_rating = serializers.SerializerMethodField()
    feedback_comments = serializers.SerializerMethodField()

    def get_has_pending_reopen_request(self, obj):
        return obj.reopen_requests.filter(status=ReopenRequest.RequestStatus.PENDING).exists()

    def get_latest_reopen_request_status(self, obj):
        latest = obj.reopen_requests.order_by('-created_at').first()
        return latest.status if latest else None

    def get_has_feedback(self, obj):
        return hasattr(obj, 'feedback_entry') and obj.feedback_entry is not None

    def get_feedback_rating(self, obj):
        if hasattr(obj, 'feedback_entry') and obj.feedback_entry is not None:
            return obj.feedback_entry.rating
        return None

    def get_feedback_comments(self, obj):
        if hasattr(obj, 'feedback_entry') and obj.feedback_entry is not None:
            return obj.feedback_entry.comments
        return ''

    class Meta:
        model = StudentComplain
        fields = (
            'id',
            'complainer',
            'complaint_date',
            'complaint_finish',
            'complaint_type',
            'location',
            'specific_location',
            'details',
            'status',
            'priority',
            'sla_deadline',
            'remarks',
            'flag',
            'reason',
            'feedback',
            'worker_id',
            'assigned_caretaker',
            'assigned_supervisor',
            'resolved_at',
            'closed_at',
            'upload_complaint',
            'upload_resolved',
            'comment',
            'escalation_level',
            'has_pending_reopen_request',
            'latest_reopen_request_status',
            'has_feedback',
            'feedback_rating',
            'feedback_comments',
        )


class ComplaintCreateSerializer(serializers.Serializer):
    complaint_type = serializers.ChoiceField(choices=[c[0] for c in StudentComplain._meta.get_field('complaint_type').choices])
    location = serializers.ChoiceField(choices=[c[0] for c in StudentComplain._meta.get_field('location').choices])
    specific_location = serializers.CharField(required=False, allow_blank=True, max_length=50)
    details = serializers.CharField(required=True, min_length=5, max_length=100)
    priority = serializers.ChoiceField(choices=ComplaintPriority.choices, required=False)
    upload_complaint = serializers.FileField(required=False)


class ComplaintProgressSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        if value not in [ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED]:
            raise serializers.ValidationError("Invalid status.")
        return value

    def validate(self, data):
        if data['status'] == ComplaintStatus.RESOLVED and not data.get('note'):
            raise serializers.ValidationError("A resolution note is required when marking a complaint as Resolved.")
        return data


class ComplaintEscalateSerializer(serializers.Serializer):
    justification = serializers.CharField(required=True, min_length=10)


class ComplaintCloseSerializer(serializers.Serializer):
    verified = serializers.BooleanField(required=True)


class ComplaintReopenSerializer(serializers.Serializer):
    justification = serializers.CharField(required=True, min_length=10)


class ComplaintFeedbackSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = ComplaintFeedback
        fields = ('rating', 'comments')


class ComplaintAdminAssignSerializer(serializers.Serializer):
    complaint_id = serializers.IntegerField(required=True)
    caretaker_id = serializers.IntegerField(required=False)
    supervisor_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if attrs.get('caretaker_id') is None and attrs.get('supervisor_id') is None:
            raise serializers.ValidationError('At least one of caretaker_id or supervisor_id is required.')
        return attrs


class SupervisorReassignSerializer(serializers.Serializer):
    caretaker_id = serializers.IntegerField(required=True)
    note = serializers.CharField(required=False, allow_blank=True, default='')


class ReopenRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReopenRequest
        fields = ('id', 'complaint', 'requester', 'justification', 'status', 'reviewed_by', 'review_note', 'created_at', 'reviewed_at')
        read_only_fields = ('id', 'complaint', 'requester', 'status', 'reviewed_by', 'review_note', 'created_at', 'reviewed_at')


class ReopenRequestCreateSerializer(serializers.Serializer):
    justification = serializers.CharField(required=True, min_length=10)


class ReopenRequestReviewSerializer(serializers.Serializer):
    approved = serializers.BooleanField(required=True)
    review_note = serializers.CharField(required=False, allow_blank=True, default='')


class ReportExportSerializer(serializers.Serializer):
    FORMAT_CHOICES = [('csv', 'CSV'), ('pdf', 'PDF'), ('excel', 'Excel')]
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='csv')
    location = serializers.CharField(required=False, allow_blank=True)
    complaint_type = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.CharField(required=False, allow_blank=True)
    status = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class ComplaintActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintActivityLog
        fields = ('id', 'action', 'previous_status', 'new_status', 'details', 'timestamp')


class WorkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workers
        fields = (
            'id',
            'caretaker_id',
            'name',
            'age',
            'phone',
            'worker_type',
        )


class CaretakerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caretaker
        fields = (
            'id',
            'staff_id',
            'area',
            'rating',
            'myfeedback',
        )


class SupervisorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supervisor
        fields = (
            'id',
            'sup_id',
            'area',
        )


class ExtraInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraInfo
        fields = (
            'id',
            'user',
            'title',
            'sex',
            'date_of_birth',
            'user_status',
            'address',
            'phone_no',
            'user_type',
            'department',
            'profile_picture',
            'about_me',
            'date_modified',
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
        )