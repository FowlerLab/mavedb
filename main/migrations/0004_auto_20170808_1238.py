# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-08 02:38
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_auto_20170807_1651'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='keyword',
            name='experiment',
        ),
        migrations.RemoveField(
            model_name='keyword',
            name='scoreset',
        ),
        migrations.RemoveField(
            model_name='referencemapping',
            name='experiment',
        ),
    ]