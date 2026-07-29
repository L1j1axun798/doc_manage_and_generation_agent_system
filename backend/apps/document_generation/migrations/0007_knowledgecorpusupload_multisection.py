from django.db import migrations, models


def populate_section_codes(apps, schema_editor):
    KnowledgeCorpusUpload = apps.get_model(
        "document_generation",
        "KnowledgeCorpusUpload",
    )
    for upload in KnowledgeCorpusUpload.objects.only("id", "section_code").iterator():
        upload.section_codes = [upload.section_code]
        upload.save(update_fields=["section_codes"])


class Migration(migrations.Migration):
    dependencies = [
        ("document_generation", "0006_knowledgecorpusupload"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledgecorpusupload",
            name="fallback_to_full_document",
            field=models.BooleanField(default=False, verbose_name="允许整篇归入单一章节"),
        ),
        migrations.AddField(
            model_name="knowledgecorpusupload",
            name="indexed_section_codes",
            field=models.JSONField(blank=True, default=list, verbose_name="已索引章节列表"),
        ),
        migrations.AddField(
            model_name="knowledgecorpusupload",
            name="section_codes",
            field=models.JSONField(default=list, verbose_name="适用章节列表"),
        ),
        migrations.AddField(
            model_name="knowledgecorpusupload",
            name="skipped_section_codes",
            field=models.JSONField(blank=True, default=list, verbose_name="未识别章节列表"),
        ),
        migrations.RunPython(populate_section_codes, migrations.RunPython.noop),
    ]
