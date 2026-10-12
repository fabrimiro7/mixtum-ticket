from rest_framework import status
from rest_framework.test import APITestCase

from base_modules.user_manager.models import User
from plugins.project_manager.models import Project
from plugins.ticket_manager.models import Task


class ProjectTaskListTests(APITestCase):
    def setUp(self):
        self.associate = User.objects.create_user(
            username='associate',
            email='associate@example.com',
            password='password',
        )
        self.associate.permission = 50
        self.associate.save(update_fields=['permission'])

        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            password='password',
        )
        self.project = Project.objects.create(
            title='Progetto test',
            description='Descrizione progetto test',
            client=self.client_user,
        )

    def test_post_creates_project_task(self):
        self.client.force_authenticate(user=self.associate)

        response = self.client.post('/api/ticket_manager/tasks/', {
            'project': self.project.id,
            'title': 'Task test',
            'description': 'Descrizione task test',
            'assignee': self.associate.id,
            'priority': 'medium',
            'status': 'todo',
            'estimate_hours': '2.50',
            'start_date': '2026-06-19',
            'due_date': '2026-06-20',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.count(), 1)
        task = Task.objects.get()
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.assignee, self.associate)
        self.assertEqual(response.data['title'], 'Task test')
