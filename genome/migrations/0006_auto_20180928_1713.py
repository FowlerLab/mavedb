# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-09-28 07:13
from __future__ import unicode_literals

from django.db import migrations, models
import genome.validators


class Migration(migrations.Migration):

    dependencies = [("genome", "0005_auto_20180904_1228")]

    operations = [
        migrations.AlterField(
            model_name="referencegenome",
            name="organism_name",
            field=models.CharField(
                default=None,
                max_length=256,
                validators=[genome.validators.validate_organism_name],
                verbose_name="Organism",
            ),
        )
    ]
