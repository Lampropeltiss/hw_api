import requests
import json
import configparser
from datetime import datetime
from tqdm import tqdm

config = configparser.ConfigParser()
config.read('config.ini')


def tag_picture(picture):
    tagged_picture = {
        'likes': str(picture['likes']['count']),
        'date': datetime.fromtimestamp(picture['date']).strftime('%d-%m-%Y'),
        'height': str(picture['orig_photo']['height']),
        'width': str(picture['orig_photo']['width']),
        'size': f'{picture['orig_photo']['width']}x{picture['orig_photo']['height']}',
        'area': picture['orig_photo']['height'] * picture['orig_photo']['width'],
        'url': picture['orig_photo']['url']
    }
    return tagged_picture


def get_pictures_from_json(json_file):
    pictures_info = json_file['response']['items']
    pictures_short_info = []
    for picture in pictures_info:
        pictures_short_info.append(tag_picture(picture))
    sorted_pictures = sorted(pictures_short_info, key=lambda d: d['area'])
    return sorted_pictures


def find_duplicates(list_to_check):
    duplicates = []
    if len(list_to_check) != len(set(list_to_check)):
        for elem in set(list_to_check):
            list_to_check.remove(elem)
        duplicates = set(list_to_check)
    return duplicates


def name_pictures_with_likes(pictures):
    all_likes = [picture['likes'] for picture in pictures]
    duplicates = find_duplicates(all_likes)
    for picture in pictures:
        if picture['likes'] not in duplicates:
            picture['filename'] = f'{picture['likes']}.jpg'
        else:
            picture['filename'] = f'{picture['likes']} {picture['date']}.jpg'
    return pictures


def save_pictures_to_pc(pictures):
    name_pictures_with_likes(pictures)
    counter = 1
    with tqdm(total=len(pictures), desc=f'Saving {len(pictures)} pictures to pc') as pbar:
        for picture in pictures:
            picture_jpg = requests.get(picture['url'])
            with open(picture['filename'], 'wb') as f:
                f.write(picture_jpg.content)
            counter += 1
            pbar.update(1)


def describe_pictures_to_json(pictures):
    name_pictures_with_likes(pictures)
    description_list = []
    with tqdm(total=len(pictures), desc='Creating json') as pbar:
        for picture in pictures:
            description = {
                'filename': picture['filename'],
                'size': f'{picture['width']}x{picture['height']}'
            }
            description_list.append(description)
            pbar.update(1)
        with open('description.json', 'w', encoding='utf-8') as f:
            json.dump(description_list, f, indent=4)


class VkApiClient:
    API_BASE_URL = 'https://api.vk.com/method'
    V = '5.199'

    def __init__(self, token):
        self.token = token

    def get_common_params(self):
        return {
            'access_token': self.token,
            'v': self.V
        }

    def get_user_name(self, vk_user_id):
        params = self.get_common_params()
        params.update({'user_ids': vk_user_id})
        response = requests.get(f'{self.API_BASE_URL}/users.get', params=params).json()['response'][0]
        user_name = f'{response['last_name']} {response['first_name']}'
        return user_name

    def get_json_pictures_from_vk(self, vk_user_id, album_id='profile'):
        with tqdm(total=2, desc='Getting json from VK', colour='blue') as pbar:
            params = self.get_common_params()
            params.update({'owner_id': vk_user_id,
                           'album_id': album_id,
                           'rev': 0,
                           'extended': 1})
            pbar.update(1)
            response = requests.get(f'{self.API_BASE_URL}/photos.get', params=params)
            pbar.update(1)
            return response.json()


class YandexApiClient:
    def __init__(self, yandex_token):
        self.yandex_token = yandex_token

    def get_common_header(self):
        return {
            'Authorization': self.yandex_token
        }

    def create_folder(self, folder_name='VK pictures'):
        headers = self.get_common_header()
        method_url = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {
            'path': folder_name
        }
        response = requests.put(method_url, params=params, headers=headers)

    def put_pictures(self, pictures, folder_name):
        self.create_folder(folder_name)
        headers = self.get_common_header()
        method_url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        with tqdm(total=len(pictures), desc=f'Posting {len(pictures)} pictures to Yandex.Disk', colour='yellow') as bar:
            for picture in pictures:
                params = {
                    'path': f'{folder_name}/{picture['filename']}',
                    'url': picture['url']
                }
                response = requests.post(method_url, params=params, headers=headers)
                bar.update(1)


def save_pics_vk_to_yandex(vk_user_id, album, amount=5, saving_flag=0):
    album_id = 'profile' if album == 0 else 'wall'
    vk_client = VkApiClient(config['Tokens']['vk_token'])
    pictures_json = vk_client.get_json_pictures_from_vk(vk_user_id, album_id)

    with tqdm(total=2, desc='Analyzing pictures') as pbar:
        pictures = get_pictures_from_json(pictures_json)
        pbar.update(1)
        filtered_pictures = pictures[-amount:]
        pbar.update(1)

    describe_pictures_to_json(filtered_pictures)

    if saving_flag == 2:
        save_pictures_to_pc(filtered_pictures)
    elif saving_flag == 1:
        save_pictures_to_pc(pictures)

    folder_name = 'VK photos ' + vk_client.get_user_name(vk_user_id)
    yandex_client = YandexApiClient(config['Tokens']['yandex_token'])
    yandex_client.put_pictures(filtered_pictures, folder_name)


if __name__ == '__main__':
    vk_id = input('Введите ID пользователя VK.com: ')
    vk_album = int(input('Выберите альбом: \n'
                         '0 - фото профиля \n'
                         '1 (или другой символ) - фото со стены\n'
                         'Введено: '))
    amount_of_pics = int(input('Введите количество фотографий для загрузки на Диск: '))
    saving_photos_flag = int(input(f'Сохранить на пк?\n'
                                   '0 - не сохранять\n1 - сохранить все фото\n'
                                   f'2 - сохранить только фото, загружаемые на Диск ({amount_of_pics} шт.)\n'
                                   'Введено: '))

    save_pics_vk_to_yandex(vk_id, vk_album, amount_of_pics, saving_photos_flag)
