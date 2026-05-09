from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('complaint_system', '0002_auto_20250421_1155'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentcomplain',
            name='priority',
            field=models.CharField(choices=[('URGENT', 'Urgent (24h SLA)'), ('STANDARD', 'Standard (3d SLA)'), ('LOW', 'Low (7d SLA)')], default='STANDARD', max_length=20),
        ),
        migrations.AddField(
            model_name='studentcomplain',
            name='sla_deadline',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentcomplain',
            name='assigned_caretaker',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_complaints', to='complaint_system.caretaker'),
        ),
        migrations.AddField(
            model_name='studentcomplain',
            name='assigned_supervisor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='escalated_complaints', to='complaint_system.supervisor'),
        ),
        migrations.AddField(
            model_name='studentcomplain',
            name='resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentcomplain',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='studentcomplain',
            name='status',
            field=models.IntegerField(choices=[(0, 'Pending'), (1, 'In Progress'), (2, 'Resolved'), (3, 'Declined'), (4, 'Escalated'), (5, 'Closed'), (6, 'Reopened')], default=0),
        ),
        migrations.CreateModel(
            name='ComplaintActivityLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=100)),
                ('previous_status', models.IntegerField(blank=True, null=True)),
                ('new_status', models.IntegerField(blank=True, null=True)),
                ('details', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='globals.extrainfo')),
                ('complaint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_logs', to='complaint_system.studentcomplain')),
            ],
        ),
        migrations.CreateModel(
            name='ComplaintFeedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField()),
                ('comments', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('complaint', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='feedback_entry', to='complaint_system.studentcomplain')),
            ],
        ),
    ]
