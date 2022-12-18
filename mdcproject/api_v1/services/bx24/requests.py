import json
import os
import time
import re
import logging
from requests import adapters, post, exceptions, get as http_get
from urllib.parse import unquote
from mimetypes import guess_extension as extension
from django.conf import settings


from .tokens import update_secrets_bx24, get_secrets_all_bx24
from ..parameters import BX24__COUNT_METHODS_IN_BATH, BX24__COUNT_RECORDS_IN_METHODS


logger_request_success = logging.getLogger('request_success')
logger_request_success.setLevel(logging.INFO)
fh_request_success = logging.handlers.TimedRotatingFileHandler('./logs/request_success/success.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_request_success = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_request_success.setFormatter(formatter_request_success)
logger_request_success.addHandler(fh_request_success)

logger_request_errors = logging.getLogger('request_errors')
logger_request_errors.setLevel(logging.INFO)
fh_request_errors = logging.handlers.TimedRotatingFileHandler('./logs/request_errors/errors.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_request_errors = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_request_errors.setFormatter(formatter_request_errors)
logger_request_errors.addHandler(fh_request_errors)


adapters.DEFAULT_RETRIES = 10


class Bitrix24:
    api_url = 'https://{domain}/rest/{method}.json'
    oauth_url = 'https://oauth.bitrix.info/oauth/token/'
    timeout = 60

    def __init__(self):
        self.length_batch = BX24__COUNT_METHODS_IN_BATH
        self.domain = None
        self.auth_token = None
        self.refresh_token = None
        self.client_id = None
        self.client_secret = None
        self.expires_in = None
        self.init_tokens()

    def init_tokens(self):
        tokens = get_secrets_all_bx24()
        # print("tokens = ", tokens)
        logger_request_success.info(tokens)
        self.domain = tokens.get("domain", None)
        self.auth_token = tokens.get("auth_token", None)
        self.refresh_token = tokens.get("refresh_token", None)
        self.client_id = tokens.get("client_id")
        self.client_secret = tokens.get("client_secret")
        self.expires_in = None

    def refresh_tokens(self):
        r = {}
        try:
            r = post(
                self.oauth_url,
                params={'grant_type': 'refresh_token', 'client_id': self.client_id, 'client_secret': self.client_secret,
                        'refresh_token': self.refresh_token})
            logger_request_success.info({
                "func": "refresh_tokens",
                "url": self.oauth_url,
                "params": {'grant_type': 'refresh_token', 'client_id': self.client_id, 'client_secret': self.client_secret,
                        'refresh_token': self.refresh_token},
                "state": "post_req",
                "result": r.text
            })
            result = json.loads(r.text)

            self.auth_token = result['access_token']
            self.refresh_token = result['refresh_token']
            self.expires_in = result['expires_in']
            update_secrets_bx24(self.auth_token, self.expires_in, self.refresh_token)
            return True
        except (ValueError, KeyError) as err:
            logger_request_errors.error({
                "func": "refresh_tokens",
                "error": err,
                "text": r.text
            })
            result = dict(error='Error on decode oauth response [%s]' % r.text)
            return result
        except Exception as err:
            logger_request_errors.error({
                "func": "refresh_tokens",
                "error": err,
                "text": r.text
            })

    def call(self, method, data):
        if not self.domain or self.auth_token:
            self.init_tokens()
        r = {}
        try:
            url = self.api_url.format(domain=self.domain, method=method)
            params = dict(auth=self.auth_token)
            headers = {
                'Content-Type': 'application/json',
            }
            # print("url = ", url)
            # print("params = ", params)
            r = post(url, data=json.dumps(data), params=params, headers=headers, timeout=self.timeout)
            # print("r = ", r)
            logger_request_success.info({
                "func": "call",
                "url": url,
                "data": data,
                "params": params,
                "headers": headers,
                "state": "post_req",
                "result": r.text
            })
            result = json.loads(r.text)
        except ValueError as err:
            logger_request_errors.error({
                "func": "call",
                "error": err,
                "method": method,
                "data": data,
                "text": r.text
            })
            result = dict(error=f'Error on decode api response [{r.text}]')
        except exceptions.ReadTimeout as err:
            logger_request_errors.error({
                "func": "call",
                "error": err,
                "method": method,
                "data": data,
                "text": r
            })
            result = dict(error=f'Timeout waiting expired [{str(self.timeout)} sec]')
        except exceptions.ConnectionError as err:
            logger_request_errors.error({
                "func": "call",
                "error": err,
                "method": method,
                "data": data,
                "text": r
            })
            result = dict(error=f'Max retries exceeded [{str(adapters.DEFAULT_RETRIES)}]')
        except Exception as err:
            logger_request_errors.error({
                "func": "call",
                "error": err,
                "method": method,
                "data": data,
                "text": r
            })

        if 'error' in result and result['error'] in ('NO_AUTH_FOUND', 'expired_token'):
            result_update_token = self.refresh_tokens()
            if result_update_token is not True:
                return result
            result = self.call(method, data)
        elif 'error' in result and result['error'] in ['QUERY_LIMIT_EXCEEDED', ]:
            time.sleep(2)
            return self.call(method, data)

        return result

    def batch(self, cmd):
        if not cmd or not isinstance(cmd, dict):
            logger_request_errors.error({
                "func": "batch",
                "error": "cmd is not dict",
                "cmd": cmd,
            })
            return dict(error='Invalid batch structure')

        response = self.call(
            'batch',
            {
                "halt": 0,
                "cmd": cmd
            }
        )
        logger_request_success.info({
            "func": "batch",
            "cmd": cmd,
            "state": "post_req",
            "result": response
        })
        return response

    # возвращает количество объектов для заданного списочного метода
    def get_count_records(self, method, filters={}):
        data = {}
        if filters:
            data["filter"] = filters

        response = self.call(method, data)
        logger_request_success.info({
            "func": "get_count_records",
            "method": method,
            "filters": filters,
            "data": data,
            "state": "post_req",
            "result": response
        })
        if response and 'total' in response:
            return response['total']

        return 0

    # формирование команд для batch запросов
    @staticmethod
    def forming_long_batch_commands(method, total_contacts, fields=[], filters={}):
        cmd = {}
        for i in range(0, total_contacts, BX24__COUNT_RECORDS_IN_METHODS):
            cmd[f'key_{i}'] = f'{method}?start={i}&'
            cmd[f'key_{i}'] += '&'.join([f'select[]={field}' for field in fields])
            if filters:
                cmd[f'key_{i}'] += '&'
                cmd[f'key_{i}'] += '&'.join([f'FILTER[{key}]={val}' for key, val in filters.items()])

        return cmd

    # разбивка команд на группы по определенной длине
    def split_long_batch_commands(self, commands):
        count = 0
        cmd = {}
        cmd_list = []
        for key in commands:
            count += 1
            cmd[key] = commands[key]
            if count == self.length_batch:
                cmd_list.append(cmd)
                count = 0
                cmd = {}

        if cmd:
            cmd_list.append(cmd)

        return cmd_list

    # объединение результатов запроса
    @staticmethod
    def merge_long_batch_result(keys, data):
        res = []
        for key in keys:
            res.extend(data.get(key, []))

        return res

    def long_batch(self, method):
        result_batch = []
        # всего записей
        total_contacts = self.get_count_records(method)
        # словарь команд для извлечения всех данных
        commands = self.forming_long_batch_commands(method, total_contacts)
        # список команд для выполнения batch запросов
        cmd_list = self.split_long_batch_commands(commands)
        # выполнение запросов
        for cmd in cmd_list:
            response = self.batch(cmd)
            if 'result' not in response or 'result' not in response['result']:
                continue
            result_batch.extend(self.merge_long_batch_result(cmd.keys(), response['result']['result']))

        return result_batch

    def download_file(self, url_path, fileid, recursion=5):
        recursion -= 1
        try:
            url = f'https://{self.domain}{url_path}'
            params = {
                'auth': self.auth_token
            }

            result = http_get(url, params)

        except exceptions.ReadTimeout:
            result = dict(error=f'Timeout waiting expired [{str(self.timeout)} sec]')
        except exceptions.ConnectionError:
            result = dict(error=f'Max retries exceeded [{str(adapters.DEFAULT_RETRIES)}]')

        if 'error' in result or 'X-Bitrix-Ajax-Status' in result.headers:
            result_update_token = self.refresh_tokens()
            if result_update_token is not True:
                return
            if recursion > 0:
                return self.download_file(url_path, fileid, recursion)
        else:
            f_name = self.get_filename(result.headers, fileid)
            f_path = os.path.join(settings.BASE_DIR, 'files', f_name)
            with open(f_path, 'wb') as f:
                f.write(result.content)

            return f_path

    def get_filename(self, headers, fileid):
        data = headers.get('Content-Disposition')

        if data:
            filename = re.search(r'filename="(.+)";', data).group(1)
            return unquote(filename)
        else:
            content_type = headers.get("Content-Type")

            if content_type and extension(content_type):
                filename = fileid + extension(content_type)
                return unquote(filename)
            else:
                return unquote(fileid)

