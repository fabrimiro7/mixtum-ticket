from base_modules.attachment.serializers import AttachmentCreateSerializer
from base_modules.mailer.services import send_individual_templated_emails
from base_modules.workspace.models import WorkspaceUser
from plugins.ticket_manager.permissions import (
    IsWorkspaceMemberOrClientOrAssigneeOrAdmin,
    can_access_ticket,
    can_edit_ticket,
    get_user_workspace_ids,
)
from rest_framework.response import Response
from datetime import datetime, time
from django.db.models import Q, Case, When, IntegerField, Prefetch
from rest_framework import generics
from rest_framework import status
from .models import Ticket, Message, Task, TASK_STATUS_CHOICES, TicketUserRead
from plugins.project_manager.models import Project
from base_modules.user_manager.models import User
from typing import Optional
from .serializers import MessageFullSerializer, TicketSerializer, MessageSerializer, TicketPostSerializer, TaskCreateSerializer, TaskSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from mixtum_core.settings.base import REMOTE_API
from base_modules.user_manager.authentication import JWTAuthentication
from base_modules.user_manager.models import *
import requests
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from .pagination import StandardResultsSetPagination
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from django.core.exceptions import ValidationError

class TicketList(generics.ListCreateAPIView):
    serializer_class = TicketSerializer
    pagination_class = StandardResultsSetPagination

    if JWTAuthentication is not None:
        authentication_classes = [JWTAuthentication]

    # Ordinamenti consentiti
    allowed_ordering = {
        "id", "-id",
        "opening_date", "-opening_date",
        "closing_date", "-closing_date",
        "priority", "-priority",
        "priority_custom", "-priority_custom",
        "metatag__released_at", "-metatag__released_at",
    }

    def _parse_date_or_datetime(self, s: str) -> datetime:
        """
        Accetta:
          - 'YYYY-MM-DD' -> restituisce aware datetime alle 00:00
          - ISO 8601 completa -> restituisce aware datetime
        """
        if not s:
            raise ValidationError({"date": "Stringa data vuota"})

        # Prova ISO 8601 completa
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
        except Exception:
            pass

        # Prova solo data 'YYYY-MM-DD'
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            start_dt = datetime.combine(d, time.min)
            return timezone.make_aware(start_dt)
        except Exception:
            raise ValidationError({"date": f"Formato data non valido: {s}"})

    def get_queryset(self):
        user = self.request.user

        qs = (
            Ticket.objects
            .select_related("client", "project", "ticket_workspace")
            .prefetch_related(
                "assignees",
                "attachments",
                Prefetch(
                    "ticket",
                    queryset=Message.objects.order_by("-insert_date").select_related("author"),
                ),
                Prefetch(
                    "read_by_users",
                    queryset=TicketUserRead.objects.filter(user=user).only("ticket_id", "last_read_at"),
                ),
            )
        )

        # -----------------------------
        # Permessi/Visibilità
        # -----------------------------
        if hasattr(user, "is_superadmin") and callable(user.is_superadmin) and user.is_superadmin():
            # SuperAdmin: vede tutto
            pass
        elif hasattr(user, "is_associate") and callable(user.is_associate) and user.is_associate():
            # Associate: come can_access_ticket — assignee, client, o condivisione workspace
            # (ticket_workspace nei miei ws, oppure progetto il cui client condivide un ws con me)
            ws_ids = get_user_workspace_ids(user)
            base_q = Q(assignees=user) | Q(client=user)
            if ws_ids:
                base_q = base_q | Q(ticket_workspace_id__in=ws_ids) | Q(
                    project__client__workspaceuser_set__workspace_id__in=ws_ids
                )
            qs = qs.filter(base_q).distinct()
        else:
            # Utente "normale": visibilità per workspace/client
            workspace_ids = WorkspaceUser.objects.filter(
                user=user
            ).values_list("workspace_id", flat=True)

            users_in_same_ws_ids = WorkspaceUser.objects.filter(
                workspace_id__in=workspace_ids
            ).values_list("user_id", flat=True)

            qs = qs.filter(
                Q(client=user) |
                Q(ticket_workspace_id__in=workspace_ids) |
                Q(client_id__in=users_in_same_ws_ids)
            ).distinct()

        # -----------------------------
        # Filtri Query Params
        # -----------------------------
        params = self.request.query_params

        # mine=true -> solo ticket creati da me o assegnati a me
        mine_val = params.get("mine")
        if mine_val == "true":
            qs = qs.filter(Q(client=user) | Q(assignees=user)).distinct()

        owner_val = params.get("owner")
        if owner_val:
            try:
                owner_id = int(owner_val)
            except (TypeError, ValueError):
                raise ValidationError({"owner": "Owner ID non valido"})
            qs = qs.filter(client_id=owner_id)

        workspace_open = params.get("workspace_open")
        if workspace_open == "true":
            workspace_ids = WorkspaceUser.objects.filter(
                user=user
            ).values_list("workspace_id", flat=True)
            other_user_ids = WorkspaceUser.objects.filter(
                workspace_id__in=workspace_ids
            ).exclude(user=user).values_list("user_id", flat=True)

            if not other_user_ids:
                return Ticket.objects.none()

            qs = qs.filter(client_id__in=other_user_ids, status="open")

        # status (singolo) — non applicato se released=true
        status_val = params.get("status")
        released_val = params.get("released")
        if released_val == "true":
            qs = qs.filter(metatag__released=True)
        elif status_val:
            qs = qs.filter(status=status_val)

        # status__in (lista CSV) — solo se non released
        status_in_val = params.get("status__in")
        if status_in_val and released_val != "true":
            statuses = [s.strip() for s in status_in_val.split(",") if s.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)

        # assigned: 'true' / 'false'
        assigned = params.get("assigned")
        if assigned == "true":
            qs = qs.filter(assignees__isnull=False)
        elif assigned == "false":
            qs = qs.filter(assignees__isnull=True)

        # priority
        priority = params.get("priority")
        if priority:
            qs = qs.filter(priority=priority)

        # project__in (lista CSV) ha priorità su project (singolo)
        project_in_val = params.get("project__in")
        if project_in_val:
            raw = [x.strip() for x in project_in_val.split(",") if x.strip()]
            ids = []
            for x in raw:
                try:
                    i = int(x)
                    if i > 0:
                        ids.append(i)
                except (TypeError, ValueError):
                    pass
            if ids:
                qs = qs.filter(project_id__in=ids)
        else:
            project = params.get("project")
            if project:
                qs = qs.filter(project_id=project)

        # ticket_type__in (CSV) e/o ticket_type (CSV o ripetuto)
        type_values = []
        raw_in = params.get("ticket_type__in")
        if raw_in:
            type_values.extend([t.strip() for t in raw_in.split(",") if t.strip()])
        for raw in params.getlist("ticket_type"):
            type_values.extend([t.strip() for t in raw.split(",") if t.strip()])
        type_aliases = {
            "features": "feature",
            "evolutiva": "evo",
            "evolution": "evo",
            "evolutionary": "evo",
        }
        types = []
        for t in type_values:
            t_norm = type_aliases.get(t.lower(), t)
            if t_norm and t_norm not in types:
                types.append(t_norm)
        if types:
            qs = qs.filter(ticket_type__in=types)

        # payments_status: 'true' / 'false'
        payments_status = params.get("payments_status")
        if payments_status == "true":
            qs = qs.filter(payments_status=True)
        elif payments_status == "false":
            qs = qs.filter(payments_status=False)

        # search: per id (se numerico) o parole in titolo/descrizione
        search = params.get("search")
        if search:
            search = search.strip()
            if search:
                try:
                    sid = int(search)
                    qs = qs.filter(Q(id=sid) | Q(title__icontains=search) | Q(description__icontains=search))
                except (TypeError, ValueError):
                    qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        # -----------------------------
        # Filtri periodo (opening_date | closing_date)
        # -----------------------------
        date_field = params.get("date_field") or "opening_date"
        if date_field not in ("opening_date", "closing_date"):
            raise ValidationError({"date_field": "Valori ammessi: opening_date, closing_date"})

        year = params.get("year")
        month = params.get("month")
        if year:
            try:
                qs = qs.filter(**{f"{date_field}__year": int(year)})
            except (TypeError, ValueError):
                raise ValidationError({"year": "Anno non valido"})
        if month:
            try:
                m = int(month)
                if m < 1 or m > 12:
                    raise ValidationError({"month": "Mese deve essere 1-12"})
                qs = qs.filter(**{f"{date_field}__month": m})
            except (TypeError, ValueError):
                raise ValidationError({"month": "Mese non valido"})

        # range from / to
        from_str = params.get("from")
        to_str = params.get("to")

        start_dt: Optional[datetime] = self._parse_date_or_datetime(from_str) if from_str else None
        end_dt: Optional[datetime] = self._parse_date_or_datetime(to_str) if to_str else None

        if start_dt and end_dt and end_dt < start_dt:
            raise ValidationError({"range": "'to' deve essere >= 'from'"})

        if start_dt:
            qs = qs.filter(**{f"{date_field}__gte": start_dt})
        if end_dt:
            # Se 'to' è solo data (YYYY-MM-DD), includi l'intera giornata
            if to_str and len(to_str) == 10 and to_str.count("-") == 2:
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            qs = qs.filter(**{f"{date_field}__lte": end_dt})

        # -----------------------------
        # Ordinamento
        # -----------------------------
        ordering = params.get("ordering")

        # Ordinamento custom per priorità: high -> medium -> low
        if ordering == "priority_custom":
            priority_case = Case(
                When(priority="high", then=1),
                When(priority="medium", then=2),
                When(priority="low", then=3),
                default=4,
                output_field=IntegerField(),
            )
            qs = qs.annotate(priority_rank=priority_case).order_by("priority_rank", "-opening_date")
        elif ordering == "-priority_custom":
            priority_case = Case(
                When(priority="high", then=1),
                When(priority="medium", then=2),
                When(priority="low", then=3),
                default=4,
                output_field=IntegerField(),
            )
            qs = qs.annotate(priority_rank=priority_case).order_by("-priority_rank", "-opening_date")
        elif ordering in self.allowed_ordering:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-opening_date")

        return qs
        
