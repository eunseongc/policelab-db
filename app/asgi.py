import os
import django

from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from graphene_subscriptions.consumers import GraphqlSubscriptionConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')


def get_asgi_application():
    django.setup(set_prefix=False)

    from channels.auth import AuthMiddlewareStack

    return ProtocolTypeRouter({
        'websocket':
        AuthMiddlewareStack(
            URLRouter([re_path(r'^graphql/?$', GraphqlSubscriptionConsumer)])),
    })


application = get_asgi_application()
