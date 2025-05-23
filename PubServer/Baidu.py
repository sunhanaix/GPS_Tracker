import os,sys,re,json,time,requests
import air_config as cfg
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
import math

# 初始化Flask应用和SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{cfg.db_file}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

mylogger=cfg.logger

x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.1415926535897932384626  # π
a = 6378245.0  # 长半轴
ee = 0.00669342162296594323  # 偏心率平方

# 定义GPS缓存数据模型
class GpsAddressCache(db.Model):
    __tablename__ = 'gps_address_cache'
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
#定义WIFI、基站缓存数据模型
class CellInfoCache(db.Model):
    __tablename__ = 'cell_info_cache'
    id = db.Column(db.Integer, primary_key=True)
    cellinfo = db.Column(db.String(500), nullable=False)
    wifi_info= db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

#给定wifi和基站信息，返回地址，不过当前百度这个接口属于高级功能，需要申请
def get_address_by_wifi_cellinfo(wifi_info, cellinfo,imei):
    if len(wifi_info)<1 and len(cellinfo)<1:
        return "Error: Invalid input"
    #参考https://lbsyun.baidu.com/faq/api?title=webapi/intel-hardware-base
    str_wifi_info=json.dumps(wifi_info, ensure_ascii=False)
    str_cellinfo=json.dumps(cellinfo, ensure_ascii=False)
    # 首先检查缓存中是否有该wifi/基站的信息地址
    with app.app_context():
        # 确保表存在
        db.create_all()
        cached_address = CellInfoCache.query.filter_by(cellinfo=str_cellinfo, wifi_info=str_wifi_info).first()
        if cached_address:
            mylogger.debug(f"从缓存中获取地址: {cached_address.address}")
            return cached_address.address
    # 如果缓存中没有，则调用百度API获取地址
    mylogger.debug(f"调用百度API获取地址: {wifi_info} {cellinfo}")
    url = f"https://api.map.baidu.com/locapi/v2"
    data = {
        'ver': '1.0',
        'trace': False,
        'prod': 'test_loc_api',
        'src': 'baidu_loc_api',
        'key': cfg.baidu_ak,
        'body': []
    }
    if len(wifi_info)>=1:
        # 构建WiFi参数
        valid_wifi = [w for w in wifi_info if len(w['bssid']) >= 12]
        macs = "|".join([
            f"{w['bssid']},{w['rssi']},{w['ssid'] or ''}"
            for w in valid_wifi[:30]  # 取前30个有效WiFi
        ]) if valid_wifi else ""
        wifi_body = {
            'accesstype': 1,
            'macs': macs,
            "imei": imei,
            'ctime': str(int(time.time())),
            'need_rgc': 'Y',
            'coor': 'WGS84',
            'output': 'json',
        }
        data['body'].append(wifi_body)
    if len(cellinfo)>=1:
        main_cell = cellinfo[0] if cellinfo else {}
        bts = (
            f"{main_cell.get('mcc', -1)},"
            f"{main_cell.get('mnc', -1)},"
            f"{main_cell.get('tac', -1)},"
            f"{main_cell.get('cid', -1)},"
            f"{main_cell.get('rsrp', 50)}"  # signal默认50
        ) if main_cell else ""
        nearbts="|".join([  # 周边基站
            f"{c.get('mcc', -1)},{c.get('mnc', -1)},"
            f"{c.get('tac', -1)},{c.get('cid', -1)},"
            f"{c.get('rsrp', 50)}"
            for c in cellinfo[1:]
            ]
        )
        cell_body = {
            'accesstype': 0,
            "bts": bts,
            "nearbts": nearbts,
            "imei":imei,
            'ctime': str(int(time.time())),
            'need_rgc': 'Y',
            'coor': 'WGS84',
            'output': 'json',
        }
        data['body'].append(cell_body)
    mylogger.info(f"{data=}")
    response = requests.post(url=url,json=data)
    if response.status_code == 200:
        result = response.json()
        mylogger.debug(f"{result}")
        if result['status'] == 0:
            address = result['result']['formatted_address_poi']
            # 将地址存入缓存
            with app.app_context():
                new_cache = CellInfoCache(cellinfo=cellinfo, wifi_info=wifi_info, address=address)
                db.session.add(new_cache)
                db.session.commit()


#给定坐标，返回地址
def get_address_by_coords(lat, lng):
    # 首先检查缓存中是否有该坐标的地址
    with app.app_context():
        # 确保表存在
        db.create_all()
        cached_address = GpsAddressCache.query.filter_by(lat=lat, lng=lng).first()
        if cached_address:
            mylogger.debug(f"从缓存中获取地址: {cached_address.address}")
            return cached_address.address

    # 如果缓存中没有，则调用百度API获取地址
    url = f"http://api.map.baidu.com/reverse_geocoding/v3/?ak={cfg.baidu_ak}&output=json&coordtype=wgs84ll&location={lat},{lng}&extensions_poi=1"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        mylogger.debug(f"{result}")
        if result['status'] == 0:
            address = result['result']['formatted_address_poi']
            # 将地址存入缓存
            with app.app_context():
                new_cache = GpsAddressCache(lat=lat, lng=lng, address=address)
                db.session.add(new_cache)
                db.session.commit()
            return address
        else:
            return f"Error: {result['message']}"
    else:
        return "Request failed"

#给定wifi扫描结果，以及基站信息，返回地址
def get_address(wifi_info, cellinfo):

    address = get_address_by_coords(lat, lng)
    return jsonify({"status": "success", "message": "Address request sent", "address": address})