class TicketDetail(generics.RetrieveUpdateAPIView):
    if REMOTE_API is True:
        authentication_classes = [JWTAuthentication]
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsWorkspaceMemberOrClientOrAssigneeOrAdmin]

    def get(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("ticket_workspace"), pk=pk)
        if not can_access_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        serializer = TicketSerializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("ticket_workspace"), pk=pk)
        if not can_edit_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        ticket.delete()
        return Response({"message": "success"}, status=status.HTTP_200_OK)     

class ToggleTicketPayment(APIView):
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        try:
            ticket = Ticket.objects.get(pk=pk)
        except Exception:
            ticket = None
        if request.user.is_at_least_associate():
            if ticket:
                ticket.payments_status = not ticket.payments_status
                ticket.save()
                return Response({"message": "success"}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "fail, ticket non trovato"}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)


class MarkTicketAsRead(APIView):
    """POST: segna il ticket come letto per l'utente corrente (Opzione 4 - messaggi non letti)."""
    if REMOTE_API is True:
        authentication_classes = [JWTAuthentication]

    def post(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, pk=ticket_id)
        if not can_access_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        obj, _ = TicketUserRead.objects.update_or_create(
            ticket=ticket, user=request.user,
            defaults={"last_read_at": timezone.now()},
        )
        return Response({"message": "success", "last_read_at": obj.last_read_at.isoformat()}, status=status.HTTP_200_OK)


