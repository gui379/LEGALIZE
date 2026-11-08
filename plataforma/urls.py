from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('painel/', views.painel_view, name='painel'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('logout/', views.logout_view, name='logout'),
    path('esqueceu-senha/', views.esqueceu_senha_view, name='esqueceu_senha'),
    path('historico/', views.historico_contratos_view, name='historico_contratos'),
    path('contratos/', views.gerar_contratos_view, name='gerar_contratos'),
    path('analise/', views.analise_clausulas_view, name='analise_clausulas'),
    path('legislacao/', views.consulta_legislativa_view, name='consulta_legislativa'),
    path('assistente/', views.assistente_juridico_view, name='assistente_juridico'),
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),
]