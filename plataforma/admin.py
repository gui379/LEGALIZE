from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, ContratoGerado

class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ['username', 'first_name', 'cpf', 'ocupacao', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Informações Adicionais (Protótipo)', {'fields': ('cpf', 'ocupacao')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informações Adicionais (Protótipo)', {'fields': ('cpf', 'ocupacao', 'first_name')}),
    )

class ContratoGeradoAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'modelo_contrato', 'parte_a', 'parte_b', 'data', 'valor', 'criado_em']
    list_filter = ['modelo_contrato', 'data']
    search_fields = ['parte_a', 'parte_b', 'usuario__username']

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(ContratoGerado, ContratoGeradoAdmin)