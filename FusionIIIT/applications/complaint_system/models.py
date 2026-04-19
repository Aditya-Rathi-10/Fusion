# imports
from django.db import models
from django.utils import timezone

from applications.globals.models import ExtraInfo

# Class definations:


class Constants:
    AREA = (
        ('hall-1', 'hall-1'),
        ('hall-3', 'hall-3'),
        ('hall-4', 'hall-4'),
        ('CC1', 'CC1'),
        ('CC2', 'CC2'),
        ('core_lab', 'core_lab'),
        ('LHTC', 'LHTC'),
        ('NR2', 'NR2'),
        ('Rewa_Residency', 'Rewa_Residency'),
        ('Maa Saraswati Hostel', 'Maa Saraswati Hostel'),
        ('Nagarjun Hostel', 'Nagarjun Hostel'),
        ('Panini Hostel', 'Panini Hostel'),

    )
    COMPLAINT_TYPE = (
        ('Electricity', 'Electricity'),
        ('carpenter', 'carpenter'),
        ('plumber', 'plumber'),
        ('garbage', 'garbage'),
        ('dustbin', 'dustbin'),
        ('internet', 'internet'),
        ('other', 'other'),
    )


class ComplaintPriority(models.TextChoices):
    URGENT = 'URGENT', 'Urgent (24h SLA)'
    STANDARD = 'STANDARD', 'Standard (3d SLA)'
    LOW = 'LOW', 'Low (7d SLA)'


class ComplaintStatus(models.IntegerChoices):
    PENDING = 0, 'Pending'
    IN_PROGRESS = 1, 'In Progress'
    RESOLVED = 2, 'Resolved'
    DECLINED = 3, 'Declined'
    ESCALATED = 4, 'Escalated'
    CLOSED = 5, 'Closed'
    REOPENED = 6, 'Reopened'


class Caretaker(models.Model):
    staff_id = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE)
    area = models.CharField(choices=Constants.AREA, max_length=20, default='hall-3')
    rating = models.IntegerField(default=0)
    myfeedback = models.CharField(max_length=400, default='this is my feedback')
    # no_of_comps = models.CharField(max_length=1000)

    def __str__(self):
        return str(self.id) + '-' + self.area


class Workers(models.Model):
    caretaker_id = models.ForeignKey(Caretaker, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    age = models.CharField(max_length=10)
    phone = models.BigIntegerField(blank=True)
    worker_type = models.CharField(choices=Constants.COMPLAINT_TYPE,
                                   max_length=20, default='internet')

    def __str__(self):
        return str(self.id) + '-' + self.name


class StudentComplain(models.Model):
    complainer = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE)
    complaint_date = models.DateTimeField(default=timezone.now)
    complaint_finish = models.DateField(blank=True, null=True)
    complaint_type = models.CharField(choices=Constants.COMPLAINT_TYPE,
                                      max_length=20, default='internet')
    location = models.CharField(max_length=20, choices=Constants.AREA)
    specific_location = models.CharField(max_length=50, blank=True)
    details = models.CharField(max_length=100)
    status = models.IntegerField(choices=ComplaintStatus.choices, default=ComplaintStatus.PENDING)
    priority = models.CharField(max_length=20, choices=ComplaintPriority.choices, default=ComplaintPriority.STANDARD)
    sla_deadline = models.DateTimeField(blank=True, null=True)
    remarks = models.CharField(max_length=300, default="Pending")
    flag = models.IntegerField(default='0')
    reason = models.CharField(max_length=100, blank=True, default="None")
    feedback = models.CharField(max_length=500, blank=True)
    worker_id = models.ForeignKey(Workers, blank=True, null=True,on_delete=models.CASCADE)
    assigned_caretaker = models.ForeignKey(Caretaker, blank=True, null=True, on_delete=models.SET_NULL, related_name='assigned_complaints')
    assigned_supervisor = models.ForeignKey('Supervisor', blank=True, null=True, on_delete=models.SET_NULL, related_name='escalated_complaints')
    resolved_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    upload_complaint = models.FileField(blank=True)
    upload_resolved = models.FileField(blank=True, null=True)
    comment = models.CharField(max_length=100,  default="None")
    #upload_resolved = models.FileField(blank=True,null=True)

    def __str__(self):
        return str(self.complainer.user.username)


class Supervisor(models.Model):
    sup_id = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE)
    area = models.CharField(choices=Constants.AREA, max_length=20)

    def __str__(self):
        return str(self.sup_id.user.username)


class ComplaintActivityLog(models.Model):
    complaint = models.ForeignKey(StudentComplain, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(ExtraInfo, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    previous_status = models.IntegerField(blank=True, null=True)
    new_status = models.IntegerField(blank=True, null=True)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class ComplaintFeedback(models.Model):
    complaint = models.OneToOneField(StudentComplain, on_delete=models.CASCADE, related_name='feedback_entry')
    rating = models.PositiveSmallIntegerField()
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
