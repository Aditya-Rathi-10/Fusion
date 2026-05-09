from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('complaint_system', '0002_auto_20250421_1155'),
        ('complaint_system', '0002_complaint_usecases'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE complaint_system_supervisor ADD COLUMN IF NOT EXISTS area varchar(20)",
                    "ALTER TABLE complaint_system_supervisor DROP COLUMN IF EXISTS area",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='supervisor',
                    name='area',
                    field=models.CharField(choices=[
                        ('hall-1', 'hall-1'), ('hall-3', 'hall-3'), ('hall-4', 'hall-4'),
                        ('CC1', 'CC1'), ('CC2', 'CC2'), ('core_lab', 'core_lab'),
                        ('LHTC', 'LHTC'), ('NR2', 'NR2'),
                        ('Rewa_Residency', 'Rewa_Residency'),
                        ('Maa Saraswati Hostel', 'Maa Saraswati Hostel'),
                        ('Nagarjun Hostel', 'Nagarjun Hostel'),
                        ('Panini Hostel', 'Panini Hostel'),
                    ], max_length=20, blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='supervisor',
                    name='sup_id',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='globals.extrainfo'),
                ),
                migrations.RemoveField(
                    model_name='supervisor',
                    name='type',
                ),
            ],
        ),
        migrations.CreateModel(
            name='ReopenRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('justification', models.TextField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('DENIED', 'Denied')], default='PENDING', max_length=10)),
                ('review_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('complaint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reopen_requests', to='complaint_system.studentcomplain')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reopen_requests_made', to='globals.extrainfo')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reopen_reviews', to='globals.extrainfo')),
            ],
        ),
    ]
