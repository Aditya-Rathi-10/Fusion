"""
conftest.py — Initial setup scaffold.
Customize this file with your module's specific logic.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import SimpleTestCase

from applications.complaint_system.models import (
    Caretaker,
    Complaint_Admin,
    ServiceAuthority,
    ServiceProvider,
    StudentComplain,
    Supervisor,
)
from applications.globals.models import DepartmentInfo, Designation, ExtraInfo, HoldsDesignation


class BaseModuleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.department = DepartmentInfo.objects.create(name="CSE")
        cls.designation_caretaker = Designation.objects.create(
            name="hall1caretaker",
            full_name="Hall 1 Caretaker",
            type="administrative",
        )
        cls.designation_supervisor = Designation.objects.create(
            name="hall1supervisor",
            full_name="Hall 1 Supervisor",
            type="administrative",
        )
        cls.designation_complaint_admin = Designation.objects.create(
            name="complaintadmin",
            full_name="Complaint Admin",
            type="administrative",
        )

        cls.user_student = User.objects.create_user(
            username="student1",
            password="testpass123",
        )
        cls.user_caretaker = User.objects.create_user(
            username="caretaker1",
            password="testpass123",
        )
        cls.user_supervisor = User.objects.create_user(
            username="supervisor1",
            password="testpass123",
        )
        cls.user_service_provider = User.objects.create_user(
            username="serviceprovider1",
            password="testpass123",
        )
        cls.user_service_authority = User.objects.create_user(
            username="serviceauthority1",
            password="testpass123",
        )
        cls.user_admin = User.objects.create_user(
            username="complaintadmin1",
            password="testpass123",
        )

        cls.extra_student = ExtraInfo.objects.create(
            id="STU001",
            user=cls.user_student,
            user_type="student",
            department=cls.department,
        )
        cls.extra_caretaker = ExtraInfo.objects.create(
            id="CARE001",
            user=cls.user_caretaker,
            user_type="staff",
            department=cls.department,
        )
        cls.extra_supervisor = ExtraInfo.objects.create(
            id="SUP001",
            user=cls.user_supervisor,
            user_type="staff",
            department=cls.department,
        )
        cls.extra_service_provider = ExtraInfo.objects.create(
            id="SP001",
            user=cls.user_service_provider,
            user_type="staff",
            department=cls.department,
        )
        cls.extra_service_authority = ExtraInfo.objects.create(
            id="SA001",
            user=cls.user_service_authority,
            user_type="staff",
            department=cls.department,
        )
        cls.extra_admin = ExtraInfo.objects.create(
            id="ADMIN001",
            user=cls.user_admin,
            user_type="staff",
            department=cls.department,
        )

        HoldsDesignation.objects.create(
            user=cls.user_caretaker,
            working=cls.user_caretaker,
            designation=cls.designation_caretaker,
        )
        HoldsDesignation.objects.create(
            user=cls.user_supervisor,
            working=cls.user_supervisor,
            designation=cls.designation_supervisor,
        )
        HoldsDesignation.objects.create(
            user=cls.user_admin,
            working=cls.user_admin,
            designation=cls.designation_complaint_admin,
        )

        cls.caretaker = Caretaker.objects.create(
            staff_id=cls.extra_caretaker,
            area="hall-1",
        )
        cls.supervisor = Supervisor.objects.create(
            sup_id=cls.extra_supervisor,
            area="hall-1",
        )
        cls.service_provider = ServiceProvider.objects.create(
            ser_pro_id=cls.extra_service_provider,
            type="Electricity",
        )
        cls.service_authority = ServiceAuthority.objects.create(
            ser_pro_id=cls.extra_service_authority,
            type="Electricity",
        )
        cls.complaint_admin = Complaint_Admin.objects.create(
            sup_id=cls.extra_admin,
        )

        cls.complaint = StudentComplain.objects.create(
            complainer=cls.extra_student,
            complaint_type="Electricity",
            location="hall-1",
            specific_location="Room 101",
            details="Power outage",
            assigned_caretaker=cls.caretaker,
            assigned_supervisor=cls.supervisor,
        )


class ReportingSimpleTestCase(SimpleTestCase):
    """Lightweight base class for report-oriented tests that do not require DB I/O."""

    def setUp(self):
        super().setUp()
        self._test_id = ""
        self._uc_id = ""
        self._br_id = ""
        self._wf_id = ""
        self._test_category = ""
        self._scenario = ""
        self._preconditions = ""
        self._input_action = ""
        self._expected_result = ""
        self._results = []
        self._steps = []

    def _record_result(self, actual, status, evidence=""):
        self._results.append(
            {
                "actual": actual,
                "status": status,
                "evidence": evidence,
            }
        )

    def _add_step(self, number, action, expected, actual, passed):
        self._steps.append(
            {
                "step": number,
                "action": action,
                "expected": expected,
                "actual": actual,
                "status": "Pass" if passed else "Fail",
            }
        )

    def _all_steps_passed(self):
        return all(step.get("status") == "Pass" for step in self._steps)


class UCTestBase(ReportingSimpleTestCase):
    pass


class BRTestBase(ReportingSimpleTestCase):
    pass


class WFTestBase(ReportingSimpleTestCase):
    pass
