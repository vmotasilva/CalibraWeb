# -*- coding: utf-8 -*-
"""
Serializers para o Módulo de Diagramas / Fluxogramas
Validação de Schema JSON xyflow e Auto-Save
"""

from rest_framework import serializers
from .models_diagram import Diagrama, DiagramaVersao, StatusDiagrama


class TopologiaPayloadSerializer(serializers.Serializer):
    """Validador do payload JSON gerado pelo editor de fluxograma (xyflow)."""
    nodes = serializers.ListField(child=serializers.DictField(), required=True)
    edges = serializers.ListField(child=serializers.DictField(), required=True)
    grid_data = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    viewport = serializers.DictField(required=False, default=dict)

    def validate_nodes(self, nodes):
        for node in nodes:
            if not isinstance(node, dict):
                raise serializers.ValidationError("Cada nó deve ser um objeto JSON.")
            if 'id' not in node or 'position' not in node:
                raise serializers.ValidationError(f"Nó sem ID ou position obrigatórios: {node.get('id')}")
            pos = node.get('position', {})
            if not (isinstance(pos.get('x'), (int, float)) and isinstance(pos.get('y'), (int, float))):
                raise serializers.ValidationError(f"Coordenadas x/y inválidas no nó ID: {node.get('id')}")
        return nodes

    def validate_edges(self, edges):
        for edge in edges:
            if not isinstance(edge, dict):
                raise serializers.ValidationError("Cada aresta deve ser um objeto JSON.")
            if not all(k in edge for k in ('id', 'source', 'target')):
                raise serializers.ValidationError(f"Aresta inválida (requer id, source, target): {edge.get('id')}")
        return edges


class DiagramaVersaoAutoSaveSerializer(serializers.ModelSerializer):
    """Serializer otimizado para o endpoint PATCH de auto-save."""
    dados_topologia = TopologiaPayloadSerializer()

    class Meta:
        model = DiagramaVersao
        fields = ['dados_topologia']

    def update(self, instance, validated_data):
        instance.dados_topologia = validated_data.get('dados_topologia', instance.dados_topologia)
        # Grava apenas o JSONField no banco para economia de I/O
        instance.save(update_fields=['dados_topologia', 'atualizado_em'])
        return instance


class DiagramaVersaoDetailSerializer(serializers.ModelSerializer):
    """Serializer de leitura completa de versão e status QMS."""
    aprovado_por_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DiagramaVersao
        fields = [
            'id', 'diagrama', 'revisao', 'status', 'status_display',
            'dados_topologia', 'motivo_revisao', 'aprovado_por',
            'aprovado_por_nome', 'data_aprovacao', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['id', 'revisao', 'criado_em', 'atualizado_em']

    def get_aprovado_por_nome(self, obj):
        if obj.aprovado_por:
            return obj.aprovado_por.get_full_name() or obj.aprovado_por.username
        return None


class DiagramaSerializer(serializers.ModelSerializer):
    """Serializer completo de cabeçalho do fluxograma."""
    versoes = DiagramaVersaoDetailSerializer(many=True, read_only=True)
    criado_por_nome = serializers.SerializerMethodField()
    versao_vigente = DiagramaVersaoDetailSerializer(read_only=True)

    class Meta:
        model = Diagrama
        fields = [
            'id', 'codigo', 'titulo', 'departamento', 'matriz_procedimento',
            'procedimento', 'descricao', 'criado_por', 'criado_por_nome',
            'ativo', 'criado_em', 'atualizado_em', 'versao_vigente', 'versoes'
        ]
        read_only_fields = ['id', 'criado_por', 'criado_em', 'atualizado_em']

    def get_criado_por_nome(self, obj):
        if obj.criado_por:
            return obj.criado_por.get_full_name() or obj.criado_por.username
        return None