class TicketPutView(APIView):
    if REMOTE_API is True:
        authentication_classes = [JWTAuthentication]

    serializer_class = TicketPostSerializer

    def get(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("ticket_workspace"), pk=pk)
        if not can_access_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        serializer = TicketPostSerializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("ticket_workspace"), pk=pk)
        if not can_edit_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        serializer = TicketPostSerializer(ticket, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"data": serializer.data, "message": "success"}, status=status.HTTP_200_OK)
        error_list = [serializer.errors[k][0] for k in serializer.errors]
        print(error_list)
        return Response({"data": serializer.errors, "message": "fail"}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("ticket_workspace"), pk=pk)
        if not can_edit_ticket(request.user, ticket):
            return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)
        data = request.data
        if "status" in data:
            ticket.status = data["status"]
        if "priority" in data:
            ticket.priority = data["priority"]
        if "assignees" in data:
            try:
                ids = [int(x) for x in data["assignees"]]
                ticket.assignees.set(ids)
            except (TypeError, ValueError):
                return Response({"assignees": "Lista di ID utenti non valida"}, status=status.HTTP_400_BAD_REQUEST)
        if "metatag" in data:
            meta = dict(ticket.metatag) if isinstance(ticket.metatag, dict) else {}
            incoming = data["metatag"]
            if isinstance(incoming, dict):
                if "released" in incoming:
                    meta["released"] = bool(incoming["released"])
                if "released_at" in incoming:
                    val = incoming["released_at"]
                    meta["released_at"] = val if val is None or isinstance(val, str) else str(val)
            ticket.metatag = meta
        ticket.save()
        serializer = TicketSerializer(ticket)
        return Response({"data": serializer.data, "message": "success"}, status=status.HTTP_200_OK)

