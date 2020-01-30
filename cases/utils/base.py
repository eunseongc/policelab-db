import os
import torch
import numpy as np

from PIL import Image
from glob import glob
from collections import OrderedDict

from torch.nn.functional import normalize
from torch.utils.data import dataloader
from torchvision import transforms


class Preprocessor(object):
    def __init__(self, dataset, root=None, transform=None):
        super(Preprocessor, self).__init__()
        self.dataset = dataset
        self.root = root
        self.transform = transform

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, indices):
        if isinstance(indices, (tuple, list)):
            return [self._get_single_item(index) for index in indices]
        return self._get_single_item(indices)

    def _get_single_item(self, index):
        fname = self.dataset[index]
        fpath = fname
        if self.root is not None:
            fpath = os.path.join(self.root, fname)
        img = Image.open(fpath).convert('RGB')
        if self.transform is not None:
            img = self.transform(img)
        return img, fname


def to_numpy(tensor):
    if torch.is_tensor(tensor):
        return tensor.cpu().numpy()
    elif type(tensor).__module__ != 'numpy':
        raise ValueError("Cannot convert {} to numpy array".format(
            type(tensor)))
    return tensor


def to_torch(ndarray):
    if type(ndarray).__module__ == 'numpy':
        return torch.from_numpy(ndarray)
    elif not torch.is_tensor(ndarray):
        raise ValueError("Cannot convert {} to torch tensor".format(
            type(ndarray)))
    return ndarray


def extract_cnn_feature(model, inputs):
    model.eval()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    inputs = to_torch(inputs)
    inputs = inputs.to(device)
    outputs = model(inputs)
    if len(outputs) == 1:
        outputs = outputs.data.cpu()
    else:
        outputs = outputs[0].data.cpu()
    return outputs


def extract_query_feature(model, img):
    """
    :param model: MGN model
    :param img: image to extract feature
    :return: feature vector
    """

    test_transform = transforms.Compose([
        transforms.Resize((384, 128), interpolation=3),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])
    ])
    img = test_transform(img).unsqueeze(0)
    feature = extract_cnn_feature(model, img)
    feature = normalize(feature)
    return feature


def video_preprocessing(model, video, batch_size=32, workers=4):
    """
    :param model: MGN model (feature extractor)
    :param video: video name(video directory name)
    :param batch_size: batch size for preprocessing (default: 32)
    :param workers: workers (default: 4)
    :return: input video feature vectors(dict)
    """
    model.eval()

    features = OrderedDict()

    test_transform = transforms.Compose([
        transforms.Resize((384, 128), interpolation=3),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])
    ])
    images_path_list = sorted(glob(os.path.join(video, "cropped") + "/*.jpg"))

    test_loader = dataloader.DataLoader(Preprocessor(images_path_list,
                                                     root=None,
                                                     transform=test_transform),
                                        batch_size=batch_size,
                                        num_workers=workers,
                                        pin_memory=True)

    for i, (imgs, fnames) in enumerate(test_loader):

        outputs = extract_cnn_feature(model, imgs)
        for fname, output in zip(fnames, outputs):
            features[fname] = output

        if (i + 1) % 10 == 0:
            print("\rExtract Features: [{} / {}]".format(
                i + 1, len(test_loader)),
                  end=" ")

    features = \
        torch.cat([features[f].unsqueeze(0) for f in images_path_list], 0)
    features = normalize(features).numpy()

    sub_gallery = {}
    for idx in range(len(images_path_list)):
        image_name = os.path.join(
            video.split('/')[-1], os.path.basename(images_path_list[idx]))
        sub_gallery[image_name] = features[idx]
    np.save(os.path.join(video, 'gallery.npy'), sub_gallery)

    return sub_gallery


def calc_similarity(query_feature, gallery):
    """
    Calculate similarity between query and gallery features
    :param query_feature: query image feature vector (ndarray)
    :param gallery: collection of gallery feature vectors (dict)
    :return: result (dict)
    """
    
    # gallery.npy
    #   key: MOT_2019_02_14_16_58_08_F/0008_0000005.jpg
    #   value: 2048-dim feature vector
    
    nns = []
    result = dict([])
    
    # needs refactoring
    for idx, key in enumerate(gallery):
        nns.append((np.multiply(query_feature, gallery.get(key)).sum(), key))
    nns = sorted(nns, reverse=True)

    # key : data/case/CASE ID/video/VIDEO ID/preprocessed/cropped/IMAGE FILE
    for similarity, image_file in nns:
        # image_file : data/case/CASE ID/video/VIDEO ID/preprocessed/cropped/IMAGE FILE
        video_id = image_file.split('/')[4]
        
        # file_name_array = image_file.split('/')
        # video_name = file_name_array[0]
        # image_name = file_name_array[1]
        
        # image_file = '{}/cropped/{}'.format(video_name, image_name)

        if video_id not in result.keys():
            result[video_id] = [(image_file, similarity)]

        else:
            result[video_id].append((image_file, similarity))

    return result
