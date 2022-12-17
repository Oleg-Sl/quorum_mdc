import os
import logging
from threading import Thread
from django.shortcuts import render
from django.http import FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings


from .services.bx24 import tokens
from .services import tasks

logger_access = logging.getLogger('access')
logger_access.setLevel(logging.INFO)
fh_access = logging.handlers.TimedRotatingFileHandler('./logs/access/access.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_access = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_access.setFormatter(formatter_access)
logger_access.addHandler(fh_access)

logger_error = logging.getLogger('errors')
logger_error.setLevel(logging.INFO)
fh_errors = logging.handlers.TimedRotatingFileHandler('./logs/errors/errors.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_errors = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_errors.setFormatter(formatter_errors)
logger_error.addHandler(fh_errors)


THREAD_MERGE = None


class InstallAppApiView(views.APIView):
    permission_classes = [AllowAny]

    @xframe_options_exempt
    def post(self, request):
        data = {
            "domain": request.query_params.get("DOMAIN", ""),
            "auth_token": request.data.get("AUTH_ID", ""),
            "expires_in": request.data.get("AUTH_EXPIRES", 3600),
            "refresh_token": request.data.get("REFRESH_ID", ""),
            'client_endpoint': f'https://{request.query_params.get("DOMAIN", "")}/rest/',
            "application_token": settings.APP_TOKEN,
            "client_secret": settings.CLIENT_SECRET,
            "client_id": settings.CLIENT_ID,
            # "application_token": request.query_params.get("APP_SID", ""),
        }
        tokens.create_secrets_bx24(data)
        logger_access.info({
            "view": "InstallAppApiView",
            "request": request.data,
            "params": request.query_params,
        })
        return render(request, 'install.html', context={
            "domain": settings.DOMEN,
            "url_path": settings.URL_PATH,
        })


class UninstallAppApiView(views.APIView):
    permission_classes = [AllowAny]

    @xframe_options_exempt
    def post(self, request):
        logger_access.info({
            "view": "UninstallAppApiView",
            "request": request.data,
            "params": request.query_params,
        })
        return Response(status.HTTP_200_OK)


class IndexApiView(views.APIView):
    permission_classes = [AllowAny]

    @xframe_options_exempt
    def post(self, request):
        logger_access.info({
            "view": "IndexApiView",
            "request": request.data,
            "params": request.query_params,
        })
        return render(request, 'index.html', context={
            "domain": settings.DOMEN,
            "url_path": settings.URL_PATH,
        })

    @xframe_options_exempt
    def get(self, request):
        logger_access.info({
            "view": "IndexApiView",
            "request": request.data,
            "params": request.query_params,
        })
        return render(request, 'index.html', context={
            "domain": settings.DOMEN,
            "url_path": settings.URL_PATH,
        })


class DealCreateUpdateViewSet(views.APIView):
    permission_classes = [AllowAny]

    """ Контроллер обработки событий BX24: onVoximplantCallEnd """
    def post(self, request):
        logger_access.info({
            "view": "DealCreateUpdateViewSet",
            "request": request.data,
            "params": request.query_params,
        })
        event = request.data.get("event", "")
        id_deal = request.data.get("data[FIELDS][ID]", None)
        application_token = request.data.get("auth[application_token]", None)

        if tokens.get_secret_bx24("application_token") != application_token:
            logger_error.error({
                "view": "DealCreateUpdateViewSet",
                "request": request.data,
                "error": "Unverified event source",
            })
            return Response("Unverified event source", status=status.HTTP_400_BAD_REQUEST)

        if not id_deal:
            logger_error.error({
                "view": "DealCreateUpdateViewSet",
                "request": request.data,
                "error": "Not transferred ID deal",
            })
            return Response("Not transferred ID deal", status=status.HTTP_400_BAD_REQUEST)

        status_code, msg = tasks.bind_company_to_deal_associated_with_contact(id_deal)

        if status_code == 200:
            return Response(msg, status=status.HTTP_200_OK)
        else:
            logger_error.error({
                "view": "DealCreateUpdateViewSet",
                "request": request.data,
                "error": msg,
            })
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)


class MergeContactsViewSet(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        global THREAD_MERGE
        filters = {}
        logger_access.info({
            "view": "MergeContactsViewSet",
            "request": request.data,
            "params": request.query_params,
        })
        method = request.data.get("method")
        assigned_id = request.data.get("assigned_id")

        if THREAD_MERGE and THREAD_MERGE.is_alive():
            return Response("NO", status=status.HTTP_200_OK)

        if assigned_id:
            filters["ASSIGNED_BY_ID"] = assigned_id

        thread_merge = Thread(target=tasks.merge_contacts, args=[method, filters, ])
        thread_merge.start()

        return Response("Ok", status=status.HTTP_200_OK)


class StatusMergeContactsViewSet(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        global THREAD_MERGE
        res = {
            "status": False
        }

        if THREAD_MERGE:
            state = THREAD_MERGE.is_alive()
            res["status"] = state
            if state:
                res["contacts"] = {
                    "start": tasks.QUEUE_CONTACTS.get_start_size(),
                    "actual": tasks.QUEUE_CONTACTS.qsize()
                }
                res["companies"] = {
                    "start": tasks.QUEUEU_COMPANIES.get_start_size(),
                    "actual": tasks.QUEUEU_COMPANIES.qsize()
                }
                res["deals"] = {
                    "start": tasks.QUEUE_DEALS.get_start_size(),
                    "actual": tasks.QUEUE_DEALS.qsize()
                }
                res["contact_company"] = {
                    "start": tasks.QUEUE_COMPANY_CONTACT.get_start_size(),
                    "actual": tasks.QUEUE_COMPANY_CONTACT.qsize()
                }
                res["contact_deal"] = {
                    "start": tasks.QUEUE_DEAL_CONTACT.get_start_size(),
                    "actual": tasks.QUEUE_DEAL_CONTACT.qsize()
                }
                res["duplicates"] = {
                    "start": tasks.QUEUE_DUPLICATES.get_start_size(),
                    "actual": tasks.QUEUE_DUPLICATES.qsize()
                }

        return Response(res, status=status.HTTP_200_OK)


class ReportViewSet(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        path = os.path.join(settings.BASE_DIR, 'reports')
        return Response(os.listdir(path), status=status.HTTP_200_OK)


class ReportDownloadViewSet(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger_access.info({
            "view": "ReportDownloadViewSet",
            "method": "get",
            "request": request.data,
            "params": request.query_params,
        })
        f_name = request.query_params.get("file")
        if not f_name:
            logger_error.error({
                "view": "ReportDownloadViewSet",
                "method": "get",
                "request": request.data,
                "params": request.query_params,
                "error": "Not found file"
            })
            return Response('Not found file', status=status.HTTP_404_NOT_FOUND)

        path = os.path.join(settings.BASE_DIR, 'reports', f_name)

        try:
            response = FileResponse(open(path, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(path)
            return response
        except Exception as err:
            logger_error.error({
                "view": "ReportDownloadViewSet",
                "method": "get",
                "request": request.data,
                "params": request.query_params,
                "error": err
            })
            raise Http404

    def delete(self, request, *args, **kwargs):
        logger_access.info({
            "view": "ReportDownloadViewSet",
            "method": "delete",
            "request": request.data,
            "params": request.query_params,
        })
        f_name = request.query_params.get("file")
        if not f_name:
            logger_error.error({
                "view": "ReportDownloadViewSet",
                "method": "delete",
                "request": request.data,
                "params": request.query_params,
                "error": "File name not passed"
            })
            return Response('File name not passed', status=status.HTTP_404_NOT_FOUND)

        path = os.path.join(settings.BASE_DIR, 'reports', f_name)
        if os.path.exists(path):
            os.remove(path)
            return Response(status=status.HTTP_204_NO_CONTENT)

        logger_error.error({
            "view": "ReportDownloadViewSet",
            "method": "delete",
            "request": request.data,
            "params": request.query_params,
            "error": "Not found file"
        })
        return Response('Not found file', status=status.HTTP_404_NOT_FOUND)

