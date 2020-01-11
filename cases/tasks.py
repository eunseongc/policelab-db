import asyncio
import json
import websockets

from asgiref.sync import sync_to_async
from celery import shared_task

from django.db import close_old_connections
from django.conf import settings

from .models import Video


@shared_task
def create_gallery(video_id):
    print('create_gallery')
    # asyncio.get_event_loop().run_until_complete(create_gallery_async(video_id))


async def create_gallery_async(video_id):
    async with websockets.connect(settings.WEBSOCKET_SERVER) as websocket:
        data = {
            'action': 'create_gallery',
            'video': {
                'id': video_id,
                'path': 'data/case/3/video/1/SampleVideo_1280x720_2mb.mp4',
            },
        }

        # data = {
        #     'action': 'image_resolution',
        #     'type': 'human',  # ['human', 'vehicle_registration_plate']
        #     'image': {
        #         'id': 10,
        #         'path': 'data/case/3/video/1/image/10/image.jpg',
        #     },
        # }
        await websocket.send(json.dumps(data))
        response = json.loads(await websocket.recv())

    if response['ok']:
        await sync_to_async(close_old_connections)()
        video = await sync_to_async(Video.objects.get)(id=response['video_id'])

        video.is_preprocessed = True
        await sync_to_async(video.save)()
