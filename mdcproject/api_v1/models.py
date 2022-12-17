from django.db import models


class Contacts(models.Model):
    ID = models.PositiveIntegerField(primary_key=True, verbose_name='Идентификатор контакта', unique=True, db_index=True)
    NAME = models.CharField(verbose_name="Имя", max_length=100, blank=True, null=True, db_index=True)

    def __str__(self):
        return f"{self.ID}"

    class Meta:
        verbose_name = 'Контакт'
        verbose_name_plural = 'Контакты'


class Email(models.Model):
    VALUE = models.CharField(verbose_name="Адрес электронной почты", max_length=100, blank=True, null=True, db_index=True)
    VALUE_TYPE = models.CharField(verbose_name="Тип электронной почты", max_length=100, blank=True, null=True)
    # uniq_value = models.CharField(verbose_name="Поле по которому идет поиск дублей", max_length=200, blank=True, null=True)
    contacts = models.ForeignKey(Contacts, verbose_name='Контакт', on_delete=models.CASCADE, related_name='EMAIL',
                                 blank=True, null=True, db_index=True)

    def __str__(self):
        return f"{self.VALUE}"

    class Meta:
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'


class Companies(models.Model):
    ID = models.PositiveIntegerField(primary_key=True, verbose_name='Идентификатор компании', unique=True,
                                     db_index=True)
    TITLE = models.CharField(verbose_name="Название", max_length=1000, blank=True, null=True, db_index=True)
    contacts = models.ManyToManyField(Contacts, db_index=True)

    def __str__(self):
        return f"{self.ID}. {self.TITLE}"

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компания'


class Deals(models.Model):
    ID = models.PositiveIntegerField(primary_key=True, verbose_name='Идентификатор сделки', unique=True, db_index=True)
    contacts = models.ManyToManyField(Contacts, db_index=True)

    def __str__(self):
        return str(self.ID)

    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'


