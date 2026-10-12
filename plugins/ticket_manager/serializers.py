from plugins.project_manager.models import Project
from rest_framework import serializers
from base_modules.user_manager.models import User
from base_modules.user_manager.serializers import UserDetailSerializer, UserDetailSerializer
from base_modules.attachment.serializers import AttachmentSerializer
from .models import Ticket, Message, Attachment, Task

class LinkedTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'title', 'status',]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'title']


class TicketSerializer(serializers.ModelSerializer):
    client = UserDetailSerializer()
    assignees = UserDetailSerializer(many=True)
    attachments = AttachmentSerializer(many=True)
    ticket_linked = LinkedTicketSerializer()
    project = ProjectSerializer()

    class Meta:
        model = Ticket
        fields = '__all__'

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['last_message'] = self.get_last_message(instance)
        ret['has_unread'] = self.get_has_unread(instance)
        return ret

    def get_last_message(self, obj):
        """Usa i Message prefetchati in get_queryset (Prefetch 'ticket') per evitare N+1."""
        all_msgs = list(obj.ticket.all())
        if not all_msgs:
            return None
        lm = max(all_msgs, key=lambda m: m.insert_date)
        return {
            'id': lm.id,
            'insert_date': lm.insert_date.isoformat() if lm.insert_date else None,
            'author': {'id': lm.author.id, 'permission': lm.author.permission},
        }

    def get_has_unread(self, obj):
        """Usa Message e TicketUserRead (read_by_users) prefetchati. has_unread = esiste ultimo messaggio e (mai letto o last_message.insert_date > last_read_at)."""
        all_msgs = list(obj.ticket.all())
        if not all_msgs:
            return False
        lm = max(all_msgs, key=lambda m: m.insert_date)
        read_records = list(obj.read_by_users.all())
        last_read_at = read_records[0].last_read_at if read_records else None
        if last_read_at is None:
            return True
        return lm.insert_date > last_read_at


class TicketPostSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ticket
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = '__all__'

class MessageFullSerializer(serializers.ModelSerializer):

    author = UserDetailSerializer()
    attachments = AttachmentSerializer(many=True)

    class Meta:
        model = Message
        fields = '__all__'

class TaskCreateSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Task
        fields = [
            'project',
            'ticket',
            'title',
            'description',
            'status',
            'priority',
            'assignee',
            'estimate_hours',
            'start_date',
            'due_date',
        ]
        extra_kwargs = {
            'title': {'required': True},
            'ticket': {'required': False, 'allow_null': True},
            'status': {'default': 'todo'},
            'priority': {'default': 'medium'},
        }

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        due_date = attrs.get('due_date')
        if start_date and due_date and due_date < start_date:
            raise serializers.ValidationError({
                'due_date': 'La data di fine non può precedere la data di inizio.'
            })

        ticket = attrs.get('ticket')
        project = attrs.get('project')
        if ticket and project and ticket.project_id != project.id:
            raise serializers.ValidationError({
                'ticket': 'Il ticket non appartiene al progetto indicato.'
            })

        return attrs

class TaskSerializer(serializers.ModelSerializer):
    assignee = UserDetailSerializer()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'description',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'assignee',
            'estimate_hours',
            'start_date',
            'due_date',
            'ticket_id',
            'project_id',
            'created_at',
            'updated_at',
        ]
