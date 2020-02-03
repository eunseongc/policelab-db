import os
import asyncio
import json

import graphene
import qrcode

import numpy as np

from asgiref.sync import async_to_sync

from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile, File
from django.contrib.gis.geos import Point

from graphql_relay import from_global_id, to_global_id

from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene_file_upload.scalars import Upload
from graphene_subscriptions.events import UPDATED, CREATED

from app.decorators import login_required, method_decorator
from app.exceptions import InvalidInputError

from .models import Case, Video, Image
from .types import LocationType, LocationInput
from .tasks import create_gallery, improve_resolution_async, query_feature_extraction_async
from .utils import generate_thumbnail, calc_similarity


class CaseNode(DjangoObjectType):
    class Meta:
        model = Case
        interfaces = (graphene.relay.Node, )
        filter_fields = ['token']

    def resolve_qrcode(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.qrcode)


class VideoNode(DjangoObjectType):
    location = graphene.Field(LocationType)

    class Meta:
        model = Video
        interfaces = (graphene.relay.Node, )
        filter_fields = []
        exclude_fields = ['location']

    def resolve_upload(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.upload)

    def resolve_thumbnail(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.thumbnail)

    def resolve_location(self, *args, **kwargs):
        if self.location:
            return LocationType(latitude=self.location.y,
                                longitude=self.location.x)
        return None


class ImageNode(DjangoObjectType):
    class Meta:
        model = Image
        interfaces = (graphene.relay.Node, )
        filter_fields = []

    def resolve_original(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.original)

    def resolve_improvement(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.improvement)


class Query:
    case = graphene.Field(CaseNode, token=graphene.String(required=True))
    videos = DjangoFilterConnectionField(VideoNode)

    def resolve_case(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
            return case
        except Case.DoesNotExist:
            return None


class CreateCase(graphene.relay.ClientIDMutation):
    case = graphene.Field(CaseNode)

    class Input:
        name = graphene.String(required=True)
        text = graphene.String(required=True)

    @method_decorator(login_required)
    def mutate_and_get_payload(self, info, **input):
        name = input.get('name')
        text = input.get('text')
        token = get_random_string(length=16)

        qr_img = qrcode.make(settings.WEB_URL_PREFIX +
                             'case/upload/{}'.format(token))

        f = BytesIO()
        qr_img.save(f, format='png')

        case = Case.objects.create(
            name=name,
            text=text,
            token=token,
        )

        case.qrcode.save(token + '.png', ContentFile(f.getvalue()))
        case.members.set([info.context.user])

        f.close()

        return CreateCase(case=case)


class UploadVideo(graphene.relay.ClientIDMutation):
    video = graphene.Field(VideoNode, required=True)

    class Input:
        token = graphene.String(required=True)
        location = graphene.Field(LocationInput)
        rec_date = graphene.DateTime()
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
        except Case.DoesNotExist:
            raise InvalidInputError(message=_('invalid token'))

        if case.is_expired:
            raise InvalidInputError(message=_('token is expired'))

        video = Video.objects.create(case=case)
        ext = input.get('upload').name.rpartition('.')[-1]
        video_name = 'video.' + ext
        video.upload = File(input.get('upload'), name=video_name)

        location = input.get('location')
        rec_date = input.get('rec_date')

        if location:
            point = Point(location.longitude, location.latitude, srid=4326)
            video.location = point

        if rec_date is None:
            rec_date = datetime.now()

        video.rec_date = rec_date

        thumbnail_name = 'thumbnail.jpg'
        in_filename = input.get('upload').file.name
        out_filename = os.path.join(os.path.dirname(in_filename),
                                    thumbnail_name)

        generate_thumbnail(in_filename, out_filename, 0, 512)

        video.thumbnail = File(open(out_filename, 'rb'), name=thumbnail_name)

        video.save()

        create_gallery.delay(video.id)

        return UploadVideo(video=video)


class SuperResolution(graphene.relay.ClientIDMutation):
    image = graphene.Field(ImageNode, required=True)

    class Input:
        video_id = graphene.ID(required=True)
        image_type = graphene.String(required=True)
        points = graphene.List(graphene.Int)
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        video_id = int(from_global_id(input.get('video_id'))[1])
        image_type = input.get('image_type')
        upload = input.get('upload')
        points = input.get('points')

        video = Video.objects.get(id=video_id)

        img = Image.objects.create(video=video)
        img.original = File(upload, name='image.jpg')
        img.save()

        async_to_sync(improve_resolution_async)(img.id, image_type, points, str(img.original))
        img.refresh_from_db()

        return SuperResolution(image=img)


class SearchPerson(graphene.relay.ClientIDMutation):
    result = graphene.JSONString()

    class Input:
        video_id = graphene.ID(required=True)
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        video_id = int(from_global_id(input.get('video_id'))[1])
        image = input.get('upload')

        video = Video.objects.get(id=video_id)

        img = Image.objects.create(video=video)
        img.original = File(image, name='image.jpg')
        img.save()

        async_to_sync(query_feature_extraction_async)(img.id, str(img.original))

        img.refresh_from_db()

        query_feature = np.load(os.path.join(settings.MEDIA_ROOT, str(img.query_feature)))

        result = []
        gallery = {}
        for video in Video.objects.all():
            video_dir = os.path.dirname(os.path.join(settings.MEDIA_ROOT, str(video.upload)))
            crop_dir = os.path.join(video_dir, 'gallery', 'cropped')
            gallery_path = os.path.join(video_dir, 'gallery', 'gallery.npy')

            if not os.path.exists(gallery_path):
                continue

            sub_gallery = np.load(gallery_path, allow_pickle=True).item()
            sub_gallery = {os.path.join(crop_dir, k.split('/')[1]): v for k, v in sub_gallery.items()}

            gallery.update(sub_gallery)

        for video_id, videos in calc_similarity(query_feature=query_feature, gallery=gallery).items():
            crop_results = []

            for i in range(min(5, len(videos))):
                image, similarity = videos[i]
                crop_results.append({'image': image.replace('/var/www/', settings.SERVER_URL_PREFIX), 'similarity': similarity.item()})

            video = Video.objects.get(id=video_id)
            thumbnail = settings.SERVER_URL_PREFIX + str(video.thumbnail)

            result.append({'video_id': to_global_id(VideoNode.__name__, video_id), 'thumbnail': thumbnail, 'crop': crop_results})

        return SearchPerson(result=json.dumps(result))


class Mutation:
    create_case = CreateCase.Field()
    upload_video = UploadVideo.Field()
    super_resolution = SuperResolution.Field()
    search_person = SearchPerson.Field()


class Subscription:
    case_video = graphene.Field(CaseNode, id=graphene.ID(required=True))

    @method_decorator(login_required)
    def resolve_case_video(root, info, **input):
        _id = int(from_global_id(input.get('id'))[1])

        return root.filter(
            lambda event: event.operation in [UPDATED, CREATED] and isinstance(
                event.instance, Video) and event.instance.case.id == _id).map(
                    lambda _: Case.objects.get(id=_id))
