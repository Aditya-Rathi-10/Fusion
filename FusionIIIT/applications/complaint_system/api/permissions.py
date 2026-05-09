from rest_framework.permissions import BasePermission
from applications.globals.services import get_extra_info_by_user
from applications.globals.models import ExtraInfo
from applications.complaint_system.models import Caretaker, Supervisor, Complaint_Admin, ServiceAuthority


class IsCaretaker(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        extra_info = get_extra_info_by_user(request.user)
        return Caretaker.objects.filter(staff_id=extra_info).exists()


class IsSupervisor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        extra_info = get_extra_info_by_user(request.user)
        return Supervisor.objects.filter(sup_id=extra_info).exists()


class IsSupervisorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        extra_info = get_extra_info_by_user(request.user)
        if Supervisor.objects.filter(sup_id=extra_info).exists():
            return True
        if Complaint_Admin.objects.filter(sup_id=extra_info).exists():
            return True
        if ServiceAuthority.objects.filter(ser_pro_id=extra_info).exists():
            return True
        return False


class IsComplaintAdminOrServiceAuthority(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        extra_info = get_extra_info_by_user(request.user)
        is_admin = Complaint_Admin.objects.filter(sup_id=extra_info).exists()
        is_service_authority = ServiceAuthority.objects.filter(ser_pro_id=extra_info).exists()
        return is_admin or is_service_authority


class IsSupervisorOrComplaintAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        extra_info = get_extra_info_by_user(request.user)
        if Supervisor.objects.filter(sup_id=extra_info).exists():
            return True
        if Complaint_Admin.objects.filter(sup_id=extra_info).exists():
            return True
        if ServiceAuthority.objects.filter(ser_pro_id=extra_info).exists():
            return True
        return False
