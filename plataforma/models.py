from django.db import models
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    ocupacao = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.username


class ContratoGerado(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    modelo_contrato = models.CharField(max_length=100)
    sub_segmento = models.CharField(max_length=100, null=True, blank=True)
    numero_contrato = models.CharField(max_length=20, null=True, blank=True)
    ano_contrato = models.CharField(max_length=4, null=True, blank=True)
    parte_a = models.CharField(max_length=150)
    parte_b = models.CharField(max_length=150)
    data = models.DateField()
    data_termino = models.DateField(null=True, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    clausulas_adicionais = models.TextField(blank=True, null=True)
    dados_estruturados_json = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    is_deletado = models.BooleanField(default=False)
    deletado_em = models.DateField(null=True, blank=True)
    justificativa_exclusao = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Contrato {self.numero_contrato}/{self.ano_contrato} - {self.parte_a} vs {self.parte_b}"


class ClausulaFavorita(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=100)
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo