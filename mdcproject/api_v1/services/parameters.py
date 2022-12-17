# Переменные запросов Битрикс24
BX24__COUNT_RECORDS_IN_METHODS = 50      # должно быть 50
BX24__COUNT_METHODS_IN_BATH = 10

# Символьный код контакта в Битрикс24
CHAR_CODE_CONTACT = 'C'

# Количество параллельных потоков для обращения к Битрикс
COUNT_THREAD = 3

# способы поиска дубликатов
DUPLICATES_FIELDS = {
    'email_company': ['EMAIL__VALUE', 'companies__TITLE'],
    'email_contact_name': ['EMAIL__VALUE', 'NAME'],
}

# способы объединения полей контактов
TYPE_MERGE_FIELD = {
    'max_length': ['NAME', ],
    'concat_asc_date': ['SOURCE_DESCRIPTION', 'UF_CRM_1631872191', 'UF_CRM_1637317264', ],
    'concat_desc_date': ['UF_CRM_1631872766', ],
}