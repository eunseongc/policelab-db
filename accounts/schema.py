import graphene

from django.contrib.auth import get_user_model, authenticate, login, logout
from graphene_django import DjangoObjectType

from app.decorators import login_required, method_decorator


class UserNode(DjangoObjectType):
    class Meta:
        model = get_user_model()
        interfaces = (graphene.relay.Node, )
        exclude_fields = ['password']


class Query:
    me = graphene.Field(UserNode)

    @method_decorator(login_required)
    def resolve_me(self, info, **args):
        return info.context.user


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
    state = graphene.Boolean(required=True)

    @method_decorator(login_required)
    def mutate_and_get_payload(self, info, **input):
        logout(info.context)
        return Logout(state=True)


class Mutation:
    login = Login.Field()
    logout = Logout.Field()
