from ..bx24.requests import Bitrix24
from api_v1.models import Email, Contacts, Companies, Deals


bx24 = Bitrix24()


# добавление контакта в БД
def contacts_create(res_from_bx, lock):
    for _, contacts in res_from_bx.items():
        for contact in contacts:
            emails = []
            if "EMAIL" in contact:
                emails = contact.pop("EMAIL")

            # замена пустых значений на None
            contact = replace_empty_value_with_none__in_dict(contact)

            lock.acquire()
            contact_item, created = Contacts.objects.update_or_create(**contact)
            lock.release()

            if emails:
                lock.acquire()
                email_create(emails, contact_item)
                lock.release()


# добавление EMAIL в БД
def email_create(emails, contact):
    for email in emails:
        Email.objects.update_or_create(VALUE=email['VALUE'], VALUE_TYPE=email['VALUE_TYPE'], contacts=contact)


# добавление компаний в БД
def companies_create(res_from_bx, lock):
    for _, companies in res_from_bx.items():
        for company in companies:
            lock.acquire()
            company_item, created = Companies.objects.update_or_create(**company)
            lock.release()


# добавление сделок в БД
def deals_create(res_from_bx, lock):
    for _, deals in res_from_bx.items():
        for deal in deals:
            lock.acquire()
            deal_item, created = Deals.objects.update_or_create(**deal)
            lock.release()


# связывание записей таблиц контактов и компаний в БД
def company_bind_contact(res_from_bx, lock):
    for id_company, contacts in res_from_bx.items():
        for contact in contacts:
            lock.acquire()
            company_obj = Companies.objects.filter(ID=id_company).first()
            contact_obj = Contacts.objects.filter(ID=contact['CONTACT_ID']).first()
            if company_obj and contact_obj:
                res = company_obj.contacts.add(contact_obj)
            lock.release()


# связывание записей таблиц контактов и сделок в БД
def deal_bind_contact(res_from_bx, lock):
    for id_deal, contacts in res_from_bx.items():
        for contact in contacts:
            lock.acquire()
            deal_obj = Deals.objects.filter(ID=id_deal).first()
            contact_obj = Contacts.objects.filter(ID=contact['CONTACT_ID']).first()
            if deal_obj and contact_obj:
                res = deal_obj.contacts.add(contact_obj)
            lock.release()


# замена пустых значений в словаре на None
def replace_empty_value_with_none__in_dict(d):
    for key in d:
        if not d[key]:
            d[key] = None

    return d

