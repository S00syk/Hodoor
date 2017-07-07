# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-06-14 13:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0020_holiday'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='holiday',
            name='spended_time',
        ),
        migrations.AddField(
            model_name='holiday',
            name='date',
            field=models.DateField(default=None),
        ),
        migrations.AddField(
            model_name='holiday',
            name='time_spend',
            field=models.DurationField(blank=True, default=None, null=True),
        ),
    ]