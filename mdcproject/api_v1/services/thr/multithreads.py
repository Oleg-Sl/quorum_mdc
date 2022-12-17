from threading import Thread, Lock


from ..common import func_fill_db, func_mdc, serch_duplicates


lock = Lock()


class ArrayThreads:
    def __init__(self, input_queue, bx24, count_threads):
        self.bx24 = bx24
        self.input_queue = input_queue
        self.count_threads = count_threads
        self.threads = []

    def send_queue_stop_threads(self):
        [self.input_queue.put(None) for _ in range(self.count_threads)]

    def create(self):
        if not self.threads:
            self.threads = [Thread(target=self.handler) for _ in range(self.count_threads)]

    def start(self):
        [thread.start() for thread in self.threads]

    def join(self):
        [thread.join() for thread in self.threads]

    def handler(self):
        pass


class ThreadsGetContacts(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads):
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            item = self.input_queue.pop()
            if item is None:
                break

            response = self.bx24.batch(item)
            if 'result' not in response or 'result' not in response['result']:
                continue

            # сохранение полученных контактов в БД
            func_fill_db.contacts_create(response['result']['result'], lock)

            self.input_queue.task_done()


class ThreadsGetCompanies(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads):
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            item = self.input_queue.pop()
            if item is None:
                break

            response = self.bx24.batch(item)
            if 'result' not in response or 'result' not in response['result']:
                continue

            # сохранение полученных компаний в БД
            func_fill_db.companies_create(response['result']['result'], lock)

            self.input_queue.task_done()


class ThreadsGetDeals(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads):
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            item = self.input_queue.pop()
            if item is None:
                break

            response = self.bx24.batch(item)
            if 'result' not in response or 'result' not in response['result']:
                continue

            # сохранение полученных компаний в БД
            func_fill_db.deals_create(response['result']['result'], lock)

            self.input_queue.task_done()


class ThreadsGetCompanyBindContact(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads):
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            item = self.input_queue.pop()
            if item is None:
                break

            response = self.bx24.batch(item)

            if 'result' not in response or 'result' not in response['result']:
                continue

            # сохранение связи компания-контакт в БД
            func_fill_db.company_bind_contact(response['result']['result'], lock)

            self.input_queue.task_done()


class ThreadsGetDealBindContact(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads):
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            item = self.input_queue.pop()
            if item is None:
                break

            response = self.bx24.batch(item)

            if 'result' not in response or 'result' not in response['result']:
                continue

            # сохранение связи компания-контакт в БД
            func_fill_db.deal_bind_contact(response['result']['result'], lock)

            self.input_queue.task_done()


class ThreadsMergeContact(ArrayThreads):
    def __init__(self, input_queue, bx24, count_threads, method_merge, report):
        self.method_merge = method_merge
        self.report = report
        super().__init__(input_queue, bx24, count_threads)

    def handler(self):
        while True:
            contact_value = self.input_queue.pop()
            if contact_value is None:
                break

            lock.acquire()
            ids = serch_duplicates.get_id_duplicate_by_str(contact_value, self.method_merge)
            lock.release()

            func_mdc.merge_contacts(ids, lock, self.report)

            self.input_queue.task_done()

