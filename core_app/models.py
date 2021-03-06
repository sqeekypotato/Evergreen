from __future__ import unicode_literals
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

# Create your models here.

class BankAccounts (models.Model):

    date = models.DateField(auto_now_add=True)
    account_name = models.CharField(max_length=200)
    # balance = models.IntegerField(blank=True, null=True)
    startRow = models.IntegerField()
    transDateCol = models.IntegerField()
    transCreditCol = models.IntegerField()
    transDebitCol = models.IntegerField()
    transDescriptionCol = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.user, self.account_name)

class Transaction (models.Model):

    # balance = models.IntegerField()
    date = models.DateField()
    description = models.CharField(max_length=1000)
    credit = models.IntegerField(null=True, blank=True)
    debit = models.IntegerField(null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)
    tag = models.CharField(max_length=50, null=True, blank=True)
    monthNum = models.IntegerField()
    monthName = models.CharField(max_length=10)
    year = models.IntegerField()
    user = models.CharField(max_length=200)
    account = models.ForeignKey(BankAccounts, on_delete=models.CASCADE)
    exclude_value = models.BooleanField(default=False)

    def __str__(self):
        return '{} - {}'.format(self.user, self.description)

    def get_absolute_url(self):
        return reverse('transaction-detail', kwargs={'pk': self.pk})

class Tags (models.Model):

    tag = models.CharField(max_length=50)
    category = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    drill_down = models.BooleanField(default=False)
    budget = models.IntegerField(default='0')
    fixed_cost = models.BooleanField(default=False)
    universal_average = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return '{} - {} - {}'.format(self.category, self.tag, self.user)

class UniversalTags (models.Model):
    tag = models.CharField(max_length=50)
    category = models.CharField(max_length=50)
    drill_down = models.BooleanField(default=False)

    def __str__(self):
        return '{} - {}'.format(self.category, self.tag)

class UserRule (models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    begins_with = models.BooleanField(default=False)
    ends_with = models.BooleanField(default=False)
    description = description = models.CharField(max_length=1000)
    tag = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.user, self.description)