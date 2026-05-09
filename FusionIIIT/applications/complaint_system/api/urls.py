from django.urls import path

from . import views

urlpatterns = [
    # Complaint CRUD
    path('user/detail/<int:detailcomp_id1>/', views.complaint_details_api, name='complain-detail-get-api'),
    path('studentcomplain/', views.student_complain_api, name='complain-detail2-get-api'),
    path('newcomplain/', views.create_complain_api, name='complain-post-api'),
    path('updatecomplain/<int:c_id>/', views.edit_complain_api, name='complain-put-api'),
    path('removecomplain/<int:c_id>/', views.edit_complain_api, name='complain-delete-api'),

    # Complaint lifecycle
    path('complain/<int:c_id>/progress/', views.update_progress_api, name='complain-progress-api'),
    path('complain/<int:c_id>/escalate/', views.escalate_complaint_api, name='complain-escalate-api'),
    path('complain/<int:c_id>/supervisor-reassign/', views.supervisor_reassign_api, name='complain-supervisor-reassign-api'),
    path('complain/<int:c_id>/close/', views.close_complaint_api, name='complain-close-api'),
    path('complain/<int:c_id>/reopen/', views.reopen_complaint_api, name='complain-reopen-api'),
    path('complain/<int:c_id>/feedback/', views.feedback_api, name='complain-feedback-api'),
    path('complain/<int:c_id>/reopen-request/', views.reopen_request_api, name='complain-reopen-request-api'),

    # Reports & admin
    path('complaints/report/', views.report_api, name='complaints-report-api'),
    path('complaints/export/', views.export_report_api, name='complaints-export-api'),
    path('complaints/supervisor-dashboard/', views.supervisor_dashboard_api, name='complaints-supervisor-dashboard-api'),
    path('complaints/admin/', views.admin_oversight_api, name='complaints-admin-api'),

    # Worker management
    path('workers/', views.worker_api, name='worker-get-api'),
    path('addworker/', views.worker_api, name='worker-post-api'),
    path('removeworker/<int:w_id>/', views.edit_worker_api, name='worker-delete-api'),
    path('updateworker/<int:w_id>/', views.edit_worker_api, name='worker-put-api'),

    # Caretaker management
    path('caretakers/', views.caretaker_api, name='caretaker-get-api'),
    path('addcaretaker/', views.caretaker_api, name='caretaker-post-api'),
    path('removecaretaker/<int:c_id>/', views.edit_caretaker_api, name='caretaker-delete-api'),
    path('updatecaretaker/<int:c_id>/', views.edit_caretaker_api, name='caretaker-put-api'),

    # Supervisor management
    path('supervisors/', views.supervisor_api, name='supervisor-get-api'),
    path('addsupervisor/', views.supervisor_api, name='supervisor-post-api'),
    path('removesupervisor/<int:s_id>/', views.edit_supervisor_api, name='supervisor-delete-api'),
    path('updatesupervisor/<int:s_id>/', views.edit_supervisor_api, name='supervisor-put-api'),
]