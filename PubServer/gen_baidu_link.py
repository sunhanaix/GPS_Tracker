import requests
from urllib.parse import quote
import air_config as cfg

def generate_baidu_map_link(lat, lng, title="目标位置", content=""):
    # 坐标转换
    ak = cfg.baidu_ak  # 从百度开发者平台获取
    convert_url = "http://api.map.baidu.com/geoconv/v1/"
    params = {
        "coords": f"{lng},{lat}",
        "from": 1,
        "to": 5,
        "ak": ak
    }
    response = requests.get(convert_url, params=params)
    converted = response.json()['result'][0]
    
    # 生成链接
    base_url = "https://api.map.baidu.com/marker"
    params = {
        "location": f"{converted['y']},{converted['x']}",
        "title": quote(title),
        "content": quote(content),
        "output": "html",
        "coord_type": "bd09ll",
        "src": "wechat",
        "navigation": 1
    }
    return f"{base_url}?{'&'.join([f'{k}={v}' for k,v in params.items()])}"

def baidu_shorten_url(long_url):
    api_url = "http://dwz.cn/admin/v2/create"
    headers = {
        "Content-Type": "application/json",
        "Token": "你的百度短链token"  # 替换成实际token
    }
    data = {"Url": long_url}

    response = requests.post(api_url, json=data, headers=headers)
    return response.json()["ShortUrl"]


if __name__=="__main__":

    lat = 39.9128876
    lng = 116.4868698
    title = "目标位置"
    content = "目标内容"
    link=generate_baidu_map_link(lat, lng, title, content)
    print(link)