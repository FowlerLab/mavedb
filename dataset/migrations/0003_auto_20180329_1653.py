# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-03-29 05:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0002_auto_20180323_1851'),
    ]

    operations = [
        migrations.AlterField(
            model_name='experiment',
            name='doi_ids',
            field=models.ManyToManyField(blank=True, to='metadata.DoiIdentifier', verbose_name='DOI Identifiers'),
        ),
        migrations.AlterField(
            model_name='experiment',
            name='keywords',
            field=models.ManyToManyField(blank=True, to='metadata.Keyword', verbose_name='Keywords'),
        ),
        migrations.AlterField(
            model_name='experiment',
            name='pmid_ids',
            field=models.ManyToManyField(blank=True, to='metadata.PubmedIdentifier', verbose_name='PubMed Identifiers'),
        ),
        migrations.AlterField(
            model_name='experiment',
            name='sra_ids',
            field=models.ManyToManyField(blank=True, to='metadata.SraIdentifier', verbose_name='SRA Identifiers'),
        ),
        migrations.AlterField(
            model_name='experiment',
            name='target',
            field=models.CharField(default=None, max_length=256, verbose_name='Target Gene'),
        ),
        migrations.AlterField(
            model_name='experimentset',
            name='doi_ids',
            field=models.ManyToManyField(blank=True, to='metadata.DoiIdentifier', verbose_name='DOI Identifiers'),
        ),
        migrations.AlterField(
            model_name='experimentset',
            name='keywords',
            field=models.ManyToManyField(blank=True, to='metadata.Keyword', verbose_name='Keywords'),
        ),
        migrations.AlterField(
            model_name='experimentset',
            name='pmid_ids',
            field=models.ManyToManyField(blank=True, to='metadata.PubmedIdentifier', verbose_name='PubMed Identifiers'),
        ),
        migrations.AlterField(
            model_name='experimentset',
            name='sra_ids',
            field=models.ManyToManyField(blank=True, to='metadata.SraIdentifier', verbose_name='SRA Identifiers'),
        ),
        migrations.AlterField(
            model_name='scoreset',
            name='doi_ids',
            field=models.ManyToManyField(blank=True, to='metadata.DoiIdentifier', verbose_name='DOI Identifiers'),
        ),
        migrations.AlterField(
            model_name='scoreset',
            name='keywords',
            field=models.ManyToManyField(blank=True, to='metadata.Keyword', verbose_name='Keywords'),
        ),
        migrations.AlterField(
            model_name='scoreset',
            name='pmid_ids',
            field=models.ManyToManyField(blank=True, to='metadata.PubmedIdentifier', verbose_name='PubMed Identifiers'),
        ),
        migrations.AlterField(
            model_name='scoreset',
            name='sra_ids',
            field=models.ManyToManyField(blank=True, to='metadata.SraIdentifier', verbose_name='SRA Identifiers'),
        ),
    ]
