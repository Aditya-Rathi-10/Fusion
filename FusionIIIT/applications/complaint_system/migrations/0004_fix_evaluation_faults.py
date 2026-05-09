"""
Migration: Fix evaluation workbook faults

1. Change StudentComplain.complainer from CASCADE to SET_NULL (orphan protection)
2. Add idempotency_key field to StudentComplain (duplicate submission prevention)
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('complaint_system', '0003_fix_models'),
    ]

    operations = [
        # Fix 4: CASCADE → SET_NULL on complainer FK (Data Integrity)
        migrations.AlterField(
            model_name='studentcomplain',
            name='complainer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='globals.extrainfo',
            ),
        ),
        # Fix 6: Add idempotency_key for duplicate submission prevention
        migrations.AddField(
            model_name='studentcomplain',
            name='idempotency_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
