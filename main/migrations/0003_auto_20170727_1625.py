# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-27 06:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20170727_1530'),
    ]

    operations = [
        migrations.AlterField(
            model_name='news',
            name='text',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='about',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='citation',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='documentation',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='privacy',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='terms',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='siteinformation',
            name='usage_guide',
            field=models.TextField(default=''),
        ),
    ]