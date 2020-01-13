import functools
import json

from graphene_django.settings import graphene_settings
from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.exceptions import StopConsumer
from rx.subjects import Subject

from graphene_subscriptions.events import SubscriptionEvent

stream = Subject()


# GraphQL types might use info.context.user to access currently authenticated user.
# When Query is called, info.context is request object,
# however when Subscription is called, info.context is scope dict.
# This is minimal wrapper around dict to mimic object behavior.
class AttrDict:
    def __init__(self, data):
        self.data = data or {}

    def __getattr__(self, item):
        return self.get(item)

    def get(self, item):
        return self.data.get(item)


class GraphqlSubscriptionConsumer(SyncConsumer):
    def websocket_connect(self, message):
        async_to_sync(self.channel_layer.group_add)("subscriptions",
                                                    self.channel_name)

        self.send({"type": "websocket.accept", "subprotocol": "graphql-ws"})

    def websocket_disconnect(self, message):
        self.send({"type": "websocket.close", "code": 1000})
        self.dispose()
        raise StopConsumer()

    def websocket_receive(self, message):
        request = json.loads(message["text"])
        id = request.get("id")

        if request["type"] == "connection_init":
            return

        elif request["type"] == "start":
            payload = request["payload"]
            context = AttrDict(self.scope)

            schema = graphene_settings.SCHEMA

            result = schema.execute(
                payload["query"],
                operation_name=payload.get("operationName"),
                variables=payload.get("variables"),
                context=context,
                root=stream,
                allow_subscriptions=True,
            )

            if hasattr(result, "subscribe"):
                self.disposable = result.subscribe(
                    functools.partial(self._send_result, id),
                    on_completed=functools.partial(self._send_complete, id))
            else:
                self._send_result(id, result)

        elif request["type"] == "stop":
            self.dispose()

    def signal_fired(self, message):
        stream.on_next(SubscriptionEvent.from_dict(message["event"]))

    def _send_result(self, id, result):
        errors = result.errors

        text = {
            "id": id,
            "type": "data",
            "payload": {
                "data": result.data,
            },
        }

        if errors:
            text["payload"]["errors"] = list(map(str, errors))

        self.send({
            "type": "websocket.send",
            "text": json.dumps(text),
        })

    def _send_complete(self, id):
        self.send({
            "type": "websocket.send",
            "text": json.dumps({
                "id": id,
                "type": "complete",
            })
        })

    def dispose(self):
        if getattr(self, "disposable", None) is not None:
            self.disposable.dispose()
            self.disposable = None
