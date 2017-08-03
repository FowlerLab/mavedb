# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-08-03 13:17
from __future__ import unicode_literals

import datetime
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import experiment.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(default=None, max_length=64, null=True, unique=True, validators=[experiment.validators.valid_exp_accession], verbose_name='Accession')),
                ('creation_date', models.DateField(default=datetime.date.today, verbose_name='Creation date')),
                ('last_used_suffix', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(limit_value=0)])),
                ('approved', models.BooleanField(default=False, verbose_name='Approved')),
                ('private', models.BooleanField(default=True, verbose_name='Private')),
                ('wt_sequence', models.TextField(default=None, validators=[experiment.validators.valid_wildtype_sequence], verbose_name='Wild type sequence')),
                ('target', models.TextField(default=None, verbose_name='Target')),
                ('abstract', models.TextField(blank=True, default='', verbose_name='Abstract')),
                ('method_desc', models.TextField(blank=True, default='', verbose_name='Method description')),
                ('sra_id', models.TextField(blank=True, default='', verbose_name='SRA identifier')),
                ('doi_id', models.TextField(blank=True, default='', verbose_name='DOI identifier')),
            ],
            options={
                'verbose_name': 'Experiment',
                'verbose_name_plural': 'Experiments',
                'ordering': ['-creation_date'],
            },
        ),
        migrations.CreateModel(
            name='ExperimentSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accession', models.CharField(default=None, max_length=10, null=True, unique=True, validators=[experiment.validators.valid_expset_accession], verbose_name='Accession')),
                ('last_used_suffix', models.CharField(blank=True, default='', max_length=64, null=True)),
                ('creation_date', models.DateField(default=datetime.date.today, verbose_name='Creation date')),
                ('approved', models.BooleanField(default=False, verbose_name='Approved')),
                ('private', models.BooleanField(default=True, verbose_name='Private')),
            ],
            options={
                'verbose_name': 'ExperimentSet',
                'verbose_name_plural': 'ExperimentSets',
                'ordering': ['-creation_date'],
            },
        ),
        migrations.AddField(
            model_name='experiment',
            name='experimentset',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='experiment.ExperimentSet'),
        ),
    ]
