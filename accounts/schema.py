import graphene

from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.models import Group
from graphene_django import DjangoObjectType

from app.decorators import login_required, method_decorator
from cases.schema import CaseNode


class UserNode(DjangoObjectType):
    all_cases = graphene.List(CaseNode)

    class Meta:
        model = get_user_model()
        interfaces = (graphene.relay.Node, )
        exclude_fields = ['password']

    def resolve_all_cases(self, *args, **kwargs):
        all_cases = list(self.cases.all())
        for group in self.groups.all():
            all_cases += list(group.cases.all())
        return set(all_cases)


class GroupNode(DjangoObjectType):
    class Meta:
        model = Group
        interfaces = (graphene.relay.Node,)


class Query:
    me = graphene.Field(UserNode)
    groups = graphene.List(GroupNode)

    @method_decorator(login_required)
    def resolve_me(self, info, **args):
        return info.context.user

    def resolve_groups(self, info, **args):
        return Group.objects.all()


class Login(graphene.relay.ClientIDMutation):
    me = graphene.Field(UserNode)

    class Input:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    def mutate_and_get_payload(self, info, **input):
        username = input.get('username')
        password = input.get('password')

        user = authenticate(username=username, password=password)

        if user is not None:
            login(info.context, user)
            return Login(me=user)

        return Login()


class Logout(graphene.relay.ClientIDMutation):
    ok = graphene.Boolean(required=True)

    @method_decorator(login_required)
    def mutate_and_get_payload(self, info, **input):
        logout(info.context)
        return Logout(ok=True)


class Mutation:
    login = Login.Field()
    logout = Logout.Field()
