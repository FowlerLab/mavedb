# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-08 04:13
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('experiment', '0005_remove_experiment_referencemapping'),
        ('main', '0006_auto_20170808_1348'),
    ]

    operations = [
        migrations.AddField(
            model_name='referencemapping',
            name='experiment',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='experiment.Experiment', verbose_name='Experiment target mapping'),
        ),
    ]