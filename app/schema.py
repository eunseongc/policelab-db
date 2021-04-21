import graphene

import accounts.schema
import cases.schema


class Query(
    graphene.ObjectType,
    accounts.schema.Query,
    cases.schema.Query,
):
    node = graphene.relay.Node.Field()


class Mutation(
    graphene.ObjectType,
    accounts.schema.Mutation,
    cases.schema.Mutation,
):
    pass


class Subscription(
    graphene.ObjectType,
    cases.schema.Subscription,
):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation, subscription=Subscription)