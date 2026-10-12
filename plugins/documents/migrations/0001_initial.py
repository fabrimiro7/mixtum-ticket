"""
Initial migration for the documents plugin.

Creates all 12 models:
- DocumentType, DocumentCategory, DocumentStatus (taxonomy)
- Block, DocumentTemplate, DocumentTemplateBlock (template library)
- Document, DocumentBlock, DocumentCategoryAssignment (document instances)
- Party, DocumentSigner, DocumentSignerEvent (signer workflow)
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("workspace", "0001_initial"),
    ]

    operations = [
        # ==============================================================
        # 1. Core Taxonomy
        # ==============================================================
        migrations.CreateModel(
            name="DocumentCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                (
                    "color",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional colour value (e.g. #FF5733).",
                        max_length=30,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=0)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="documents.documentcategory",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_categories",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Category",
                "verbose_name_plural": "Document Categories",
                "ordering": ["sort_order", "title"],
            },
        ),
        migrations.CreateModel(
            name="DocumentStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.SlugField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                (
                    "is_terminal",
                    models.BooleanField(
                        default=False,
                        help_text="Terminal statuses prevent further editing.",
                    ),
                ),
                ("sort_order", models.IntegerField(default=0)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_statuses",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Status",
                "verbose_name_plural": "Document Statuses",
                "ordering": ["sort_order", "title"],
            },
        ),
        migrations.CreateModel(
            name="Block",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                (
                    "content",
                    models.TextField(
                        help_text="Block body — may contain placeholders like {{ client.first_name }}.",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_blocks_library",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Block",
                "verbose_name_plural": "Blocks",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="DocumentTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_templates",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Template",
                "verbose_name_plural": "Document Templates",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="DocumentTemplateBlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title_snapshot",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Snapshot of block.title at the time of addition.",
                        max_length=255,
                    ),
                ),
                (
                    "content_snapshot",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Snapshot of block.content at the time of addition.",
                    ),
                ),
                ("position", models.PositiveIntegerField()),
                (
                    "block",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="template_usages",
                        to="documents.block",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="template_blocks",
                        to="documents.documenttemplate",
                    ),
                ),
            ],
            options={
                "verbose_name": "Template Block",
                "verbose_name_plural": "Template Blocks",
                "ordering": ["position"],
            },
        ),
        # DocumentType (depends on DocumentTemplate for default_template)
        migrations.CreateModel(
            name="DocumentType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.SlugField(
                        help_text="Slug-like identifier, unique within the workspace.",
                        max_length=100,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("requires_signature", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.IntegerField(default=0)),
                (
                    "default_template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="default_for_types",
                        to="documents.documenttemplate",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_types",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Type",
                "verbose_name_plural": "Document Types",
                "ordering": ["sort_order", "title"],
            },
        ),
        # ==============================================================
        # 2. Document Instances
        # ==============================================================
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                (
                    "context_snapshot",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Frozen context used for rendering after freeze.",
                    ),
                ),
                (
                    "signers_snapshot",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Frozen signers summary after freeze.",
                    ),
                ),
                (
                    "rendered_html",
                    models.TextField(
                        blank=True,
                        help_text="Last rendered output.",
                        null=True,
                    ),
                ),
                (
                    "render_hash",
                    models.CharField(
                        blank=True,
                        help_text="SHA-256 hash of the rendered HTML.",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "frozen_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Timestamp when the document was frozen (immutable after this point).",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="documents.documentstatus",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        help_text="Origin template reference (informational).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="documents.documenttemplate",
                    ),
                ),
                (
                    "type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="documents.documenttype",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document",
                "verbose_name_plural": "Documents",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DocumentBlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("position", models.PositiveIntegerField()),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blocks",
                        to="documents.document",
                    ),
                ),
                (
                    "source_template_block",
                    models.ForeignKey(
                        blank=True,
                        help_text="Original template block this was copied from (if any).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="document_block_instances",
                        to="documents.documenttemplateblock",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Block",
                "verbose_name_plural": "Document Blocks",
                "ordering": ["position"],
            },
        ),
        migrations.CreateModel(
            name="DocumentCategoryAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_primary", models.BooleanField(default=False)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_assignments",
                        to="documents.documentcategory",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_assignments",
                        to="documents.document",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Category Assignment",
                "verbose_name_plural": "Document Category Assignments",
            },
        ),
        migrations.AddField(
            model_name="document",
            name="categories",
            field=models.ManyToManyField(
                blank=True,
                related_name="documents",
                through="documents.DocumentCategoryAssignment",
                to="documents.documentcategory",
            ),
        ),
        # ==============================================================
        # 3. Signers
        # ==============================================================
        migrations.CreateModel(
            name="Party",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user_id",
                    models.UUIDField(
                        blank=True,
                        help_text="UUID of the auth user (loose coupling — not a FK).",
                        null=True,
                    ),
                ),
                (
                    "first_name",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "last_name",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "company_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "email",
                    models.EmailField(blank=True, db_index=True, default="", max_length=254),
                ),
                (
                    "phone",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                (
                    "tax_id",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_parties",
                        to="workspace.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Party",
                "verbose_name_plural": "Parties",
                "ordering": ["last_name", "first_name"],
            },
        ),
        migrations.CreateModel(
            name="DocumentSigner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        help_text="e.g. client, provider, witness",
                        max_length=100,
                    ),
                ),
                (
                    "position",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Signing order (relevant when routing_mode is sequential).",
                    ),
                ),
                (
                    "routing_mode",
                    models.CharField(
                        choices=[("parallel", "Parallel"), ("sequential", "Sequential")],
                        default="parallel",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("invited", "Invited"),
                            ("viewed", "Viewed"),
                            ("signed", "Signed"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("invited_at", models.DateTimeField(blank=True, null=True)),
                ("viewed_at", models.DateTimeField(blank=True, null=True)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                (
                    "signature_method",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "provider_envelope_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "provider_signer_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "magic_link_token_hash",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signers",
                        to="documents.document",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="signer_roles",
                        to="documents.party",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Signer",
                "verbose_name_plural": "Document Signers",
                "ordering": ["position"],
            },
        ),
        migrations.CreateModel(
            name="DocumentSignerEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("INVITED", "Invited"),
                            ("OPENED", "Opened"),
                            ("OTP_SENT", "OTP Sent"),
                            ("SIGNED", "Signed"),
                            ("REJECTED", "Rejected"),
                            ("EXPIRED", "Expired"),
                            ("REMINDER_SENT", "Reminder Sent"),
                        ],
                        help_text="e.g. INVITED, OPENED, SIGNED, REJECTED",
                        max_length=50,
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("user_agent", models.TextField(blank=True, default="")),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document_signer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="documents.documentsigner",
                    ),
                ),
            ],
            options={
                "verbose_name": "Signer Event",
                "verbose_name_plural": "Signer Events",
                "ordering": ["created_at"],
            },
        ),
        # ==============================================================
        # 4. Constraints & Indexes
        # ==============================================================
        # DocumentCategory
        migrations.AddConstraint(
            model_name="documentcategory",
            constraint=models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="documents_doccat_ws_slug_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="documentcategory",
            index=models.Index(
                fields=["workspace", "parent", "sort_order"],
                name="documents_doccat_ws_parent_idx",
            ),
        ),
        # DocumentStatus
        migrations.AddConstraint(
            model_name="documentstatus",
            constraint=models.UniqueConstraint(
                fields=["workspace", "code"],
                name="documents_docstatus_ws_code_uniq",
            ),
        ),
        # DocumentTemplateBlock
        migrations.AddConstraint(
            model_name="documenttemplateblock",
            constraint=models.UniqueConstraint(
                fields=["template", "position"],
                name="documents_tplblock_tpl_pos_uniq",
            ),
        ),
        # DocumentType
        migrations.AddConstraint(
            model_name="documenttype",
            constraint=models.UniqueConstraint(
                fields=["workspace", "code"],
                name="documents_doctype_ws_code_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="documenttype",
            index=models.Index(
                fields=["workspace", "is_active", "sort_order"],
                name="docs_dt_ws_active_idx",
            ),
        ),
        # DocumentBlock
        migrations.AddConstraint(
            model_name="documentblock",
            constraint=models.UniqueConstraint(
                fields=["document", "position"],
                name="documents_docblock_doc_pos_uniq",
            ),
        ),
        # DocumentCategoryAssignment
        migrations.AddConstraint(
            model_name="documentcategoryassignment",
            constraint=models.UniqueConstraint(
                fields=["document", "category"],
                name="documents_catassign_doc_cat_uniq",
            ),
        ),
        # DocumentSigner
        migrations.AddConstraint(
            model_name="documentsigner",
            constraint=models.UniqueConstraint(
                fields=["document", "party", "role"],
                name="documents_signer_doc_party_role_uniq",
            ),
        ),
    ]
