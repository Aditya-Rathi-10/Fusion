from rest_framework import serializers
from .models import StudentComplain, Caretaker, Warden, Complaint_Admin, Workers, ReopenRequest

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
        fields = "__all__"

class CaretakerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caretaker
        fields = '__all__'

class WardenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warden
        fields = '__all__'

class Complaint_AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint_Admin
        fields = '__all__'

class FeedbackSerializer(serializers.Serializer):
    feedback = serializers.CharField()
    rating = serializers.IntegerField()

class ResolvePendingSerializer(serializers.Serializer):
    yesorno = serializers.ChoiceField(choices=[('Yes', 'Yes'), ('No', 'No')])
    comment = serializers.CharField(required=False, allow_blank=True)
    upload_resolved = serializers.ImageField(required=False, allow_null=True)

class WorkersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workers
        fields = '__all__'
