# Generated by Django 3.1 on 2020-08-25 07:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('cases', '0016_auto_20200130_1411'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cases', to='auth.group'),
        ),
    ]