class TicketView(APIView):
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    serializer_class = TicketPostSerializer

    def get(self, request):
        user = request.user
        if user.is_superadmin():
            not_assigned_ticket = Ticket.objects.filter(assignees=None, status="open")
            assigned_ticket = Ticket.objects.filter(Q(status="open")| Q (status="in_progress")).exclude(assignees=None)
            resolved_ticket = Ticket.objects.filter(Q(status="resolved")| Q (status="closed")).exclude(assignees=None)
            nat = TicketPostSerializer(not_assigned_ticket, many=True)
            at = TicketPostSerializer(assigned_ticket, many=True)
            rt = TicketPostSerializer(resolved_ticket, many=True)
            data = {
                'not_assigned_ticket': nat.data,
                'assigned_ticket': at.data,
                'resolved_ticket': rt.data,
            }
            return Response(data, status=status.HTTP_200_OK)
        elif user.is_at_least_associate():
            assigned_ticket = Ticket.objects.filter(Q(status="open") | Q(status="in_progress")).exclude(assignees=None)
            resolved_ticket = Ticket.objects.filter(Q(status="resolved") | Q(status="closed")).exclude(assignees=None)
            at = TicketPostSerializer(assigned_ticket, many=True)
            rt = TicketPostSerializer(resolved_ticket, many=True)
            data = {
                'assigned_ticket': at.data,
                'resolved_ticket': rt.data,
            }
            return Response(data, status=status.HTTP_200_OK)
        else:
            open_ticket = Ticket.objects.filter(client=user,status="open")
            in_progress_ticket = Ticket.objects.filter(client=user,status="in_progress")
            resolved_ticket = Ticket.objects.filter((Q(status="resolved")|Q(status="closed")),client=user)
            ot = TicketPostSerializer(open_ticket, many=True)
            it = TicketPostSerializer(in_progress_ticket, many=True)
            rt = TicketPostSerializer(resolved_ticket, many=True)
            data = {
                'open_ticket': ot.data,
                'in_progress_ticket': it.data,
                'resolved_ticket': rt.data,
            }
            return Response(data, status=status.HTTP_200_OK)
        return Response({"message": "permission denied"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request, *args, **kwargs):
        serializer = TicketPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.is_valid():
            ticket = serializer.save()
            return Response({"data": serializer.data, "message": "success"}, status=status.HTTP_200_OK)
        return Response({"data": serializer.data, "message": "fail"}, status=status.HTTP_200_OK)

class UserAssignedTicketList(APIView):
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        in_progress_tickets = Ticket.objects.filter(assignees=user, status='in_progress')
        open_tickets = Ticket.objects.filter(assignees=user, status='open')
        resolved_tickets = Ticket.objects.filter(assignees=user, status='resolved')
        closed_tickets = Ticket.objects.filter(assignees=user, status='closed')

        in_progress_serializer = TicketSerializer(in_progress_tickets, many=True)
        open_serializer = TicketSerializer(open_tickets, many=True)
        resolved_serializer = TicketSerializer(resolved_tickets, many=True)
        closed_serializer = TicketSerializer(closed_tickets, many=True)

        return Response({
            'in_progress': in_progress_serializer.data,
            'open': open_serializer.data,
            'resolved': resolved_serializer.data,
            'closed': closed_serializer.data,
        }, status=status.HTTP_200_OK)


class UserClientTicketList(APIView):
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        in_progress_tickets = Ticket.objects.filter(client=user, status='in_progress')
        open_tickets = Ticket.objects.filter(client=user, status='open')
        resolved_tickets = Ticket.objects.filter(client=user, status='resolved')
        closed_tickets = Ticket.objects.filter(client=user, status='closed')

        in_progress_serializer = TicketSerializer(in_progress_tickets, many=True)
        open_serializer = TicketSerializer(open_tickets, many=True)
        resolved_serializer = TicketSerializer(resolved_tickets, many=True)
        closed_serializer = TicketSerializer(closed_tickets, many=True)

        return Response({
            'in_progress': in_progress_serializer.data,
            'open': open_serializer.data,
            'resolved': resolved_serializer.data,
            'closed': closed_serializer.data,
        }, status=status.HTTP_200_OK)


class TicketMessages(generics.ListCreateAPIView):
    serializer_class = MessageFullSerializer
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def get(self, request, ticket_id):
        messages = Message.objects.filter(ticket__id=ticket_id)
        if messages:
            messages_serializer = MessageFullSerializer(messages, many=True)
            return Response({"data": messages_serializer.data, "message":"success"}, status=status.HTTP_200_OK)
        return Response({"data": [], "message":"fail"}, status=status.HTTP_200_OK)
    
    def post(self, request, ticket_id):
        request_data = request.data.copy()
        request_data['ticket'] = ticket_id
        request_data['author'] = request.user.id
        message_serializer = MessageSerializer(data=request_data)
        if message_serializer.is_valid():
            message_serializer.save()
        try:
            ticket = Ticket.objects.select_related('client').prefetch_related('assignees').get(id=ticket_id)
            if ticket:
                # Costruisci la lista dei destinatari con i loro dati personali
                recipients = []
                seen_emails = set()
                
                # Aggiungi il client
                if ticket.client and ticket.client.email:
                    email = ticket.client.email.lower()
                    if email not in seen_emails:
                        seen_emails.add(email)
                        recipients.append({
                            'email': ticket.client.email,
                            'first_name': ticket.client.first_name or '',
                            'last_name': ticket.client.last_name or '',
                            'name': ticket.client.get_name() or ticket.client.email,
                        })
                
                # Aggiungi gli assignees
                for user in ticket.assignees.all():
                    if user.email:
                        email = user.email.lower()
                        if email not in seen_emails:
                            seen_emails.add(email)
                            recipients.append({
                                'email': user.email,
                                'first_name': user.first_name or '',
                                'last_name': user.last_name or '',
                                'name': user.get_name() or user.email,
                            })
                
                # Invia email individuali personalizzate
                send_individual_templated_emails(
                    template_slug="notifica_messaggio",
                    recipients=recipients,
                    base_context={
                        "sender": {
                            "first_name": request.user.first_name or '',
                            "last_name": request.user.last_name or '',
                            "name": request.user.get_name() or request.user.email,
                        },
                        "ticket": {
                            "id": ticket.id,
                            "title": ticket.title,
                        },
                    },
                )
        except Exception as e:
            print("Errore invio email:", str(e))
            return Response({"data": message_serializer.errors, "message": "fail"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"data": message_serializer.data, "message": "success"}, status=status.HTTP_201_CREATED)



class TicketAttachment(APIView):
    serializer_class = AttachmentCreateSerializer
    parser_classes = (MultiPartParser, FormParser)  # Assicurati di avere i parser corretti

    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def post(self, request, ticket_id):
        print("ticket_id", ticket_id)
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        try:
            serializer = self.serializer_class(data=request.data)
            
            if serializer.is_valid():
                attachment = serializer.save(author=request.user)
                ticket.attachments.add(attachment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                print("sono qui")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        

'''
Messages API
'''

class TicketMessageAttachment(APIView):
    serializer_class = AttachmentCreateSerializer
    parser_classes = (MultiPartParser, FormParser)  # Assicurati di avere i parser corretti

    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def post(self, request, message_id):
        message = get_object_or_404(Message, id=message_id)
        
        try:
            serializer = self.serializer_class(data=request.data)
            
            if serializer.is_valid():
                attachment = serializer.save(author=request.user)
                message.attachments.add(attachment)
                return Response({"data":serializer.data, "message":"success"}, status=status.HTTP_201_CREATED)
            else:
                return Response({"data":serializer.errors, "message":"fail"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"detail": str(e), "message":"fail"}, status=status.HTTP_400_BAD_REQUEST)
        


class TicketProjectStatsView(APIView):
    """
    GET /api/projects/<project_id>/tickets/stats/?granularity=month|year&from=YYYY-MM-DD&to=YYYY-MM-DD&fill_gaps=true

    Aggrega i ticket del progetto indicato da <project_id> per mese o per anno.
    Breakdown: status, type, priority. Usa opening_date come riferimento.
    """
    if REMOTE_API == True:
        authentication_classes = [JWTAuthentication]

    def get(self, request, project_id: int):
        tz = timezone.get_current_timezone()
        p = request.query_params

        granularity = (p.get("granularity") or "month").lower()
        if granularity not in ("month", "year"):
            return Response({"detail": "granularity deve essere 'month' o 'year'."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Base queryset: SOLO il progetto richiesto
        qs = Ticket.objects.filter(project_id=project_id)

        # Date opzionali
        def parse_date(v: str):
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except Exception:
                return None

        d_from = parse_date(p.get("from") or "")
        d_to = parse_date(p.get("to") or "")

        if d_from:
            qs = qs.filter(opening_date__date__gte=d_from)
        if d_to:
            qs = qs.filter(opening_date__date__lte=d_to)

        trunc = TruncMonth if granularity == "month" else TruncYear

        aggregated = (
            qs.annotate(period=trunc("opening_date", tzinfo=tz))
              .values("period")
              .annotate(
                  total=Count("id"),
                  # status
                  open_=Count("id", filter=Q(status="open")),
                  in_progress=Count("id", filter=Q(status="in_progress")),
                  resolved=Count("id", filter=Q(status="resolved")),
                  closed=Count("id", filter=Q(status="closed")),
                  # type
                  bug=Count("id", filter=Q(ticket_type="bug")),
                  feature=Count("id", filter=Q(ticket_type="feature")),
                  evo=Count("id", filter=Q(ticket_type="evo")),
                  # priority
                  low=Count("id", filter=Q(priority="low")),
                  medium=Count("id", filter=Q(priority="medium")),
                  high=Count("id", filter=Q(priority="high")),
              )
              .order_by("period")
        )

        rows = list(aggregated)
        if not rows and (p.get("fill_gaps") or "").lower() == "true":
            return Response({
                "project_id": project_id,
                "granularity": granularity,
                "date_range": {"start": d_from.isoformat() if d_from else None,
                               "end": d_to.isoformat() if d_to else None},
                "results": []
            })

        # Mappa periodo -> dati
        data_by_key = {}
        for r in rows:
            per = r["period"]
            if granularity == "month":
                key = per.strftime("%Y-%m")
                per_start = date(per.year, per.month, 1)
            else:
                key = per.strftime("%Y")
                per_start = date(per.year, 1, 1)
            data_by_key[key] = {
                "period": key,
                "period_start": per_start.isoformat(),
                "total": r["total"],
                "by_status": {
                    "open": r["open_"],
                    "in_progress": r["in_progress"],
                    "resolved": r["resolved"],
                    "closed": r["closed"],
                },
                "by_type": {"bug": r["bug"], "feature": r["feature"], "evo": r["evo"]},
                "by_priority": {"low": r["low"], "medium": r["medium"], "high": r["high"]},
            }

        # Gap filling opzionale
        results = []
        fill_gaps = (p.get("fill_gaps") or "").lower() == "true"
        if fill_gaps and data_by_key:
            # start
            if d_from:
                start = d_from
            else:
                first_key = sorted(data_by_key.keys())[0]
                first_dt = datetime.strptime(first_key, "%Y-%m" if granularity == "month" else "%Y").date()
                start = date(first_dt.year, first_dt.month if granularity == "month" else 1, 1)
            # end
            if d_to:
                end = d_to
            else:
                last_key = sorted(data_by_key.keys())[-1]
                last_dt = datetime.strptime(last_key, "%Y-%m" if granularity == "month" else "%Y").date()
                end = date(last_dt.year, last_dt.month if granularity == "month" else 12, 1)

            cur = start.replace(day=1)
            while cur <= end:
                if granularity == "month":
                    key = cur.strftime("%Y-%m")
                    per_start = date(cur.year, cur.month, 1)
                    cur = per_start + relativedelta(months=1)
                else:
                    key = cur.strftime("%Y")
                    per_start = date(cur.year, 1, 1)
                    cur = date(cur.year + 1, 1, 1)

                results.append(data_by_key.get(key, {
                    "period": key,
                    "period_start": per_start.isoformat(),
                    "total": 0,
                    "by_status": {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0},
                    "by_type": {"bug": 0, "feature": 0, "evo": 0},
                    "by_priority": {"low": 0, "medium": 0, "high": 0},
                }))
        else:
            results = [data_by_key[k] for k in sorted(data_by_key.keys())]

        return Response({
            "project_id": project_id,
            "granularity": granularity,
            "date_range": {
                "start": d_from.isoformat() if d_from else (results[0]["period_start"] if results else None),
                "end": d_to.isoformat() if d_to else (results[-1]["period_start"] if results else None),
            },
            "results": results
        }, status=status.HTTP_200_OK)


class ProjectTaskList(APIView):
    if REMOTE_API and JWTAuthentication is not None:
        authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({"detail": "Parametro 'project' obbligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.select_related('client').get(pk=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "Progetto non trovato."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if hasattr(user, "is_at_least_associate") and callable(user.is_at_least_associate) and user.is_at_least_associate():
            pass
        elif project.client_id == getattr(user, "id", None):
            pass
        else:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        tasks = Task.objects.filter(project_id=project_id).select_related('assignee')
        serializer = TaskSerializer(tasks, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        project_id = request.data.get('project') or request.data.get('project_id')
        if not project_id:
            return Response(
                {"detail": "Parametro 'project' o 'project_id' obbligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = Project.objects.select_related('client').get(pk=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "Progetto non trovato."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if hasattr(user, "is_at_least_associate") and callable(user.is_at_least_associate) and user.is_at_least_associate():
            pass
        elif project.client_id == getattr(user, "id", None):
            pass
        else:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if data.get('project_id') and not data.get('project'):
            data['project'] = data.get('project_id')
        elif not data.get('project'):
            data['project'] = project_id

        serializer = TaskCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        task = serializer.save()
        out = TaskSerializer(task)
        return Response(out.data, status=status.HTTP_201_CREATED)


class TaskUpdateView(APIView):
    if REMOTE_API and JWTAuthentication is not None:
        authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            task = Task.objects.select_related('project__client').get(pk=pk)
        except Task.DoesNotExist:
            return Response({"detail": "Task non trovato."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        new_start = request.data.get('start_date')
        new_due = request.data.get('due_date')

        if not any([new_status, new_start, new_due]):
            return Response({"detail": "Nessun campo valido fornito."}, status=status.HTTP_400_BAD_REQUEST)

        updates = {}

        if new_status is not None:
            valid_status = {choice[0] for choice in TASK_STATUS_CHOICES}
            if new_status not in valid_status:
                return Response({"detail": "Status non valido."}, status=status.HTTP_400_BAD_REQUEST)
            updates['status'] = new_status

        from datetime import datetime

        def parse_date(value, field_name):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                raise ValueError(f"Formato data non valido per {field_name}.")

        if new_start is not None:
            try:
                updates['start_date'] = parse_date(new_start, 'start_date')
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if new_due is not None:
            try:
                updates['due_date'] = parse_date(new_due, 'due_date')
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if hasattr(user, "is_at_least_associate") and callable(user.is_at_least_associate) and user.is_at_least_associate():
            pass
        elif task.project.client_id == getattr(user, "id", None):
            pass
        elif task.assignee_id == getattr(user, "id", None):
            pass
        else:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        if 'start_date' in updates and 'due_date' in updates:
            if updates['due_date'] < updates['start_date']:
                return Response({"detail": "La data di fine non può precedere la data di inizio."}, status=status.HTTP_400_BAD_REQUEST)
        elif 'start_date' in updates and task.due_date and task.due_date < updates['start_date']:
            return Response({"detail": "La data di fine non può precedere la data di inizio."}, status=status.HTTP_400_BAD_REQUEST)
        elif 'due_date' in updates and task.start_date and updates['due_date'] < task.start_date:
            return Response({"detail": "La data di fine non può precedere la data di inizio."}, status=status.HTTP_400_BAD_REQUEST)

        for field, value in updates.items():
            setattr(task, field, value)

        update_fields = list(updates.keys()) + ['updated_at']
        task.save(update_fields=update_fields)
        serializer = TaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)
