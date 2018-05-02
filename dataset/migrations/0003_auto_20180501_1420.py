# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-05-01 04:20
from __future__ import unicode_literals

import dataset.validators
import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0002_auto_20180429_1125'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scoreset',
            name='dataset_columns',
            field=django.contrib.postgres.fields.jsonb.JSONField(default={'count_columns': [], 'score_columns': ['score']}, validators=[dataset.validators.validate_scoreset_json], verbose_name='Dataset columns'),
        ),
    ]
