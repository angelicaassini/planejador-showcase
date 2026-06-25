# Trecho curado do Planejador (repositório privado)
# Origem: backend/apps/core/mixins.py
#
# O "coração" do multi-tenant: TODA ViewSet que herda este mixin passa a
# filtrar automaticamente os dados pelo salão (tenant) do usuário logado e
# injeta o tenant ao criar registros. Isolamento por construção — nenhum
# salão enxerga dados de outro, sem repetir `filter(tenant=...)` em cada view.

from rest_framework.exceptions import PermissionDenied


class TenantFilterMixin:
    """
    Mixin para ViewSets/Generics que garante isolamento por tenant.

    - `get_queryset` filtra automaticamente pelo tenant do usuário autenticado.
    - `perform_create` injeta o tenant ao criar novos registros.

    Usuários sem tenant (ex.: SAAS_ADMIN) recebem queryset vazio aqui e são
    barrados na criação com um 403 claro; endpoints administrativos tratam o
    acesso global separadamente.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, 'tenant_id', None):
            return queryset.filter(tenant=user.tenant)
        return queryset.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant is None:
            raise PermissionDenied(
                'Sua conta não está vinculada a um negócio. Faça login como '
                'administrador de um negócio para criar este registro.'
            )
        serializer.save(tenant=tenant)
