import graphene

import accounts.schema


class Query(graphene.ObjectType, accounts.schema.Query):
    node = graphene.relay.Node.Field()


class Mutation(graphene.ObjectType, accounts.schema.Mutation):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
