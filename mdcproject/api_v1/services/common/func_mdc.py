import logging
from pprint import pprint

from . import merge_fields
from ..parameters import TYPE_MERGE_FIELD, BX24__COUNT_METHODS_IN_BATH, CHAR_CODE_CONTACT
from ..bx24.requests import Bitrix24
from api_v1.models import Email, Contacts, Companies, Deals


logger_report_success = logging.getLogger('report_success')
logger_report_success.setLevel(logging.INFO)
fh_report_success = logging.handlers.TimedRotatingFileHandler('./logs/report_success/success.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_report_success = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_report_success.setFormatter(formatter_report_success)
logger_report_success.addHandler(fh_report_success)

logger_report_errors = logging.getLogger('report_errors')
logger_report_errors.setLevel(logging.INFO)
fh_report_errors = logging.handlers.TimedRotatingFileHandler('./logs/report_errors/errors.log', when='D', interval=1, encoding="cp1251", backupCount=30)
formatter_report_errors = logging.Formatter('[%(asctime)s] %(levelname).1s %(message)s')
fh_report_errors.setFormatter(formatter_report_errors)
logger_report_errors.addHandler(fh_report_errors)


bx24 = Bitrix24()


# объединение контактов с переданным списком идентификаторов
def merge_contacts(ids, lock, report):
    data_old = {}
    data_new = []
    try:
        fields = get_fields_contact()

        # список контактов (возвращает словарь {<id_контакта>: <данные>})
        contacts = get_data_contacts(ids)
        if not contacts or fields is None:
            return None

        # объединение значений полей
        contacts_update = merge_fields.FieldsContactsUpdate(bx24, contacts)

        # ID последнего созданного контакта
        id_contact_last = contacts_update.get_id_max_date()

        # ID компании для добавления в последний созданный контакт (возврашает: [id_company, ])
        companies = contacts_update.get_field_company_non_empty()

        # ID сделок для добавления в последний созданный контакт (возврашает: [id_deal, ...])
        deals = contacts_update.get_field_deal_non_empty()

        data = {}   # {"field_1": "val_1", "field_2": "val_2", ...}
        for field, field_data in fields.items():
            if field_data['isReadOnly'] is True:
                continue
            elif field in TYPE_MERGE_FIELD['max_length']:
                data[field] = contacts_update.get_field_rule_max_length(field)
            elif field in TYPE_MERGE_FIELD['concat_asc_date']:
                data[field] = contacts_update.get_field_rule_concat_asc_date(field)
            elif field in TYPE_MERGE_FIELD['concat_desc_date']:
                data[field] = contacts_update.get_field_rule_concat_desc_date(field)
            elif field_data['type'] == 'crm_multifield':
                field_content = contacts_update.get_field_type_crm_multifield(field)
                if field_content:
                    data[field] = field_content
            elif field_data['type'] == 'file':
                field_content = contacts_update.get_field_type_file(field)
                if field_content:
                    data[field] = field_content
            else:
                field_content = contacts_update.get_field_non_empty(field)
                if field_content:
                    data[field] = field_content

        # обновление контакта (возвращает: True, False)
        res_update_contact = update_data_contacts(id_contact_last, data)

        # Копирование комментариев {id_contact: ["comment_1", "comment_2", ...], ...}
        comments = contact__copy_comments(id_contact_last, ids)

        # Копирование дел {id_contact: [id_activity_1, id_activity_2, ...], ...}
        activities = contact__copy_activities(id_contact_last, ids)
        activities_calls = contact__copy_calls(id_contact_last, ids)

        # Привязка задач {id_contact: [id_task_1, id_task_2, ...], ...}
        tasks = change_task_binding(id_contact_last, ids, CHAR_CODE_CONTACT)

        # добавление компаний к контакту
        res_add_companies = add_companies_to_contact(id_contact_last, companies)

        # удаление дубликатов контактов
        del_companies_to_contact(ids, id_contact_last)

        # добавление сделок к контакту
        res_add_deals = add_deals_to_contact(id_contact_last, deals)

        # # получение списка сделок по контактам
        # deals_obj = get_dealid_by_contacts(id_contact_last, ids, deals)

        # Подготоака данных для отчета
        data_old, data_new = preparing_data_for_report(
            id_contact_last, ids, fields, contacts, comments, activities, tasks, activities_calls
        )

        logger_report_success.info({
            "id_contact_last": id_contact_last,
            "ids": ids,
            "data": data_old,
            "result_update": data_new
        })

        fields["contact_comments"] = {"title": "Комментарии"}
        fields["contact_activities"] = {"title": "Связанные дела"}
        fields["contact_tasks"] = {"title": "Связанные задачи"}
        fields["contact_deals"] = {"title": "Связанные сделки"}
        fields["contact_companies"] = {"title": "Связанные компани"}

        # добавление данных в отчет
        lock.acquire()
        report.add_fields(fields)
        report.add_records(data_old, data_new)
        # report.add_fields(fields)
        # report.add(contacts, id_contact_last, data, companies, deals_obj, coments, activities, tasks)
        lock.release()

    except Exception as err:
        logger_report_success.info({
            "id_contact_last": id_contact_last,
            "ids": ids,
            "error": err,
            "data": data_old,
            "result_update": data_new
        })


def preparing_data_for_report(id_contact_last, ids, fields, contacts, comments, activities, tasks, activities_calls):
    """
    :param id_contact_last:
    :param ids:             - [id_contacts, ...]
    :param fields:          - {field_1: {type: val, ...}, ...}
    :param contacts:        - {id_контакта: {field_1: val_1, field_2: val_2, ...}, ...}
    :param comments:        - {id_contact: ["comment_1", "comment_2", ...], ...}
    :param activities:      - {id_contact: [id_activity_1, id_activity_2, ...], ...}
    :param tasks:           - {id_contact: [id_task_1, id_task_2, ...], ...}
    :return:                - ({id_контакта: {field_1: val_1, field_2: val_2, ...}, ...}, {{field_1: val_1, field_2: val_2, ...}})
    """
    data = {}
    summary = {
        "contact_comments": [],
        "contact_activities": [],
        "contact_activities_calls_": [],
        "contact_tasks": [],
        "contact_deals": [],
        "contact_companies": [],
    }
    contacts_new = get_data_contacts([id_contact_last, ])
    if contacts_new and id_contact_last in contacts_new:
        contact_res = contacts_new.get(str(id_contact_last))
        for field_name, field_desc in fields.items():
            if field_desc["type"] == "crm_multifield":
                summary[field_name] = [item['VALUE'] for item in contact_res.get(field_name, []) if item.get('VALUE')]
            elif isinstance(contact_res.get(field_name), list):
                summary[field_name] = [item for item in contact_res.get(field_name, []) if item]
            else:
                summary[field_name] = contact_res.get(field_name)

    for id_cont in sorted(ids, key=int, reverse=True):
        deals_contact = Deals.objects.filter(contacts=id_cont).values_list("ID", flat=True)
        companies_contact = Companies.objects.filter(contacts=id_cont).values_list("ID", flat=True)
        comments_ = comments.get(str(id_cont), [])
        activities_ = activities.get(str(id_cont), [])
        activities_calls_ = activities_calls.get(str(id_cont), [])
        tasks_ = tasks.get(str(id_cont), [])
        contact_ = contacts.get(str(id_cont), [])
        data_contact = {
            "contact_comments": comments_,
            "contact_activities": activities_,
            "contact_activities_calls_": activities_calls_,
            "contact_tasks": tasks_,
            "contact_deals": list(deals_contact),
            "contact_companies": list(companies_contact),
        }

        summary["contact_comments"].extend(comments_)
        summary["contact_activities"].extend(activities_)
        summary["contact_activities_calls_"].extend(activities_calls_)
        summary["contact_tasks"].extend(tasks_)
        summary["contact_deals"].extend(list(deals_contact))
        summary["contact_companies"].extend(list(companies_contact))

        for field_name, field_desc in fields.items():
            if field_desc["type"] == "crm_multifield":
                data_contact[field_name] = [item['VALUE'] for item in contact_.get(field_name, []) if item.get('VALUE')]
            elif isinstance(contact_.get(field_name), list):
                data_contact[field_name] = [item for item in contact_.get(field_name, []) if item]
            else:
                data_contact[field_name] = contact_.get(field_name)

        data[id_cont] = data_contact

    return data, summary


def get_dealid_by_contacts(id_contact_last, ids_contacts, deals):
    deals_obj = {}
    deals_contact_last = Deals.objects.filter(contacts=id_contact_last).values_list("ID", flat=True)
    deals_obj["summary"] = deals + list(deals_contact_last)

    for id_contact in ids_contacts:
        deals_contact = Deals.objects.filter(contacts=id_contact).values_list("ID", flat=True)
        deals_obj[str(id_contact)] = list(deals_contact)

    return deals_obj


# удаление контактов
def del_companies_to_contact(ids_contacts, id_contact_last):
    for id_contact in ids_contacts:
        if int(id_contact) in [id_contact_last, int(id_contact_last)]:
            continue

        res_del = bx24.call(
            'crm.contact.delete',
            {'id': id_contact}
        )


# добавляет компании к контакту
def add_companies_to_contact(id_contact, companies):
    if not companies:
        return True

    response = bx24.call(
        'crm.contact.company.items.set',
        {
            'id': id_contact,
            'items': [{'COMPANY_ID': company_id} for company_id in companies]
        }
    )

    if 'result' not in response:
        return

    return response['result']


# добавляет контакта к сделке
def add_deals_to_contact(id_contact, deals):
    if not deals:
        return True

    batch = {}
    for deal_id in deals:
        batch[deal_id] = f'crm.deal.contact.add?id={deal_id}&fields[CONTACT_ID]={id_contact}'

    response = bx24.batch(batch)
    if response and 'result' in response and 'result' in response['result']:
        return response['result']['result']


# обновляет данные контакта
def update_data_contacts(id_contact, data):
    response = bx24.call(
        'crm.contact.update',
        {
            'id': id_contact,
            'fields': {
                **data,
            },
            'params': {"REGISTER_SONET_EVENT": "Y"}
        }
    )

    if 'result' not in response:
        return

    return response['result']


# запрашивает данные контактов по id
def get_data_contacts(ids):
    cmd = {}
    for id_contact in ids:
        cmd[id_contact] = f'crm.contact.get?id={id_contact}'

    response = bx24.batch(cmd)

    if 'result' not in response or 'result' not in response['result']:
        return None

    return response['result']['result']


# запрашивает и возвращает список всех полей контакта
def get_fields_contact():
    response_fields = bx24.call('crm.contact.fields', {})
    if 'result' not in response_fields:
        return None

    return response_fields['result']


def contact__copy_comments(origin_contact, contacts):
    cmd = {}
    method_timeline_comment = "crm.timeline.comment.list?filter[ENTITY_TYPE]=contact&filter[ENTITY_ID]={contact}"
    for ind, contact in enumerate(contacts):
        if contact == origin_contact or str(contact) == str(origin_contact):
            continue
        cmd[contact] = method_timeline_comment.format(contact=contact)

    response = bx24.batch(cmd)
    if "result" not in response or "result" not in response["result"] or "result_total" not in response["result"]:
        return

    contacts_comments = response["result"]["result"]
    contacts_total = response["result"]["result_total"]
    contacts_next = response["result"]["result_next"]

    if contacts_next and contacts_total:
        cmd = {}
        for contact, start in contacts_next.items():
            count_records = 50
            count = contacts_total[contact]
            for i in range(count // count_records):
                method = method_timeline_comment.format(contact=contact)
                method += f"&start={start + i * count_records}"
                cmd[f"{contact}_{i}"] = method

        i = 1
        cmd_list = []
        cmd_block = {}
        for key, val in cmd.items():
            if i > BX24__COUNT_METHODS_IN_BATH:
                cmd_list.append(cmd_block)
                cmd_block = {}
                i = 1
            cmd_block[key] = val
            i += 1
        else:
            if cmd_block:
                cmd_list.append(cmd_block)

        for cmd in cmd_list:
            response = bx24.batch(cmd)
            if "result" not in response or "result" not in response["result"]:
                return
            for key, val in response["result"]["result"].items():
                contact, _ = key.split("_")
                contacts_comments[contact].extend(val)

    # comments_list = [{'ID': 21, 'ENTITY_ID': 223, 'ENTITY_TYPE': 'contact', 'CREATED': '2022-12-08', 'COMMENT': 'dsa', 'AUTHOR_ID': '9'}, ...]
    comments_list = [comment for contact, comments in contacts_comments.items() for comment in comments]

    comment_obj = {}
    for contact, comments in contacts_comments.items():
        lst = []
        for comment in comments:
            lst.append(comment.get("COMMENT", "-"))
        comment_obj[contact] = lst

    cmd = {}
    method_timeline_comment_add = "crm.timeline.comment.add?fields[AUTHOR_ID]={AUTHOR_ID}&" \
                                  "fields[COMMENT]={COMMENT}&" \
                                  "fields[CREATED]={CREATED}&" \
                                  "fields[ENTITY_ID]={ENTITY_ID}&" \
                                  "fields[ENTITY_TYPE]={ENTITY_TYPE}"
    for comment in comments_list:
        key = comment["ID"]
        comment["ENTITY_ID"] = origin_contact
        cmd[key] = method_timeline_comment_add.format(**comment)

    i = 1
    cmd_list = []
    cmd_block = {}
    for key, val in cmd.items():
        if i > BX24__COUNT_METHODS_IN_BATH:
            cmd_list.append(cmd_block)
            cmd_block = {}
            i = 1
        cmd_block[key] = val
        i += 1
    else:
        if cmd_block:
            cmd_list.append(cmd_block)

    for cmd in cmd_list:
        response = bx24.batch(cmd)
        if "result" not in response or "result" not in response["result"]:
            return

    return comment_obj


def contact__copy_calls(origin_contact, contacts):
    # ПОЛУЧЕНИЕ ВСЕХ ЗВОНКОВ СВЯЗАННЫХ С ДУБЛИКАТАМИ КОНТАКОВ
    cmd = {}
    method_calls_list = "voximplant.statistic.get?FILTER[CRM_ENTITY_TYPE]=CONTACT&FILTER[CRM_ENTITY_ID]={contact}"
    for ind, contact in enumerate(contacts):
        if contact == origin_contact or str(contact) == str(origin_contact):
            continue
        cmd[contact] = method_calls_list.format(contact=contact)

    response = bx24.batch(cmd)
    if "result" not in response or "result" not in response["result"]:
        return

    calls = []
    for contact_id, calls_ in response["result"]["result"].items():
        calls.extend(calls_)

    activities_obj = {}
    activities = []
    for call_ in calls:
        if call_.get("CRM_ENTITY_TYPE") == "CONTACT" and call_.get("CRM_ACTIVITY_ID"):
            activities.append(call_["CRM_ACTIVITY_ID"])
            contact_id_ = call_.get("CRM_ENTITY_ID", "")
            if not activities_obj[contact_id_]:
                activities_obj[contact_id_] = [call_.get("CRM_ACTIVITY_ID", "-"), ]
            else:
                activities_obj[contact_id_].append(call_.get("CRM_ACTIVITY_ID", "-"))
            # activities_obj[call_.get("CRM_ENTITY_ID", "")]

    binding_activities_at_contact(origin_contact, activities)

    return activities_obj


def contact__copy_activities(origin_contact, contacts):
    # ПОЛУЧЕНИЕ ВСЕХ АКТИВНОСТЕЙ СВЯЗАННЫХ С ДУБЛИКАТАМИ КОНТАКОВ
    cmd = {}
    method_activity_list = "crm.activity.list?filter[OWNER_TYPE_ID]=3&filter[OWNER_ID]={contact}&select[]=ID"
    for ind, contact in enumerate(contacts):
        if contact == origin_contact or str(contact) == str(origin_contact):
            continue
        cmd[contact] = method_activity_list.format(contact=contact)

    response = bx24.batch(cmd)
    if "result" not in response or "result" not in response["result"] or "result_total" not in response["result"]:
        return

    activities = response["result"]["result"]
    totals = response["result"]["result_total"]
    nexts = response["result"]["result_next"]

    if nexts and totals:
        cmd = {}
        for contact, start in nexts.items():
            count_records = 50
            count = totals[contact]
            for i in range(count // count_records):
                method = method_activity_list.format(contact=contact)
                method += f"&start={start + i * count_records}"
                cmd[f"{contact}_{i}"] = method

        i = 1
        cmd_list = []
        cmd_block = {}
        for key, val in cmd.items():
            if i > BX24__COUNT_METHODS_IN_BATH:
                cmd_list.append(cmd_block)
                cmd_block = {}
                i = 1
            cmd_block[key] = val
            i += 1
        else:
            if cmd_block:
                cmd_list.append(cmd_block)

        for cmd in cmd_list:
            response = bx24.batch(cmd)
            if "result" not in response or "result" not in response["result"]:
                return
            for key, val in response["result"]["result"].items():
                contact, _ = key.split("_")
                activities[contact].extend(val)

    activities_list = [activity_ for contact_, activities_ in activities.items() for activity_ in activities_]

    activities_obj = {}
    for contact, activities_ in activities.items():
        lst = []
        for activity_ in activities_:
            lst.append(activity_.get("ID", "-"))
        activities_obj[contact] = lst

    binding_activities_at_contact(origin_contact, [activity["ID"] for activity in activities_list])

    return activities_obj


def binding_activities_at_contact(origin_contact, activities):
    # ПРИВЯЗКА ОРИГИНАЛЬНОГО КОНТАКТА К АКТИВНОСТЯМ СВЯЗАННЫХ С ДУБЛИКАТОМ КОНТАКТА
    cmd = {}
    method_activity_add = "crm.activity.binding.add?activityId={activity}&" \
                          "entityTypeId=3&" \
                          "entityId={origin_contact}"
    for activity in activities:
        # key = activity["ID"]
        key = activity
        cmd[key] = method_activity_add.format(activity=activity, origin_contact=origin_contact)

    i = 1
    cmd_list = []
    cmd_block = {}
    for key, val in cmd.items():
        if i > BX24__COUNT_METHODS_IN_BATH:
            cmd_list.append(cmd_block)
            cmd_block = {}
            i = 1
        cmd_block[key] = val
        i += 1
    else:
        if cmd_block:
            cmd_list.append(cmd_block)

    for cmd in cmd_list:
        response = bx24.batch(cmd)
        if "result" not in response or "result" not in response["result"]:
            return


def change_task_binding(origin_contact, contacts, crm_type):
    cmd = {}
    method_contact_list = "tasks.task.list?filter[UF_CRM_TASK]={crm_type}_{contact}&select[]=UF_CRM_TASK"
    for ind, contact in enumerate(contacts):
        if contact == origin_contact or str(contact) == str(origin_contact):
            continue
        cmd[contact] = method_contact_list.format(crm_type=crm_type, contact=contact)

    response = bx24.batch(cmd)
    if "result" not in response or "result" not in response["result"] or "result_total" not in response["result"]:
        return

    tasks = response["result"]["result"]
    totals = response["result"]["result_total"]
    nexts = response["result"]["result_next"]

    if nexts and totals:
        cmd = {}
        for contact, start in nexts.items():
            count_records = 50
            count = totals[contact]
            for i in range(count // count_records):
                method = method_contact_list.format(contact=contact)
                method += f"&start={start + i * count_records}"
                cmd[f"{contact}_{i}"] = method

        i = 1
        cmd_list = []
        cmd_block = {}
        for key, val in cmd.items():
            if i > BX24__COUNT_METHODS_IN_BATH:
                cmd_list.append(cmd_block)
                cmd_block = {}
                i = 1
            cmd_block[key] = val
            i += 1
        else:
            if cmd_block:
                cmd_list.append(cmd_block)

        for cmd in cmd_list:
            response = bx24.batch(cmd)
            if "result" not in response or "result" not in response["result"]:
                return
            for key, val in response["result"]["result"].items():
                contact, _ = key.split("_")
                tasks[contact].extend(val)

    tasks_list = [task_ for contact, tasks_ in tasks.items() for task_ in tasks_["tasks"]]

    tasks_obj = {}
    for contact, tasks_ in tasks.items():
        lst = []
        for task_ in tasks_.get("tasks", {}):
            lst.append(task_.get("id", "-"))
        tasks_obj[contact] = lst

    cmd = {}
    method_tak_update = "tasks.task.update?taskId={task_id}&" \
                        "fields[UF_CRM_TASK][]={crm_type}_{contact}"

    for task in tasks_list:
        method = method_tak_update.format(task_id=task["id"], crm_type=crm_type, contact=origin_contact)
        for crm_ in task["ufCrmTask"]:
            method += f"&fields[UF_CRM_TASK][]={crm_}"
        key = task["id"]
        cmd[key] = method

    i = 1
    cmd_list = []
    cmd_block = {}
    for key, val in cmd.items():
        if i > BX24__COUNT_METHODS_IN_BATH:
            cmd_list.append(cmd_block)
            cmd_block = {}
            i = 1
        cmd_block[key] = val
        i += 1
    else:
        if cmd_block:
            cmd_list.append(cmd_block)

    for cmd in cmd_list:
        response = bx24.batch(cmd)
        if "result" not in response or "result" not in response["result"]:
            return

    return tasks_obj
