import os
import asyncio
import json

import graphene
import qrcode

import numpy as np

from collections import OrderedDict
from asgiref.sync import async_to_sync

from io import BytesIO

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile, File
from django.contrib.gis.geos import Point
from django.contrib.auth.models import Group

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
    bookmark = graphene.JSONString(video_id=graphene.ID(required=True))

    def resolve_case(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
            return case
        except Case.DoesNotExist:
            return None

    def resolve_bookmark(self, info, **input):
        video_id = int(from_global_id(input.get('video_id'))[1])

        video = Video.objects.get(id=video_id)
        summary_path = os.path.join(
                settings.MEDIA_ROOT,
                os.path.dirname(str(video.upload)),
                'gallery', 'summary.json',
        )

        with open(summary_path, 'r', encoding='utf8') as f:
            summary = json.load(f)

        bookmark = []
        for frame, content in summary.items():
            if not content['key_frame']:
                continue

            if isinstance(content['content'], list):
                new_content = content['content']
            else:
                new_content = [content['content']]

            second = int(frame.split('_')[-1].split('.')[0])
            bookmark.append({'time': second, 'content': new_content})

        # bookmark shape
        # [
        #   {'time': 1, 'content': ['person', 'truck', 'car']},
        #   {'time': 2, 'content': ['person']},
        # ]

        # content_time shape
        # {
        #   'person': [1, 2, ...],
        #   'truck': [1, ...],
        #   'car': [1, ...],
        # }

        content_time = {}
        for item in bookmark:
            for content in item['content']:
                if content not in content_time:
                    content_time[content] = []
                content_time[content].append(item['time'])

        # Remove consecutive time
        summary_content_time = {}
        for content, time_list in content_time.items():
            summary_time = []
            con = -1

            for time in time_list:
                if con + 1 != time:
                    summary_time.append(time)
                    con = time
                    continue
                con += 1

            summary_content_time[content] = summary_time

        # grouping content by time
        # {
        #   1: ['person', 'truck', 'car'],
        #   2: ['person'],
        # }
        group_content_time = OrderedDict()
        for content, time_list in summary_content_time.items():
            for time in time_list:
                if time not in group_content_time:
                    group_content_time[time] = []
                group_content_time[time].append(content)
        group_content_time = OrderedDict(sorted(group_content_time.items(), key=lambda item: item[0]))

        bookmark = []
        for time, content_list in group_content_time.items():
            bookmark.append({'time': time, 'content': content_list})

        return json.dumps(bookmark)


class CreateCase(graphene.relay.ClientIDMutation):
    case = graphene.Field(CaseNode)

    class Input:
        name = graphene.String(required=True)
        text = graphene.String(required=True)
        group_id = graphene.ID()

    @method_decorator(login_required)
    def mutate_and_get_payload(self, info, **input):
        name = input.get('name')
        text = input.get('text')
        token = get_random_string(length=16)

        group_id = input.get('group_id')
        group_id = int(from_global_id(group_id)[1]) if group_id else None
        group = Group.objects.get(id=group_id) if group_id else None

        qr_img = qrcode.make(settings.WEB_URL_PREFIX +
                             'case/upload/{}'.format(token))

        f = BytesIO()
        qr_img.save(f, format='png')

        case = Case.objects.create(
            name=name,
            text=text,
            token=token,
            group=group,
        )

        case.qrcode.save(token + '.png', ContentFile(f.getvalue()))
        case.members.set([info.context.user])

        f.close()

        return CreateCase(case=case)


def upload_video(id_type, params):
    if id_type == 'token':
        try:
            case = Case.objects.get(token=params.get('token'))
        except Case.DoesNotExist:
            raise InvalidInputError(message=_('invalid token'))

        if case.is_expired:
            raise InvalidInputError(message=_('token is expired'))

    elif id_type == 'id':
        case_id = int(from_global_id(params.get('case_id')[1]))
        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            raise InvalidInputError(message=_('case id is invalid'))

    else:
        raise ValueError("id_type is invalid (must be 'token' or 'id')")

    location = params.get('location')
    rec_date = params.get('rec_date')
    original_date = params.get('original_date')

    if rec_date is None:
        rec_date = timezone.now()

    video = Video.objects.create(case=case)
    ext = params.get('upload').name.rpartition('.')[-1]
    video_name = rec_date.strftime("%Y-%m-%d_%H:%M") + '.' + ext
    video.upload = File(params.get('upload'), name=video_name)

    if location:
        point = Point(location.longitude, location.latitude, srid=4326)
        video.location = point

    video.rec_date = rec_date
    video.original_date = original_date

    thumbnail_name = 'thumbnail.jpg'
    in_filename = params.get('upload').file.name
    out_filename = os.path.join(os.path.dirname(in_filename),
                                thumbnail_name)

    generate_thumbnail(in_filename, out_filename, 0, 512)

    video.thumbnail = File(open(out_filename, 'rb'), name=thumbnail_name)

    video.save()

    create_gallery.delay(video.id)

    return UploadVideo(video=video)



class UploadVideo(graphene.relay.ClientIDMutation):
    video = graphene.Field(VideoNode, required=True)

    class Input:
        token = graphene.String(required=True)
        location = graphene.Field(LocationInput)
        rec_date = graphene.DateTime()
        original_date = graphene.DateTime()
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        return upload_video('token', input)


class UploadVideoByID(graphene.relay.ClientIDMutation):
    video = graphene.Field(VideoNode, required=True)

    class Input:
        case_id = graphene.ID(required=True)
        location = graphene.Field(LocationInput)
        rec_date = graphene.DateTime()
        original_date = graphene.DateTime()
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        return upload_video('id', input)


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
        img.original = File(upload, name='image.png')
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
        img.original = File(image, name='image.png')
        img.save()

        async_to_sync(query_feature_extraction_async)(img.id, str(img.original))

        img.refresh_from_db()

        query_feature = np.load(os.path.join(settings.MEDIA_ROOT, str(img.query_feature)))

        result = []
        gallery = {}
        for video in video.case.videos.all():
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
                time = int(os.path.basename(image).partition('_')[0])

                if similarity <= 0.3:
                    continue

                crop_results.append({
                    'image': image.replace('/var/www/', settings.SERVER_URL_PREFIX),
                    'time': time,
                    'similarity': similarity.item(),
               })

            video = Video.objects.get(id=video_id)
            thumbnail = settings.SERVER_URL_PREFIX + str(video.thumbnail)

            if len(crop_results) == 0:
                continue

            result.append({
                'video_id': to_global_id(VideoNode.__name__, video_id),
                'thumbnail': thumbnail,
                'crop': crop_results,
            })

        return SearchPerson(result=json.dumps(result))


class Mutation:
    create_case = CreateCase.Field()
    upload_video = UploadVideo.Field()
    upload_video_by_id = UploadVideoByID.Field()
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
