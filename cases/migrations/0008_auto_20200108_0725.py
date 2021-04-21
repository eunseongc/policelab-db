# Generated by Django 3.0.2 on 2020-01-08 07:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0007_auto_20200108_0543'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='case_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='case occured'),
        ),
        migrations.AlterField(
            model_name='video',
            name='rec_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='date recorded'),
        ),
    ]