from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from applications.globals.services import get_extra_info_by_user
from . import messages, selectors, services
from .permissions import IsCaretaker, IsSupervisor, IsSupervisorOrAdmin
from .serializers import (
    CaretakerSerializer,
    ComplaintAdminAssignSerializer,
    ComplaintCloseSerializer,
    ComplaintCreateSerializer,
    ComplaintEscalateSerializer,
    ComplaintFeedbackSerializer,
    ComplaintProgressSerializer,
    ComplaintReopenSerializer,
    StudentComplainSerializer,
    SupervisorSerializer,
    WorkerSerializer,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def complaint_details_api(request,detailcomp_id1):
    complaint_detail = selectors.get_complaint(detailcomp_id1)
    if not services.can_access_complaint(request.user, complaint_detail):
        return Response({'message': messages.PERMISSION_DENIED}, status=status.HTTP_403_FORBIDDEN)
    response = services.build_complaint_payload(complaint_detail)
    return Response(data=response, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def student_complain_api(request):
    extra_info = get_extra_info_by_user(request.user)
    complain = services.get_complains_for_user(extra_info)
    complains = StudentComplainSerializer(complain, many=True).data
    resp = {
        'student_complain': complains,
    }
    return Response(data=resp, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def create_complain_api(request):
    serializer = ComplaintCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    extra_info = get_extra_info_by_user(request.user)
    data = services.create_complaint(extra_info, serializer.validated_data)
    return Response(data, status=status.HTTP_201_CREATED)

@api_view(['DELETE','PUT'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def edit_complain_api(request,c_id):
    complain = selectors.get_complaint(c_id)
    if not services.can_access_complaint(request.user, complain):
        return Response({'message': messages.PERMISSION_DENIED}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        services.delete_complaint(complain)
        return Response(status=status.HTTP_204_NO_CONTENT)
    elif request.method == 'PUT':
        data = services.update_complaint(complain, request.data)
        return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def update_progress_api(request, c_id):
    complain = selectors.get_complaint(c_id)
    serializer = ComplaintProgressSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.update_progress(
        complain,
        get_extra_info_by_user(request.user),
        serializer.validated_data['status'],
        serializer.validated_data.get('note', ''),
        request.FILES.get('upload_resolved'),
    )
    return Response({'message': 'Progress updated.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def escalate_complaint_api(request, c_id):
    complain = selectors.get_complaint(c_id)
    serializer = ComplaintEscalateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.escalate_complaint(
        complain,
        get_extra_info_by_user(request.user),
        serializer.validated_data['justification'],
        is_auto=False,
    )
    return Response({'message': 'Complaint escalated.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def close_complaint_api(request, c_id):
    complain = selectors.get_complaint(c_id)
    if not services.can_access_complaint(request.user, complain):
        return Response({'message': messages.PERMISSION_DENIED}, status=status.HTTP_403_FORBIDDEN)
    serializer = ComplaintCloseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.close_complaint(complain, get_extra_info_by_user(request.user), serializer.validated_data['verified'])
    return Response({'message': 'Complaint closed.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def reopen_complaint_api(request, c_id):
    complain = selectors.get_complaint(c_id)
    if not services.can_access_complaint(request.user, complain):
        return Response({'message': messages.PERMISSION_DENIED}, status=status.HTTP_403_FORBIDDEN)
    serializer = ComplaintReopenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.reopen_complaint(complain, get_extra_info_by_user(request.user), serializer.validated_data['justification'])
    return Response({'message': 'Complaint reopened.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def feedback_api(request, c_id):
    complain = selectors.get_complaint(c_id)
    if not services.can_access_complaint(request.user, complain):
        return Response({'message': messages.PERMISSION_DENIED}, status=status.HTTP_403_FORBIDDEN)
    serializer = ComplaintFeedbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    services.submit_feedback(complain, serializer.validated_data['rating'], serializer.validated_data.get('comments', ''))
    return Response({'message': 'Feedback submitted.'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupervisorOrAdmin])
@authentication_classes([TokenAuthentication])
def report_api(request):
    filters = {
        'location': request.GET.get('location') or None,
        'complaint_type': request.GET.get('complaint_type') or None,
        'priority': request.GET.get('priority') or None,
        'status': request.GET.get('status'),
        'start_date': request.GET.get('start_date') or None,
        'end_date': request.GET.get('end_date') or None,
    }
    if filters['status'] is not None:
        try:
            filters['status'] = int(filters['status'])
        except ValueError:
            return Response({'message': 'Invalid status filter.'}, status=status.HTTP_400_BAD_REQUEST)
    qs = services.generate_report(filters)
    data = StudentComplainSerializer(qs, many=True).data
    summary = services.build_report_summary(qs)
    return Response({'results': data, 'count': len(data), 'summary': summary}, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
@authentication_classes([TokenAuthentication])
def admin_oversight_api(request):
    if request.method == 'GET':
        qs = selectors.list_unresolved()
        data = StudentComplainSerializer(qs, many=True).data
        return Response({'results': data, 'count': len(data)}, status=status.HTTP_200_OK)

    serializer = ComplaintAdminAssignSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    complaint_id = request.data.get('complaint_id')
    if not complaint_id:
        return Response({'message': 'complaint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    complaint = selectors.get_complaint(complaint_id)
    caretaker = None
    supervisor = None
    if serializer.validated_data.get('caretaker_id'):
        caretaker = selectors.get_caretaker(serializer.validated_data['caretaker_id'])
    if serializer.validated_data.get('supervisor_id'):
        supervisor = selectors.get_supervisor(serializer.validated_data['supervisor_id'])
    services.admin_assign(complaint, caretaker=caretaker, supervisor=supervisor, actor=get_extra_info_by_user(request.user))
    return Response({'message': 'Admin assignment updated.'}, status=status.HTTP_200_OK)

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated, IsCaretaker])
@authentication_classes([TokenAuthentication])
def worker_api(request):

    if request.method == 'GET':
        worker = services.list_workers()
        workers = WorkerSerializer(worker, many=True).data
        resp = {
            'workers': workers,
        }
        return Response(data=resp, status=status.HTTP_200_OK)

    elif request.method =='POST':
        data = services.create_worker(request.data)
        return Response(data, status=status.HTTP_201_CREATED)

@api_view(['DELETE','PUT'])
@permission_classes([IsAuthenticated, IsCaretaker])
@authentication_classes([TokenAuthentication])
def edit_worker_api(request,w_id):
    worker = selectors.get_worker(w_id)
    if request.method == 'DELETE':
        services.delete_worker(worker)
        return Response(status=status.HTTP_204_NO_CONTENT)
    elif request.method == 'PUT':
        data = services.update_worker(worker, request.data)
        return Response(data, status=status.HTTP_200_OK)

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated, IsSupervisor])
@authentication_classes([TokenAuthentication])
def caretaker_api(request):

    if request.method == 'GET':
        caretaker = services.list_caretakers()
        caretakers = CaretakerSerializer(caretaker, many=True).data
        resp = {
            'caretakers': caretakers,
        }
        return Response(data=resp, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        data = services.create_caretaker(request.data)
        return Response(data, status=status.HTTP_201_CREATED)

@api_view(['DELETE','PUT'])
@permission_classes([IsAuthenticated, IsSupervisor])
@authentication_classes([TokenAuthentication])
def edit_caretaker_api(request,c_id):
    caretaker = selectors.get_caretaker(c_id)
    if request.method == 'DELETE':
        services.delete_caretaker(caretaker)
        return Response(status=status.HTTP_204_NO_CONTENT)
    elif request.method == 'PUT':
        data = services.update_caretaker(caretaker, request.data)
        return Response(data, status=status.HTTP_200_OK)

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
@authentication_classes([TokenAuthentication])
def supervisor_api(request):

    if request.method == 'GET':
        supervisor = services.list_supervisors()
        supervisors = SupervisorSerializer(supervisor, many=True).data
        resp = {
            'supervisors': supervisors,
        }
        return Response(data=resp, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        data = services.create_supervisor(request.data)
        return Response(data, status=status.HTTP_201_CREATED)
   
@api_view(['DELETE','PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
@authentication_classes([TokenAuthentication])
def edit_supervisor_api(request,s_id):
    supervisor = selectors.get_supervisor(s_id)
    if request.method == 'DELETE':
        services.delete_supervisor(supervisor)
        return Response(status=status.HTTP_204_NO_CONTENT)
    elif request.method == 'PUT':
        data = services.update_supervisor(supervisor, request.data)
        return Response(data, status=status.HTTP_200_OK)

