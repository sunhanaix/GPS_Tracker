from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import air_config as cfg

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{cfg.db_file}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class IotData(db.Model):
    __tablename__ = 'iot_data'
    id = db.Column(db.Integer, primary_key=True)
    imei = db.Column(db.String(20), nullable=False, default='860678075954729')  # 确保imei字段存在
    timestamp = db.Column(db.DateTime, nullable=False)
    ip = db.Column(db.String(20))
    rssi = db.Column(db.Integer)
    temp = db.Column(db.Float)
    memsys = db.Column(db.JSON)
    memlua = db.Column(db.JSON)
    rsrp = db.Column(db.Integer)
    vbat = db.Column(db.Float)
    csq = db.Column(db.Integer)
    snr = db.Column(db.Integer)
    rsrq = db.Column(db.Integer)
    variation = db.Column(db.Integer)
    lng = db.Column(db.Float)
    lat = db.Column(db.Float)
    agps_lat = db.Column(db.Float)
    agps_lng = db.Column(db.Float)
    valid = db.Column(db.Boolean)
    speed = db.Column(db.Float)
    course = db.Column(db.Float)
    day = db.Column(db.Integer)
    hour = db.Column(db.Integer)
    month = db.Column(db.Integer)
    sec = db.Column(db.Integer)
    year = db.Column(db.Integer)
    uptime = db.Column(db.DateTime)
    up_vbat = db.Column(db.Float)
    agps_ts = db.Column(db.Integer)
    gps_ts = db.Column(db.Integer)
    wifi_ts = db.Column(db.Integer)
    wifi = db.Column(db.JSON)
    cellinfo = db.Column(db.JSON)
    cfg = db.Column(db.JSON)


class UrlMapping(db.Model):
    __tablename__ = 'url_mapping'
    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(8), unique=True, nullable=False)
    long_url = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())


class IotCfg(db.Model):
    __tablename__ = 'iot_cfg'
    id = db.Column(db.Integer, primary_key=True)
    imei = db.Column(db.String(20), nullable=False, default='860678075954729')  # 确保imei字段存在
    timestamp = db.Column(db.DateTime)
    cfg = db.Column(db.String(1000))  # 存储配置数据


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    imei = db.Column(db.String(15), unique=True, nullable=False)  # 用户名统一为IMEI
    password = db.Column(db.String(64), nullable=False)  # 存储加密后的密码
    last_login = db.Column(db.DateTime)  # 上次登录时间
    password_changed = db.Column(db.Boolean, default=False)  # 是否已修改密码
    xiatui_key= db.Column(db.String(255)) #虾推密钥
    #设置是否启用xiatui_key字段
    enable_xiatui = db.Column(db.Boolean, default=True)
    notify_phone = db.Column(db.String(255)) #通知号码
    #设置是否启用notify_phone字段
    enable_notify_phone = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.String(255)) #通知邮箱
    #设置是否启用notify_email字段
    enable_notify_email = db.Column(db.Boolean, default=True)
    notify_time = db.Column(db.DateTime)  # 新增字段，记录上次发送告警的时间
    #增加备注字段
    remark = db.Column(db.String(255))

# 定义ZipData模型
class ZipData(db.Model):
    __tablename__ = 'zip_data'
    id = db.Column(db.Integer, primary_key=True)
    imei = db.Column(db.String(15), nullable=False)  # 新增字段，用于区分设备
    timestamp = db.Column(db.DateTime)
    vbat = db.Column(db.Integer)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

# 新增GeoFence模型，用于存储电子围栏数据
class GeoFence(db.Model):
    __tablename__ = 'geo_fence'
    id = db.Column(db.Integer, primary_key=True)
    imei = db.Column(db.String(15), nullable=False)  # 设备IMEI
    timestamp = db.Column(db.DateTime, nullable=False)  # 时间戳
    lat = db.Column(db.Float, nullable=False)  # 纬度
    lng = db.Column(db.Float, nullable=False)  # 经度
    address = db.Column(db.String(255))  # 地址描述
    radius = db.Column(db.Float, nullable=False)  # 围栏半径，单位：米

# 新增ShareTracker模型，用于存储共享轨迹数据
class ShareTracker(db.Model):
    __tablename__ = 'share_tracker'
    id = db.Column(db.String(32), primary_key=True)  # 存放MD5值
    imei = db.Column(db.String(15), nullable=False)  # 设备IMEI
    start_time = db.Column(db.DateTime, nullable=False)  # 轨迹开始时间
    end_time = db.Column(db.DateTime, nullable=False)  # 轨迹结束时间
