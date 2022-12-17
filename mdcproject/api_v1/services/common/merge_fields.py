import os
import re
import base64
from datetime import datetime


from api_v1.models import Email, Contacts, Companies, Deals


class FieldsContactsDealNonEmptyAscDate:
    def get_field_deal_non_empty(self):
        deals_new = []
        for id_contact in self.ids_sort_date[::-1]:
            deals = Deals.objects.filter(contacts=id_contact).values_list("ID", flat=True)
            if deals:
                deals_new.extend(list(deals))

        return deals_new


class FieldsContactsCompanyNonEmptyAscDate:
    # возвращает компанию из наиболее свежего контакта, если ее нет в новом контакте
    def get_field_company_non_empty(self):
        companies = Companies.objects.filter(contacts=self.ids_sort_date[-1]).values_list("ID", flat=True)
        if companies:
            return []
        for id_contact in self.ids_sort_date[::-1]:
            companies = Companies.objects.filter(contacts=id_contact).values_list("ID", flat=True)
            if companies:
                return list(companies)
        return []


class FieldsContactsFirstNonEmptyAscDate:
    def get_field_non_empty(self, field):
        if self.contacts[self.ids_sort_date[-1]].get(field):
            return

        for id_contact in self.ids_sort_date[::-1]:
            value = self.contacts[id_contact].get(field)
            if value:
                return value


class FieldsContactsRuleConcatDescDate:
    def get_field_rule_concat_desc_date(self, field):
        values = []

        for id_contact in self.ids_sort_date[::-1]:
            field_value = self.contacts[id_contact].get(field, '')
            if not field_value:
                continue

            for el in re.split(',|;', field_value):
                elem = el.strip()
                if elem and elem not in values:
                    values.append(elem)

        return ', '.join(values)


class FieldsContactsRuleConcatAscDate:
    def get_field_rule_concat_asc_date(self, field):
        values = []

        for id_contact in self.ids_sort_date:
            field_value = self.contacts[id_contact].get(field, '')
            if not field_value:
                continue
            for el in re.split(',|;', field_value):
                elem = el.strip()
                if elem and elem not in values:
                    values.append(elem)

        return ', '.join(values)


class FieldsContactsRuleMaxLength:
    def get_field_rule_max_length(self, field):
        value = ''
        for id_contact, contact in self.contacts.items():
            if not contact.get(field):
                continue
            if len(contact[field]) > len(value):
                value = contact[field]

        return value


class FieldsContactsTypeCrmMultifield:
    def get_field_type_crm_multifield(self, field):
        multifield = []

        for id_contact, contact in self.contacts.items():
            if not contact.get(field):
                continue

            for item in contact[field]:
                if item['VALUE'] not in [d['VALUE'] for d in multifield]:
                    multifield.append({
                        'TYPE_ID': item['TYPE_ID'],
                        'VALUE': item['VALUE'],
                        'VALUE_TYPE': item['VALUE_TYPE']
                    })

        return multifield


class FieldsContactsTypeFile:
    def get_field_type_file(self, field):
        field_value = self.contacts[self.id_last_created].get(field)

        if field_value:
            return

        for id_cont in self.ids_sort_date[::-1]:
            field_value = self.contacts[id_cont].get(field)
            if not field_value:
                continue
            if isinstance(field_value, list):
                return self.get_files(field_value)
            else:
                return self.get_file(field_value)

    def get_files(self, files_items):
        data = []
        for file_item in files_items:
            row_add_file = self.get_file(file_item)
            data.append(row_add_file)

        return data

    def get_file(self, file_item):
        f_name = f'file_{file_item["id"]}'
        f_url = file_item['downloadUrl']
        f_path = self.bx24.download_file(f_url, file_item["id"])
        return {
            "fileData": [
                os.path.split(f_path)[1],
                self.file_to_base64(f_path)
            ]
        }

    @staticmethod
    def file_to_base64(f_path):
        encoded_string = None
        print(f'{f_path=}')
        with open(f_path, "rb") as f:
            encoded_string = base64.b64encode(f.read())

        return encoded_string.decode("ascii")


class FieldsContactsUpdate(FieldsContactsRuleConcatDescDate,
                           FieldsContactsRuleConcatAscDate,
                           FieldsContactsRuleMaxLength,
                           FieldsContactsTypeCrmMultifield,
                           FieldsContactsTypeFile,
                           FieldsContactsFirstNonEmptyAscDate,
                           FieldsContactsCompanyNonEmptyAscDate,
                           FieldsContactsDealNonEmptyAscDate):
    def __init__(self, bx24, contacts):
        self.bx24 = bx24
        self.contacts = contacts
        self.date_format = '%Y-%m-%dT%H:%M:%S%z'
        self.ids_sort_date = None
        self.id_last_created = None

        self.sort_id_by_date()

    def sort_id_by_date(self):
        id_date_list = []
        for id_contact, contact in self.contacts.items():
            date = datetime.strptime(contact['DATE_CREATE'], self.date_format)
            id_date_list.append((id_contact, date))

        id_date_list.sort(key=lambda item: item[1])
        self.ids_sort_date = [id_date[0] for id_date in id_date_list]
        self.id_last_created = self.ids_sort_date[-1]

    def get_id_max_date(self):
        date_create = {}
        for id_contact, contact in self.contacts.items():
            date_create[id_contact] = datetime.strptime(contact['DATE_CREATE'], '%Y-%m-%dT%H:%M:%S%z')

        return max(date_create, key=date_create.get)

