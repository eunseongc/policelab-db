import asyncio
from asgiref.sync import async_to_sync
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib import auth
from django.core import serializers
from django.http import HttpResponse, JsonResponse, FileResponse, HttpResponseNotAllowed
from .models import Case
from .models import Video
from .models import Image
from django.forms.models import model_to_dict
import json
import base64
import numpy as np
import os
import logging
from .utils import calc_similarity
from .tasks import query_feature_extraction_async, improve_resolution_async
from django.core.files.base import File, ContentFile
from django.conf import settings

# Create your views here.


logger = logging.getLogger('mylogger')


def encode_image(binary_data):
    return base64.b64encode(binary_data)


def decode_image(base64_data):
    return base64.b64decode(base64_data)


def search_person(request):
    image = request.FILES.get('image')
    video_id = request.POST.get('video_id')

    ### Store original image
    video = Video.objects.get(id=video_id)

    img_obj = Image.objects.create(video=video)
    img_obj.original = File(image, name=image.name)
    img_obj.save()

    ###

    ### Load query feature
    async_to_sync(query_feature_extraction_async)(img_obj.id, str(img_obj.original))

    # img_obj.query_feature가 reload 자동으로 되는지  체크 필요
    img_obj.refresh_from_db()
    query_feature_path = img_obj.query_feature

    query_feature = np.load(os.path.join(settings.MEDIA_ROOT, str(query_feature_path)))
    ###
    ### Search image for all videos
    cases = Case.objects.all()

    result = []
    for case in cases:
        case_id = case.id

        # query_feature_path = query_feature_path_prefix + str(case.id) + query_feature_path_postfix
        # video_path_prefix: '/var/www/data/case/CASE ID/video'
        video_path_prefix = os.path.join('data/case', str(case_id), 'video')
        videos = case.videos

        # Set gallery from video list
        gallery = {}
        for video in videos.all():
            video_id = video.id
            # query_feature_path = query_feature_path_prefix + str(case.id) + query_feature_path_postfix
            # video_path_prefix: '/var/www/data/case/CASE ID/video'
            processed_path = os.path.join(video_path_prefix, str(video_id))
            gallery_path = os.path.join(processed_path, 'gallery', 'gallery.npy')
            crop_path_client = os.path.join(processed_path, 'cropped')
            sub_gallery = np.load(os.path.join(settings.MEDIA_ROOT, gallery_path), allow_pickle=True).item()   # dictionary

            #####
            # key : data/case/CASE ID/video/VIDEO ID/preprocessed/cropped/IMAGE FILE 로 변환
            sub_gallery = {os.path.join(settings.MEDIA_ROOT, crop_path_client, k.split('/')[1]): v for k, v in sub_gallery.items()}
            #####

            gallery.update(sub_gallery)

        # Calculate similarity
        result_dict = calc_similarity(query_feature=query_feature, gallery=gallery)

        for video_id in result_dict:
            crop_result = []

            result_list_video = result_dict[video_id]
            video = Video.objects.get(id=video_id)
            video_path = os.path.join(settings.MEDIA_ROOT, video_path_prefix, str(video_id))
            thumbnail_path = os.path.join(video_path, 'thumbnail.jpg')
            with open(thumbnail_path, 'rb') as f:
                thumbnail64 = encode_image(f.read()).decode('utf-8')

            # read top 5 result images
            for i in range(min(5, len(result_list_video))):
                # file_path_postfix = result_dict[video_name][i][0]
                # file_path = os.path.join(video_path_prefix, str(video.id), file_path_postfix)

                image_file, similarity = result_list_video[i]
                logger.debug(f'image_file: {image_file}')
                gallery_path = os.path.join(video_path, 'gallery')
                with open(os.path.join(gallery_path, 'cropped', os.path.basename(image_file)), 'rb') as data:
                    file_binary = data.read()

                binary_data = encode_image(file_binary)

                image_name = image_file.split('/')[-1]
                second = int(image_name.split('_')[0])

                crop_result.append({"image": binary_data.decode('utf-8'), "time": second, "similarity": str(similarity)})

            res_dict = {}
            res_dict.update(extract_video_info_dict(video))
            res_dict.update(extract_case_info_dict(video.case))
            res_dict["bookmark"] = bookmark_from_video(video)

            result.append({"video": res_dict, "crops": crop_result, "thumbnail64": thumbnail64})
    ###

    ret = {"result": result}

    return JsonResponse(ret, safe=False)


def image_resolution(request):
    image = request.FILES.get('image')                   # BASE64 str of full image
    query_type = request.POST.get('type')               # human, plate
    video_id = request.POST.get('video_id')

    location = None
    if query_type == 'plate':
        location = request.POST.get('location').split(',')  # left top x, y // left bottom x, y // right top x, y // right bottom x, y

    ### Store original image
    video = Video.objects.get(id=video_id)

    img_obj = Image.objects.create(video=video)
    img_obj.original = File(image, name=image.name)
    img_obj.save()
    ###

    ### image resolution
    async_to_sync(improve_resolution_async)(img_obj.id, query_type, location, str(img_obj.original))
    img_obj.refresh_from_db()
    result_img = base64.b64encode(img_obj.improvement.read())
    # logger.error(f'result_img: {result_img}')
    ###

    data = {"result": result_img.decode('utf-8')}

    return JsonResponse(data, safe=False)


def video_list_by_case():
    videos = Video.objects.all()

    result = []
    for video in videos:
        res_dict = {}
        res_dict.update(extract_video_info_dict(video))
        res_dict.update(extract_case_info_dict(video.case))
        res_dict["bookmark"] = bookmark_from_video(video)
        result.append(res_dict)

    return {"result": result}


def extract_video_info_dict(video):
    dict_video = model_to_dict(video)
    dict_video['upload'] = str(dict_video['upload'])
    dict_video['thumbnail'] = str(dict_video['thumbnail'])

    return {"filepath": dict_video["upload"], "video_id": str(dict_video["id"]),
            "video_name": dict_video["name"], "video_date": video.rec_date.strftime('%Y-%m-%d %H:%M:%S+00:00'),
            "video_length": dict_video["length"], "video_size": dict_video["size"]}


def extract_case_info_dict(case):
    dict_case = model_to_dict(case)
    dict_case["qrcode"] = str(dict_case["qrcode"])

    return {"case_name": dict_case["name"], "case_date": str(dict_case["case_date"]),
            "case_loc": dict_case["loc"], "case_info": dict_case["text"]}


def bookmark_from_video(video):
    bookmarks = video.bookmarks.all()
    return [{"sec": bm.sec, "code": bm.code} for bm in bookmarks]


def login(request):
    return JsonResponse(video_list_by_case(), safe=False)


def upload_file(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    print(request.FILES['upload'])
    return JsonResponse({'ok': True})
