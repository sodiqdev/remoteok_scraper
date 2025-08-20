from rest_framework import viewsets, filters
from .models import Job
from .serializers import JobSerializer


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all().order_by("-remoteok_id")
    serializer_class = JobSerializer

    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'company']
