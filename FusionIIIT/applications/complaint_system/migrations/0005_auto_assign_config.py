"""
Migration: Add ComplaintAssigneeConfig

Creates a configuration mapping table to allow dynamic auto-assignment instead of hardcoded rules.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('complaint_system', '0004_fix_evaluation_faults'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComplaintAssigneeConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.CharField(max_length=20)),
                ('complaint_type', models.CharField(max_length=20)),
                ('caretaker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='complaint_system.caretaker')),
                ('supervisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='complaint_system.supervisor')),
            ],
            options={
                'unique_together': {('location', 'complaint_type')},
            },
        ),
    ]
