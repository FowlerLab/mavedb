# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-03 02:03
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('genome', '0006_auto_20180928_1713'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='targetgene',
            options={'ordering': ('id',), 'verbose_name': 'Target Gene', 'verbose_name_plural': 'Target Genes'},
        ),
    ]