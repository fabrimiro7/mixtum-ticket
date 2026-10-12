"""
URL configuration for mixtum_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from base_modules.celery.views import flower_auth

urlpatterns = [
    path('admin/', admin.site.urls),

    # Celery Flower
    path("flower-auth/", flower_auth, name="flower-auth"),

    # Auth and Users
    path('api/v1/accounts/', include('allauth.urls')),
    path('api/v1/users/', include('base_modules.user_manager.urls')),

    # Attachments
    path('api/attachments/', include(('base_modules.attachment.urls', 'attachment'), namespace='attachment')),

    # Links
    path('api/links/', include(('base_modules.links.urls', 'links'), namespace='links')),

    # Ticket Manager
    path('api/ticket_manager/', include(('plugins.ticket_manager.urls', 'ticket_manager'), namespace='ticket_manager')),

    # Academy
    path('api/academy_manager/', include(('plugins.academy.urls', 'academy'), namespace='academy')),

    # Payments Manager
    path('api/payments_manager/', include(('plugins.payments_manager.urls', 'payments_manager'), namespace='payments_manager')),

    # Meeting manager
    path('api/meeting_manager/', include(('plugins.meeting.urls', 'meeting'), namespace='meeting')),

    # Project manager
    path('api/project_manager/', include(('plugins.project_manager.urls', 'project'), namespace='project')),

    # Sprint manager
    path('api/sprint_manager/', include(('plugins.sprint_manager.urls', 'sprint_manager'), namespace='sprint_manager')),

    # Report manager
    path('api/report_manager/', include(('plugins.report.urls', 'report'), namespace='report')),

    # SEO manager
    path('api/per_seo/', include(('plugins.per_seo.urls', 'per_seo'), namespace='per_seo')),

    # Workspace
    path('api/workspace/', include('base_modules.workspace.urls')),

    # Branding
    path('api/branding/', include('base_modules.branding.urls')),

    # Finance
    path('api/finance_manager_accounts/', include(('plugins.finance_manager_accounts.urls', 'finance_manager_accounts'), namespace='finance_account')),
    path('api/finance_manager_core/', include(('plugins.finance_manager_core.urls', 'finance_manager_core'), namespace='finance_core')),
    path('api/finance_manager_planning/', include(('plugins.finance_manager_planning.urls', 'finance_manager_planning'), namespace='finance_manager_planning')),


    # Cheshire Cat AI Integration
    path('api/cat/', include(('plugins.ai_integrations.cashirecat.urls', 'cashirecat'), namespace='cashirecat')),

    # Documents
    path('api/documents/', include(('plugins.documents.urls', 'documents'), namespace='documents')),
    # External Integrations
    path('api/slack/', include(('base_modules.integrations.slack.urls', 'slack'), namespace='slack')),
    path('api/n8n/', include(('base_modules.integrations.n8n.urls', 'n8n'), namespace='n8n')),
    # Twilio WhatsApp Integration
    path('api/whatsapp/', include(('base_modules.integrations.twilio.urls', 'twilio'), namespace='twilio')),
]


if getattr(settings, 'AUTH_MODE', 'django') == 'keycloak':
    urlpatterns += [path('oidc/', include('mozilla_django_oidc.urls'))]
