from rest_framework.permissions import BasePermission
from applications.globals.services import get_extra_info_by_user
from applications.complaint_system.models import Caretaker, Supervisor


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
        return Supervisor.objects.filter(sup_id=extra_info).exists()
