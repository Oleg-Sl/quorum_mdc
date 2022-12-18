import os
import datetime
from django.conf import settings

date = datetime.datetime.now()
filename_secrets_bx24 = os.path.join(settings.BASE_DIR, 'reports', 'report.txt')


class Report:
    api_task = 'https://{domain}/company/personal/user/0/tasks/task/view/{id_task}/'
    api_deal = 'https://{domain}/crm/deal/details/{id_deal}/'
    api_contact = 'https://{domain}/crm/contact/details/{id_contact}/'
    api_company = 'https://{domain}/crm/company/details/{id_company}/'

    def __init__(self, domain):
        self.domain = domain
        self.date = None
        self.filename = None
        self.fields = None
        self.encoding = 'utf8'

    def create(self):
        self.set_date()
        self.forming_filename()
        with open(self.filename, 'a+', encoding=self.encoding) as f:
            html_tags = \
                """
                <!DOCTYPE html>
                <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <meta http-equiv="X-UA-Compatible" content="IE=edge">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            table {border-collapse: collapse;}
                            th {
                                border: 2px solid #dee2e6;
                                padding: 6px;
                                text-align: "center";
                                font-size: 14px;
                                font-family: sans-serif;
                                color: rgb(33, 37, 41);
                                max-width: 300px;
                                overflow: auto;
                                white-space: nowrap;
                            }
                            td {
                                border: 2px solid #dee2e6;
                                font-size: 12px;
                                font-weight: 400;
                                font-family: sans-serif;
                                white-space: nowrap;
                                color: rgb(33, 37, 41);
                                padding: 2px 5px;
                                max-width: 300px;
                                overflow: auto;
                            }
                            .result td {
                                background-color: #cfe2ff;
                                border-bottom: 4px solid #74b0ec;
                            }
                            .table_cell {
                                max-width: 75px;
                                overflow: auto;
                            }
                        </style>
                        <!-- <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-iYQeCzEYFbKjA/T2uDLTpkwGzCiq6soy8tYaI1GyVh/UjpbCx/TYkiZhlZB6+fzT" crossorigin="anonymous"> -->
                        <title>Отчет</title>
                    </head>
                    <body>
                        <h1>Результат объединения контактов от 
                """
            html_tags += self.date.isoformat()
            html_tags += """
                </h1>
                <table class="table">
            """
            f.write(html_tags)

    def add_fields(self, fields):
        self.fields = fields
        html = '<th>ID</th>\n'
        for field, desc in self.fields.items():
            if field != 'ID':
                html += f'<th>{desc.get("title", field)}</th>\n'

        with open(self.filename, 'a', encoding=self.encoding) as f:
            f.write(f'''
                <thead>
                    <tr>
                        {html}
                    </tr>
                </thead>
            ''')

    def add_records(self, data_old, data_new):
        try:
            html = ''
            for id_contact, data in data_old.items():
                html += f'''
                    <tr>
                        {self.add_record(data)}
                    </tr>
                '''
            html += f'''
                <tr class="result">
                    {self.add_record(data_new)}
                </tr>
            '''
            with open(self.filename, 'a', encoding=self.encoding) as f:
                f.write(f'''
                    <tbody>
                        {html}
                    </tbody>
                ''')
        except Exception as err:
            print("err = ", err)

    def add_record(self, data):
        try:
            id_contact = data.get("ID", "")
            html = f'''
                <td>
                    <div class="table_cell">
                        <a href="{self.api_contact.format(domain=self.domain, id_contact=id_contact)}">{id_contact}</a>
                    </div>
                </td>\n
            '''

            for field in self.fields:
                value = data.get(field, "")
                if field == 'ID':
                    continue
                elif field == 'contact_companies':
                    links = [f'<a href="{self.api_company.format(domain=self.domain, id_company=id_)}">{id_}</a>' for id_ in value if id_]
                    html += f'<td><div class="table_cell">{",<br>".join(links)}</div></td>\n'
                elif field == 'contact_deals':
                    links = [f'<a href="{self.api_deal.format(domain=self.domain, id_deal=id_)}">{id_}</a>' for id_ in value if id_]
                    html += f'<td><div class="table_cell">{",<br>".join(links)}</div></td>\n'
                elif field == 'contact_tasks':
                    links = [f'<a href="{self.api_task.format(domain=self.domain, id_task=id_)}">{id_}</a>' for id_ in value if id_]
                    html += f'<td><div class="table_cell">{",<br>".join(links)}</div></td>\n'
                elif isinstance(value, list):
                    html += f'<td><div class="table_cell">{",<br>".join(value)}</div></td>\n'
                else:
                    html += f'<td><div class="table_cell">{value or "&ndash;"}</div></td>\n'
            return html
        except Exception as err:
            print("err = ", err)

    def add(self, old_contacts, id_contact_res, data_update, companies, deals={}):
        with open(self.filename, 'a', encoding=self.encoding) as f:
            html = ''
            for _, contact in old_contacts.items():
                html += f'''
                    <tr>
                        {self.get_row_html(contact, deals)}
                    </tr>
                '''

            res_contact = old_contacts.get(id_contact_res, {})
            html += f"""
                <tr class="result">
                    {self.get_row_res_html(res_contact, data_update, companies, deals)}
                </tr>
            """
            f.write(f'''
                <tbody>
                    {html}
                </tbody>
            ''')

    def get_row_html(self, contact, deals):
        id_contact = contact.get("ID", "")
        html_row = f'<td>{contact.get("ID", "")}</td>\n'
        for field, field_data in self.fields.items():
            if field == 'ID':
                continue
            elif field_data['type'] == 'crm_multifield':
                cell = ''
                for item in contact.get(field, []):
                    cell += item.get('VALUE', '') or "&ndash;"
                    cell += '<br>'
                html_row += f'<td>{cell}</td>\n'
            else:
                html_row += f'<td>{contact.get(field, "") or "&ndash;"}</td>\n'

        deals_lst = deals.get(str(id_contact), [])
        html_row += f'<td>{", ".join([str(i) for i in deals_lst])}</td>\n'
        return html_row

    def get_row_res_html(self, contact, data_update, companies, deals):
        html_row = f'<td>{contact.get("ID", "")}</td>\n'
        for field, field_data in self.fields.items():
            if field == 'ID':
                continue
            elif field == 'COMPANY_ID' and not data_update.get(field, None) and companies:
                html_row += f'<td>{companies[0]}</td>\n'
            elif field in data_update and field_data['type'] == 'crm_multifield':
                cell = ''
                for item in data_update.get(field, []):
                    cell += item.get('VALUE', '') or "&ndash;"
                    cell += '<br>'
                html_row += f'<td>{cell}</td>\n'
            elif field in data_update:
                html_row += f'<td>{data_update.get(field, "")  or "&ndash;"}</td>\n'
            elif field_data['type'] == 'crm_multifield':
                cell = ''
                for item in contact.get(field, []):
                    cell += item.get('VALUE', '') or "&ndash;"
                    cell += '<br>'
                html_row += f'<td>{cell}</td>\n'
            else:
                html_row += f'<td>{contact.get(field, "") or "&ndash;"}</td>\n'

        deals_lst = deals.get("summary", [])
        html_row += f'<td>{", ".join([str(i) for i in deals_lst])}</td>\n'
        return html_row

    def closed(self):
        with open(self.filename, 'a', encoding=self.encoding) as f:
            html_tags = \
                """ 
                         </table>
                        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-u1OknCvxWvY5kfmNBILK2hRnQC3Pr17a+RTT6rIHI7NnikvbZlHgTPOOmMi466C8" crossorigin="anonymous"></script>
                    </body>
                </html>
                """
            f.write(html_tags)

    def forming_filename(self):
        date_str = self.convert_date_to_str(self.date)
        self.filename = os.path.join(settings.BASE_DIR, 'reports', f'report_{date_str}.html')

    def set_date(self):
        self.date = datetime.datetime.now()

    @staticmethod
    def convert_date_to_str(date):
        return date.strftime("%d.%m.%Y_%H.%M")



