import graphene


class LocationInput(graphene.InputObjectType):
    latitude = graphene.Float(required=True)
    longitude = graphene.Float(required=True)


class LocationType(graphene.ObjectType):
    latitude = graphene.Float(required=True)
    longitude = graphene.Float(required=True)
