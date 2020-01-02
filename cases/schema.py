import graphene

from graphene_django import DjangoObjectType
# from graphene_django.filter import DjangoFilterConnectionField

from .models import Case, Video


class CaseNode(DjangoObjectType):
    class Meta:
        model = Case
        interfaces = (graphene.relay.Node, )
        filter_fields = ['token']


class VideoNode(DjangoObjectType):
    class Meta:
        model = Video
        interfaces = (graphene.relay.Node, )
        filter_fields = []


class Query:
    pass


class Mutation:
    pass
