import os
import asyncio
import json
import websockets
import logging

from asgiref.sync import sync_to_async
from celery import shared_task

from django.core.files.base import File
from django.db import close_old_connections
from django.conf import settings

from .models import Video, Image


logger = logging.getLogger('mylogger')


@shared_task
def create_gallery(video_id):
    logger.info('action: create_gallery')
    video = Video.objects.get(id=video_id)
    path = str(video.upload)
    asyncio.get_event_loop().run_until_complete(create_gallery_async(video_id, path))


@shared_task
def improve_resolution(image_id, obj_type, location):
    logger.info('action: improve_resolution')
    image = Image.objects.get(id=image_id)
    path = str(image.original)
    asyncio.get_event_loop().run_until_complete(
        improve_resolution_async(image_id, obj_type, location, path),
    )


@shared_task
def query_feature_extraction(image_id):
    logger.info('action: query_feature_extraction')
    image = Image.objects.get(id=image_id)
    path = str(image.original)
    asyncio.get_event_loop().run_until_complete(
        query_feature_extraction_async(image_id, path),
    )


async def create_gallery_async(video_id, path):
    async with websockets.connect(**settings.WEBSOCKET_SERVER) as websocket:
        data = {
            'action': 'create_gallery',
            'video': {
                'id': video_id,
                'path': path,
            },
        }

        await websocket.send(json.dumps(data))
        response = json.loads(await websocket.recv())

    if response['ok']:
        await sync_to_async(close_old_connections)()
        video = await sync_to_async(Video.objects.get)(id=response['video_id'])

        video.is_preprocessed = True

        await sync_to_async(close_old_connections)()
        await sync_to_async(video.save)()


async def query_feature_extraction_async(case_id, query_img, videos):
    async with websockets.connect(**settings.WEBSOCKET_SERVER) as websocket:
        data = {
            'action': 'query_feature',
            'case_id': case_id,
            'query_img': query_img,
            'videos': videos,
        }

        logger.debug(f'data: {data}')

        await websocket.send(json.dumps(data))
        response = json.loads(await websocket.recv())

        logger.debug(f'response: {response}')

    if response['ok']:
        # await sync_to_async(close_old_connections)()
        # image = await sync_to_async(Image.objects.get)(id=image_id)

        # query_path = os.path.join(settings.MEDIA_ROOT, response['path'])
        # image.query_feature = File(open(query_path, 'rb'), name=os.path.basename(query_path))

        # await sync_to_async(close_old_connections)()
        # await sync_to_async(image.save)()

        return response['results']

    raise Exception("query feature")


async def improve_resolution_async(image_id, obj_type, location, path):
    async with websockets.connect(**settings.WEBSOCKET_SERVER) as websocket:
        if obj_type == 'human':
            data = {
                'action': 'super_resolution',
                'type': obj_type,
                'image': {
                    'id': image_id,
                    'path': path,
                },
            }

        else:
            data = {
                'action': 'super_resolution',
                'type': obj_type,
                'image': {
                    'id': image_id,
                    'location': location,
                    'path': path,
                },
            }

        await websocket.send(json.dumps(data))
        response = json.loads(await websocket.recv())

    logger.debug(f'response {response}')

    if response['ok']:
        await sync_to_async(close_old_connections)()
        image = await sync_to_async(Image.objects.get)(id=response['image_id'])

        image_path = os.path.join(settings.MEDIA_ROOT, response['path'])

        image.improvement = File(open(image_path, 'rb'), name=os.path.basename(image_path))

        await sync_to_async(close_old_connections)()
        await sync_to_async(image.save)()
