# Generated by Django 3.0.2 on 2020-01-09 06:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0008_auto_20200108_0725'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='is_preprocessed',
            field=models.BooleanField(default=False),
        ),
    ]
