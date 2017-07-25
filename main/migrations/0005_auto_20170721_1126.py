# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-21 01:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_auto_20170720_1916'),
    ]

    operations = [
        migrations.AddField(
            model_name='experiment',
            name='doi',
            field=models.TextField(default='Not provided', verbose_name='DOI'),
        ),
        migrations.AddField(
            model_name='experiment',
            name='sra',
            field=models.TextField(default='Not provided', verbose_name='SRA'),
        ),
    ]