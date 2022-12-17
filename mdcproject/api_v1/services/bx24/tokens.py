import os
import json
from json.decoder import JSONDecodeError
from django.conf import settings


filename_secrets_bx24 = os.path.join(settings.BASE_DIR, 'secrets_bx24.json')


""" Сохранение токенов доступа BX24 """
def create_secrets_bx24(data):
    with open(filename_secrets_bx24, "w+") as secrets_file:
        # try:
        #     data = json.load(secrets_file)
        # except JSONDecodeError:
        #     data = {}

        # data["domain"] = data_new.get("domain")
        # data["client_endpoint"] = data_new.get("client_endpoint", "")
        # data["auth_token"] = data_new.get("auth_token", "")
        # data["refresh_token"] = data_new.get("refresh_token", "")
        # data["application_token"] = data_new.get("application_token", "")
        # data["expires_in"] = data_new.get("expires_in", "")
        json.dump(data, secrets_file)


""" Обновление токенов доступа BX24 """
def update_secrets_bx24(auth_token, expires_in, refresh_token):
    with open(filename_secrets_bx24) as secrets_file:
        try:
            data = json.load(secrets_file)
        except JSONDecodeError:
            data = {}

    data["auth_token"] = auth_token
    data["expires_in"] = expires_in
    data["refresh_token"] = refresh_token

    with open(filename_secrets_bx24, 'w') as secrets_file:
        json.dump(data, secrets_file)


""" Получение значения секрета BX24 по ключу """
def get_secret_bx24(key):
    with open(filename_secrets_bx24, "w+") as secrets_file:
        try:
            data = json.load(secrets_file)
        except JSONDecodeError:
            data = {}
        return data.get(key)


""" Получение всех секретов BX24 """
def get_secrets_all_bx24():
    with open(filename_secrets_bx24, "w+") as secrets_file:
        try:
            data = json.load(secrets_file)
        except JSONDecodeError:
            data = {}

    return data

