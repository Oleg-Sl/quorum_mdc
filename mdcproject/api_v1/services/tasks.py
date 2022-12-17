import time

from .bx24.requests import Bitrix24
from .report.html import Report
from .parameters import COUNT_THREAD
from api_v1.models import Email, Contacts, Companies, Deals
from .thr.queues import *
from .thr.multithreads import *
from .common import serch_duplicates


bx24 = Bitrix24()


QUEUE_CONTACTS = None
QUEUEU_COMPANIES = None
QUEUE_DEALS = None
QUEUE_COMPANY_CONTACT = None
QUEUE_DEAL_CONTACT = None
QUEUE_DUPLICATES = None


def merge_contacts(method_merge, filters):
    global QUEUE_CONTACTS
    global QUEUEU_COMPANIES
    global QUEUE_DEALS
    global QUEUE_COMPANY_CONTACT
    global QUEUE_DEAL_CONTACT
    global QUEUE_DUPLICATES
    report = Report(bx24.domain)


    # создание отчета
    report.create()

    # Очистка таблиц БД
    clear_database()

    # Список названий полей таблиц БД
    fields_contact = [contact.name for contact in Contacts._meta.get_fields()]
    fields_company = [company.name for company in Companies._meta.get_fields()]
    fields_deal = [deal.name for deal in Deals._meta.get_fields()]

    # Очереди
    QUEUE_CONTACTS = QueueCommands('crm.contact.list', bx24, COUNT_THREAD, filters)
    QUEUEU_COMPANIES = QueueCommands('crm.company.list', bx24, COUNT_THREAD)
    QUEUE_DEALS = QueueCommands('crm.deal.list', bx24, COUNT_THREAD)
    QUEUE_COMPANY_CONTACT = QueueByModels('crm.company.contact.items.get', bx24, COUNT_THREAD)
    QUEUE_DEAL_CONTACT = QueueByModels('crm.deal.contact.items.get', bx24, COUNT_THREAD)
    QUEUE_DUPLICATES = MyQueue(COUNT_THREAD)

    # Создание объектов для конкурентного общения с Битрикс24 по HTTP
    threads_contacts = ThreadsGetContacts(QUEUE_CONTACTS, bx24, COUNT_THREAD)
    threads_companies = ThreadsGetCompanies(QUEUEU_COMPANIES, bx24, COUNT_THREAD)
    threads_deals = ThreadsGetDeals(QUEUE_DEALS, bx24, COUNT_THREAD)
    threads_company_contact = ThreadsGetCompanyBindContact(QUEUE_COMPANY_CONTACT, bx24, COUNT_THREAD)
    threads_deal_contact = ThreadsGetDealBindContact(QUEUE_DEAL_CONTACT, bx24, COUNT_THREAD)
    threads_duplicates = ThreadsMergeContact(QUEUE_DUPLICATES, bx24, COUNT_THREAD, method_merge, report)

    # Создание потоков
    threads_contacts.create()
    threads_companies.create()
    threads_deals.create()
    threads_company_contact.create()
    threads_deal_contact.create()
    threads_duplicates.create()

    # Запуск потоков
    threads_contacts.start()
    threads_companies.start()
    threads_deals.start()
    threads_company_contact.start()
    threads_deal_contact.start()
    threads_duplicates.start()

    # Формирование очереди запросов и ожидание завершения получения данных - КОНТАКТЫ
    QUEUE_CONTACTS.forming(fields_contact)
    threads_contacts.join()


    # Заполнение очереди запросов и ожидание завершения получения данных - КОМПАНИИ
    QUEUEU_COMPANIES.forming(fields_company)
    threads_companies.join()

    # Заполнение очереди запросов и ожидание завершения получения данных - СДЕЛКИ
    QUEUE_DEALS.forming(fields_deal)
    threads_deals.join()

    # Получение данных отношения компания-контакт из Битрикс
    QUEUE_COMPANY_CONTACT.forming(Companies)
    threads_company_contact.join()

    # Получение данных отношения компания-контакт из Битрикс
    QUEUE_DEAL_CONTACT.forming(Deals)
    threads_deal_contact.join()

    # формирование списка дублирующихся значений полей
    duplicates = serch_duplicates.get_duplicate_value(method_merge)
    # print("duplicates = ", duplicates)
    if duplicates:
        # Заполнение очереди дубликатов контактов
        QUEUE_DUPLICATES.set_start_size(len(duplicates))
        [QUEUE_DUPLICATES.send_queue(id_contact) for id_contact in duplicates]

    QUEUE_DUPLICATES.send_queue_stop()

    threads_duplicates.join()

    # закрытие отчета
    report.closed()

    time.sleep(2)

    # Очистка таблиц БД
    clear_database()

    print("END!!!")


def clear_database():
    Email.objects.all().delete()
    Contacts.objects.all().delete()
    Companies.objects.all().delete()


# привязывает к сделке компанию полученную из первого связанного контакта - в Битрикс24
def bind_company_to_deal_associated_with_contact(id_deal):
    response = bx24.batch(
        {
            'deal': f'crm.deal.get?id={id_deal}',
            'contacts': f'crm.deal.contact.items.get?id={id_deal}'
        }
    )

    if 'result' not in response or 'result' not in response['result']:
        return 400, 'Ответ от биртикс не содержит поле "result"'
    if 'deal' not in response['result']['result']:
        return 400, 'Ответ от биртикс не содержит поле "deal"'
    if 'contacts' not in response['result']['result']:
        return 400, 'Ответ от биртикс не содержит поле "contacts"'

    deal = response['result']['result']['deal']
    contacts = response['result']['result']['contacts']
    company_id = deal.get('COMPANY_ID', None)

    if (company_id and company_id != '0') or not contacts:
        return 200, 'В сделке присутствует связанная компания или отсутствуют контакты'

    contact_id = contacts[0].get('CONTACT_ID')

    # Получение данных контакта по его id
    response_contact = bx24.call(
        'crm.contact.get',
        {'id': contact_id}
    )

    if 'result' not in response_contact:
        return 400, 'Ответ на запрос "crm.contact.get" не содержит поле "result"'

    contact = response_contact['result']
    company_id = contact.get('COMPANY_ID', None)

    if not company_id:
        return 200, 'К контакту не привязана компания'

    response_deal_update = bx24.call(
        'crm.deal.update',
        {
            'id': id_deal,
            'fields': {
                'COMPANY_ID': company_id
            }
        }
    )

    return 200, 'Ok'

