from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0063_norma_template_base64'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditoriaiso',
            name='abertura_auditores',
            field=models.TextField(blank=True, default='', verbose_name='Auditores (Abertura)'),
        ),
        migrations.AlterField(
            model_name='auditoriaiso',
            name='abertura_representantes',
            field=models.TextField(blank=True, default='', verbose_name='Representantes (Abertura)'),
        ),
        migrations.AlterField(
            model_name='auditoriaiso',
            name='revisao_auditores',
            field=models.TextField(blank=True, default='', verbose_name='Auditores (Revisão)'),
        ),
        migrations.AlterField(
            model_name='auditoriaiso',
            name='revisao_representantes',
            field=models.TextField(blank=True, default='', verbose_name='Representantes (Revisão)'),
        ),
        migrations.AlterField(
            model_name='auditoriaiso',
            name='encerramento_auditores',
            field=models.TextField(blank=True, default='', verbose_name='Auditores (Encerramento)'),
        ),
        migrations.AlterField(
            model_name='auditoriaiso',
            name='encerramento_representantes',
            field=models.TextField(blank=True, default='', verbose_name='Representantes (Encerramento)'),
        ),
    ]
