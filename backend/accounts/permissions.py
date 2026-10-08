from rest_framework.permissions import BasePermission

class ActionModelPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        model = view.queryset.model
        action = {'list': 'view', 'retrieve': 'view', 'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete', 'export': 'export', 'retry_notification': 'retry', 'approve': 'change', 'reject': 'change'}.get(view.action)
        return bool(action and user.has_perm(f'{model._meta.app_label}.{action}_{model._meta.model_name}'))