#下面坐标变化来自于：
#https://github.com/wandergis/coordTransform_py

class Geocoding:
    def __init__(self, api_key):
        self.api_key = api_key

    def geocode(self, address):
        """
        利用高德geocoding服务解析地址获取位置坐标
        :param address:需要解析的地址
        :return:
        """
        geocoding = {'s': 'rsv3',
                     'key': self.api_key,
                     'city': '全国',
                     'address': address}
        geocoding = urllib.urlencode(geocoding)
        ret = urllib.urlopen("%s?%s" % ("http://restapi.amap.com/v3/geocode/geo", geocoding))

        if ret.getcode() == 200:
            res = ret.read()
            json_obj = json.loads(res)
            if json_obj['status'] == '1' and int(json_obj['count']) >= 1:
                geocodes = json_obj['geocodes'][0]
                lng = float(geocodes.get('location').split(',')[0])
                lat = float(geocodes.get('location').split(',')[1])
                return [lng, lat]
            else:
                return None
        else:
            return None


def gcj02_to_bd09(lng, lat):
    """
    火星坐标系(GCJ-02)转百度坐标系(BD-09)
    谷歌、高德——>百度
    :param lng:火星坐标经度
    :param lat:火星坐标纬度
    :return:
    """
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return [bd_lng, bd_lat]


def bd09_to_gcj02(bd_lon, bd_lat):
    """
    百度坐标系(BD-09)转火星坐标系(GCJ-02)
    百度——>谷歌、高德
    :param bd_lat:百度坐标纬度
    :param bd_lon:百度坐标经度
    :return:转换后的坐标列表形式
    """
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return [gg_lng, gg_lat]


def wgs84_to_gcj02(lng, lat):
    """
    WGS84转GCJ02(火星坐标系)
    :param lng:WGS84坐标系的经度
    :param lat:WGS84坐标系的纬度
    :return:
    """
    if out_of_china(lng, lat):  # 判断是否在国内
        return [lng, lat]
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return [mglng, mglat]


def gcj02_to_wgs84(lng, lat):
    """
    GCJ02(火星坐标系)转GPS84
    :param lng:火星坐标系的经度
    :param lat:火星坐标系纬度
    :return:
    """
    if out_of_china(lng, lat):
        return [lng, lat]
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return [lng * 2 - mglng, lat * 2 - mglat]


def bd09_to_wgs84(bd_lon, bd_lat):
    lon, lat = bd09_to_gcj02(bd_lon, bd_lat)
    return gcj02_to_wgs84(lon, lat)


def wgs84_to_bd09(lon, lat):
    lon, lat = wgs84_to_gcj02(lon, lat)
    return gcj02_to_bd09(lon, lat)


def _transformlat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 *
            math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 *
            math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret


def _transformlng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 *
            math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 *
            math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret

def out_of_china(lng, lat):
    """
    判断是否在国内，不在国内不做偏移
    :param lng:
    :param lat:
    :return:
    """
    return not (lng > 73.66 and lng < 135.05 and lat > 3.86 and lat < 53.55)

if __name__=='__main__':
    with app.app_context():
        db.create_all()
    latitude = 40.1059341
    longitude = 116.5506897

    latitude = 39.930851
    longitude = 116.9081955

    #address = get_address_by_coords(latitude, longitude)
    #wifi_info=[{'channel': 0, 'rssi': -30, 'ssid': '7-3-101', 'bssid': '286C076EA09A'}, {'channel': 0, 'rssi': -39, 'ssid': 'CU_7-3-101', 'bssid': 'C0F6ECBF9690'}, {'channel': 0, 'rssi': -46, 'ssid': '没有名字的WIFI', 'bssid': 'E0E0FC3C0EA0'}, {'channel': 0, 'rssi': -46, 'ssid': '', 'bssid': 'E0E0FC3C0EA5'}, {'channel': 0, 'rssi': -47, 'ssid': '没有名字的WIFI_Wi-Fi5', 'bssid': 'E0E0FCFC0EA5'}]
    #cellinfo=[{'mnc': 0, 'earfcn': 3590, 'pci': 308, 'rsrp': -79, 'tac': 4571, 'mcc': 460, 'rsrq': -5, 'snr': 23, 'cid': 23928315}, {'mnc': 15, 'earfcn': 38400, 'pci': 18, 'rsrp': -91, 'tac': 4571, 'mcc': 460, 'rsrq': -9, 'snr': 7, 'cid': 23928265}, {'mnc': 0, 'dlbandwidth': 5, 'tdd': 1, 'earfcn': 38400, 'ulbandwidth': 5, 'band': 39, 'mcc': 460, 'pci': 18, 'rsrp': -91, 'tac': 4571, 'rssi': -62, 'rsrq': -9, 'snr': 7, 'cid': 23928265}, {'mnc': 0, 'earfcn': 36275, 'pci': 97, 'rsrp': -115, 'tac': 4571, 'mcc': 460, 'rsrq': -13, 'snr': -1, 'cid': 22243545}, {'mnc': 0, 'earfcn': 40936, 'pci': 18, 'rsrp': -108, 'tac': 4571, 'mcc': 460, 'rsrq': -13, 'snr': 2, 'cid': 19391233}]
    #address=get_address_by_wifi_cellinfo(wifi_info,cellinfo,imei='860678075954729')
    bd_lng, bd_lat = wgs84_to_bd09(
        116.4868698,
        39.9128876,
    )
    print(bd_lng, bd_lat)