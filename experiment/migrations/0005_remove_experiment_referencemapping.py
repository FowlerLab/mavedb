# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-08 04:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('experiment', '0004_auto_20170808_1326'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='experiment',
            name='ReferenceMapping',
        ),
    ]