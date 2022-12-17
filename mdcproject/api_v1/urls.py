from django.urls import include, path
from rest_framework import routers

from .views import *


app_name = 'api_v1'


router = routers.DefaultRouter()
urlpatterns = [
    path('install/', InstallAppApiView.as_view(), name='install'),
    path('uninstall/', UninstallAppApiView.as_view(), name='uninstall'),
    path('index/', IndexApiView.as_view(), name='index'),

    path(r'merge-contacts/', MergeContactsViewSet.as_view(), name='merge_contacts'),
    path(r'status-merge-contacts/', StatusMergeContactsViewSet.as_view(), name='status_merge'),
    path(r'report/', ReportViewSet.as_view(), name='status_merge'),
    path(r'report-download/', ReportDownloadViewSet.as_view(), name='status_merge'),

    path(r'create-deal/', DealCreateUpdateViewSet.as_view(), name='create_deal'),
    path(r'update-deal/', DealCreateUpdateViewSet.as_view(), name='update_deal'),
]

urlpatterns += router.urls

