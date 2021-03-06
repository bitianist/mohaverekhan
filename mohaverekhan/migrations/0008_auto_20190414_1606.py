# Generated by Django 2.1.7 on 2019-04-14 11:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mohaverekhan', '0007_auto_20190414_1556'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BitianistBasicNormalizer',
        ),
        migrations.DeleteModel(
            name='BitianistCorrectionNormalizer',
        ),
        migrations.DeleteModel(
            name='BitianistCorrectionTagger',
        ),
        migrations.DeleteModel(
            name='BitianistReplacementNormalizer',
        ),
        migrations.DeleteModel(
            name='BitianistSeq2SeqNormalizer',
        ),
        migrations.DeleteModel(
            name='BitianistSeq2SeqTagger',
        ),
        migrations.CreateModel(
            name='MohaverekhanBasicNormalizer',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.normalizer',),
        ),
        migrations.CreateModel(
            name='MohaverekhanCorrectionNormalizer',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.normalizer',),
        ),
        migrations.CreateModel(
            name='MohaverekhanCorrectionTagger',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.tagger',),
        ),
        migrations.CreateModel(
            name='MohaverekhanReplacementNormalizer',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.normalizer',),
        ),
        migrations.CreateModel(
            name='MohaverekhanSeq2SeqNormalizer',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.normalizer',),
        ),
        migrations.CreateModel(
            name='MohaverekhanSeq2SeqTagger',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('mohaverekhan.tagger',),
        ),
    ]
