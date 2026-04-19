from django.contrib.auth import get_user_model
from rest_framework import serializers
from applications.complaint_system.models import (
    Caretaker,
    ComplaintActivityLog,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintStatus,
    StudentComplain,
    Supervisor,
    Workers,
)
from applications.globals.models import ExtraInfo


class StudentComplainSerializer(serializers.ModelSerializer):
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
        )


class ComplaintCreateSerializer(serializers.Serializer):
    complaint_type = serializers.ChoiceField(choices=[c[0] for c in StudentComplain._meta.get_field('complaint_type').choices])
    location = serializers.ChoiceField(choices=[c[0] for c in StudentComplain._meta.get_field('location').choices])
    specific_location = serializers.CharField(required=False, allow_blank=True, max_length=50)
    details = serializers.CharField(required=True, min_length=5, max_length=100)
    priority = serializers.ChoiceField(choices=ComplaintPriority.choices, required=False)
    upload_complaint = serializers.FileField(required=False)


class ComplaintProgressSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED, ComplaintStatus.DECLINED])
    note = serializers.CharField(required=False, allow_blank=True)

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
    caretaker_id = serializers.IntegerField(required=False)
    supervisor_id = serializers.IntegerField(required=False)


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