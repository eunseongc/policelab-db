import os
import asyncio
import json
import websockets

from asgiref.sync import sync_to_async
from celery import shared_task

from django.core.files.base import File
from django.db import close_old_connections
from django.conf import settings

from .models import Video, Image


@shared_task
def create_gallery(video_id):
    print('create_gallery')
    video = Video.objects.get(id=video_id)
    path = str(video.upload)
    asyncio.get_event_loop().run_until_complete(create_gallery_async(video_id, path))


@shared_task
def improve_resolution(image_id, obj_type, location):
    print('improve_resolution')
    image = Image.objects.get(id=image_id)
    path = str(image.original)
    asyncio.get_event_loop().run_until_complete(
        improve_resolution_async(image_id, obj_type, location, path),
    )


async def create_gallery_async(video_id, path):
    async with websockets.connect(settings.WEBSOCKET_SERVER) as websocket:
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
        await sync_to_async(video.save)()


async def improve_resolution_async(image_id, obj_type, location, path):
    async with websockets.connect(settings.WEBSOCKET_SERVER) as websocket:
        data = {
            'action': 'improve_resolution',
            'type': obj_type,
            'image': {
                'id': image_id,
                'location': location,
                'path': path,
            },
        }

        await websocket.send(json.dumps(data))
        response = json.loads(await websocket.recv())

    if response['ok']:
        await sync_to_async(close_old_connections)()
        image = await sync_to_async(Image.objects.get)(id=response['image_id'])

        image_path = os.path.join(settings.MEDIA_ROOT, response['path'])
        image.improvement = File(open(image_path, 'rb'), name='improvement.jpg')

        await sync_to_async(image.save)()
