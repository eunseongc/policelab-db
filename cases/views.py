from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib import auth
from django.core import serializers
from django.http import HttpResponse, JsonResponse, FileResponse
from .models import Case
from .models import Video
from django.forms.models import model_to_dict
import json
import base64
import numpy as np
import os
from .utils import calc_similarity
# Create your views here.


def encode_image(binary_data):
    return base64.b64encode(binary_data)


def decode_image(base64_data):
    return base64.b64decode(base64_data)


def search_person(request):
    """
    image = request.POST.get('image')
    videos = Video.objects.all()

    binary_image = decode_image(image)
    """
    
    query_feature_path = '/var/www/data/case/1/video/info/sample_query_feature.npy'
    video_path_prefix = '/var/www/data/case/1/video/info/gallery/'

    # query_feature_path = r'C:\Users\dmlab\Desktop\TEST\sample_query_feature.npy'
    # video_path_prefix = r'C:\Users\dmlab\Desktop\TEST\gallery'

    gallery_video_list = ['A_park_0', 'A_road_0', 'A_street_0']

    """
    for video in videos:
    video_path = video.upload.split('/')[-1]
    gallery_video_list.append(video_path)

    # Calculate query_feature_vector

    # Calculate video.npy

    # 이후, 동적 입력에 작동하도록 수정 -> VC lab. 요청
    """

    # Load query feature
    query_feature = np.load(query_feature_path)

    # Set gallery from video list
    gallery = {}

    result = []
    for i, video in enumerate(gallery_video_list):
        gallery_path = os.path.join(video_path_prefix, video, 'gallery.npy')
        sub_gallery = np.load(gallery_path, allow_pickle=True).item()

        gallery.update(sub_gallery.items())

    # Calculate similarity
    result_dict = calc_similarity(query_feature=query_feature, gallery=gallery)

    video = Video.objects.first()

    for key in result_dict.keys():
        crop_result = []
        for i in range(5):
            file_path = video_path_prefix
            crop_path_array = result_dict[key][i].split('/')[3:-1]
        
            for path_element in crop_path_array:
                file_path += path_element + "/"
            file_path += result_dict[key][i].split('/')[-1]

            with open(file_path, 'rb') as data:
                file_binary = data.read()
                binary_data = encode_image(file_binary)
                crop_result.append({"image": str(binary_data), "time": 12.3, "similarity": 0.7})

        result.append({"filepath": str(video.upload), "crops": crop_result})

    return JsonResponse(result, safe=False)


def image_resolution(request):
    image = request.POST.get('image')

    binary_image = decode_image(image)

    # resolution function
    result_image = encode_image(binary_image)

    data = {"result": str(result_image)}

    return JsonResponse(data, safe=False)


def video_list_by_case():
    videos = Video.objects.all()

    result = []
    for video in videos:
        dict_video = model_to_dict(video)
        dict_video["upload"] = str(dict_video["upload"])
        dict_case = model_to_dict(video.case)
        dict_case["qrcode"] = str(dict_case["qrcode"])

        bookmarks = video.bookmarks.all()
        bookmark_result = []

        for bookmark in bookmarks:
            bookmark_result.append({"sec": bookmark.sec, "code": bookmark.code})

        result.append({"filepath": dict_video["upload"], "video_id": str(dict_video["id"]),
                        "video_name": dict_video["name"], "video_date": str(video.uploaded_at),
                        "video_length": dict_video["length"], "video_size": dict_video["size"],
                        "case_name": dict_case["name"], "case_date": str(video.case.created_at),
                        "case_loc": dict_case["loc"], "case_info": dict_case["text"],
                        "bookmark": bookmark_result
                        })

    return {"result": result}


def login(request):
    return JsonResponse(video_list_by_case(), safe=False)
