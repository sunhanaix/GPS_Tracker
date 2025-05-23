#!/usr/local/bin/python3.12
from flask import Flask, render_template, request, Response, session, make_response, send_from_directory, jsonify, redirect,abort
import hashlib
import ssl
import sys,os,time,re,json,base64
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from threading import Thread
from geopy.distance import geodesic
import air_config as cfg
from  Baidu import get_address_by_coords,wgs84_to_bd09,bd09_to_wgs84
from zip_data import copy_and_filter_data
import models
from battery_estimate import estimate_remaining_time,estimate_battery_percentage  # 导入电池估算模块

app=models.app
db=models.db
IotData=models.IotData
IotCfg=models.IotCfg
ZipData=models.ZipData
UrlMapping=models.UrlMapping
GeoFence=models.GeoFence
User=models.User
ShareTracker=models.ShareTracker
app.config['SECRET_KEY'] = b'\xder\x884_\xe9\x8e\x05\xf62\xf8q\xab*\xd7/{1y\x08\x19\xee\xcb%'  # 设置一个固定字符串为加密盐，这样每次重启程序后，session也可以继续可用，安全的话，每次生成不同的
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=cfg.exp_days)  # 设置session N天过期

# 添加静态文件路径配置
app.static_folder = 'static'
app.static_url_path = '/static'

mylogger=cfg.logger
sub_topic = "/tracker/+/up/stat" #使用mqtt通配符+来适配不同imei设备的topic
sub_cmd_topic = "/tracker/+/up/cmd"
pub_topic = "/tracker/%s/down/cmd"

cmd_data=None

# MQTT客户端初始化
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(username=cfg.mqtt_user, password=cfg.mqtt_password)

def calculate_distance(track): #给定坐标轨迹，计算总的路径长度
    total_distance = 0.0
    for i in range(len(track) - 1):
        point1 = (float(track[i]['lat']), float(track[i]['lng']))
        point2 = (float(track[i + 1]['lat']), float(track[i + 1]['lng']))
        distance = geodesic(point1, point2).meters
        total_distance += distance
    return int(total_distance)
def on_mqtt_connect(client, userdata, flags, rc):
    mylogger.info(f"MQTT Connected with result code {rc}")
    #订阅sub_topic和sub_cmd_topic
    client.subscribe(sub_cmd_topic)
    client.subscribe(sub_topic)
def on_mqtt_message(client, userdata, msg):
    global cmd_data
    #判断是否是sub_topic和sub_cmd_topic
    try:
        # 添加错误处理参数
        payload = msg.payload.decode('utf-8', errors='replace')  # 用�替代错误字节
        data = json.loads(payload)
        mylogger.info(f"mqtt payload {data}")
    except UnicodeDecodeError as e:
        mylogger.error(f"解码失败，原始payload十六进制：{msg.payload.hex()}")
    except json.JSONDecodeError:
        mylogger.error("非JSON格式消息")
    except Exception as e:
        mylogger.error(f"处理MQTT消息失败: {str(e)}")
    if msg.topic.find('/tracker')>-1 and msg.topic.find('stat') >-1: #判断是否是sub_topic，并且是报状态的数据
        cmd_data = None
        topic_parts = msg.topic.split("/")
        imei = topic_parts[2]
        mylogger.info(f"普通MQTT Message received on {msg.topic}: {payload},{imei=}")
        save_to_db(data)
        copy_and_filter_data(imei) #压缩数据
    elif msg.topic.find('/tracker')>-1 and msg.topic.find('cmd') >-1: #判断是否是sub_cmd_topic，是命令请求的返回
        mylogger.info(f"命令请求返回的MQTT Message received on {msg.topic}: {payload}")
        save_cfg_to_db(data)
def save_to_db(data):
    try:
        required_fields = ['temp', 'vbat']
        for field in required_fields:
            if field not in data:
                mylogger.warning(f"缺失必要字段: {field}")
                return
        with app.app_context():
            record = IotData(
                imei=data.get('imei', '860678075954729'),  # 新增字段，默认值为当前设备IMEI
                timestamp=datetime.now(),
                ip=data.get('ip'),
                rssi=data.get('rssi'),
                temp=data.get('temp'),
                memsys=json.dumps(data.get('memsys', {})),
                memlua=json.dumps(data.get('memlua', {})),
                rsrp=data.get('rsrp', 0),
                vbat=data.get('vbat', 0),
                csq=data.get('csq', 0),
                snr=data.get('snr', 0),
                rsrq=data.get('rsrq', 0),
                variation=data.get('variation', 0),
                lng=data.get('lng', 0.0),
                lat=data.get('lat', 0.0),
                agps_lat=data.get('agps_lat', 0.0),
                agps_lng=data.get('agps_lng', 0.0),
                valid=data.get('valid', False),
                speed=data.get('speed', 0.0),
                course=data.get('course', 0.0),
                day=data.get('day', 0),
                hour=data.get('hour', 0),
                month=data.get('month', 0),
                sec=data.get('sec', 0),
                year=data.get('year', 2000),
                uptime=data.get('uptime', 0),
                up_vbat=data.get('up_vbat', 0), #启动时候的电压
                agps_ts=data.get('agps_ts', 0),  # 新增字段处理
                gps_ts=data.get('gps_ts', 0),    # 新增字段处理
                wifi_ts=data.get('wifi_ts', 0),   # 新增字段处理
                wifi=json.dumps(data.get('wifi', [])),  # 新增字段处理
                cellinfo=json.dumps(data.get('cellinfo', [])),  # 新增字段处理
                cfg=json.dumps(data.get('cfg', {})),  # 新增字段处理
            )
            #把record.uptime的unix时间戳转换为datetime对象
            record.uptime = datetime.fromtimestamp(record.uptime)
            db.session.add(record)
            db.session.commit()
    except Exception as e:
        mylogger.error(f"保存数据失败: {str(e)}")

def save_cfg_to_db(data):
    print(f"{data=}")
    try:
        with app.app_context():
            record = IotCfg(
                imei=data.get('cfg',{}).get('imei'),
                timestamp=datetime.now(),
                cfg=json.dumps(data.get('cfg', {}))
            )
            db.session.add(record)
            db.session.commit()
    except Exception as e:
        mylogger.error(f"保存配置数据失败: {str(e)}")

@app.route('/dev')
def dev():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    user_info = User.query.filter_by(imei=session['user']).first()
    return render_template('dev.html', home_url=cfg.home_url, battery_feature=cfg.battery_feature,static_url=cfg.static_url,remark=user_info.remark)
@app.route('/api/data/realtime')
def realtime_data():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    latest = IotData.query.filter_by(imei=session['user']).order_by(IotData.timestamp.desc()).first()  # 根据当前用户IMEI过滤数据
    mylogger.info(f"{latest=}")
    if not latest:
        return jsonify({
            'temp': 0,
            'vbat': 0,
            'location': {'lat': 0, 'lng': 0,'agps_lat':0,'agps_lng':0},
            'timestamp': '无数据',
            'uptime': '无数据',
            'up_vbat': 0,
        })
    return jsonify({
        'temp': latest.temp,
        'vbat': latest.vbat,
        'location': {'lat': latest.lat, 'lng': latest.lng,'agps_lat':latest.agps_lat,'agps_lng':latest.agps_lng},
        'timestamp': latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': latest.uptime.strftime('%Y-%m-%d %H:%M:%S'),
        'up_vbat': latest.up_vbat,
    })


@app.route('/api/data/history')
def history_data():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    hours = request.args.get('hours', default=24, type=int)
    since = datetime.now() - timedelta(hours=hours)

    query = IotData.query.filter(IotData.timestamp >= since, IotData.imei == session['user'])  # 根据当前用户IMEI过滤数据
    data = [{
        'time': d.timestamp.strftime('%H:%M'),
        'temp': d.temp,
        'vbat': d.vbat
    } for d in query.all()]

    return jsonify(data)

@app.route('/api/data/GetDevicesHistory', methods=['GET'])
def get_devices_history():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        # 解析请求参数
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        
        # 将字符串转换为datetime对象
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        
        # 查询zip_data表中指定时间范围内的数据
        records = ZipData.query.filter(ZipData.timestamp.between(start_time, end_time), ZipData.imei == session['user']).all()  # 根据当前用户IMEI过滤数据
        
        # 格式化查询结果为指定JSON格式
        result = [{
            "pt": record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "lat": record.lat,
            "lng": record.lng
        } for record in records]
        for r in result:
            lng,lat=wgs84_to_bd09(r['lng'], r['lat']) # 转换成百度坐标
            r['lat']=lat
            r['lng']=lng
        return jsonify(result)
    except Exception as e:
        mylogger.error(f"查询设备历史数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/data/GetTracking', methods=['GET'])
def get_tracking():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        # 查询zip_data表中最后一条数据
        latest_record = ZipData.query.filter_by(imei=session['user']).order_by(ZipData.timestamp.desc()).first()  # 根据当前用户IMEI过滤数据
        
        if not latest_record:
            return jsonify({"status": "error", "message": "No data found"}), 404
        
        # 获取地址信息
        address = get_address_by_coords(latest_record.lat, latest_record.lng)
        
        # 返回指定格式的JSON数据
        return jsonify({
            "lat": latest_record.lat,
            "lng": latest_record.lng,
            "vbat": latest_record.vbat,
            "address": address
        })
    except Exception as e:
        mylogger.error(f"获取跟踪数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/config/get', methods=['GET'])
def get_config():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    imei = session.get('user')
    mqtt_client.publish(pub_topic % imei, json.dumps({"command": "get_config"}))
    time.sleep(2)  # 等待2秒，确保配置数据返回
    # 从iot_cfg表中获取配置数据
    iotcfg_data = IotCfg.query.filter_by(imei=imei).order_by(IotCfg.timestamp.desc()).first()
    mylogger.info(f"{iotcfg_data=}")
    if iotcfg_data:
        # 判断时间戳是否在给定时间内
        time_diff = datetime.now() - iotcfg_data.timestamp
        if time_diff.total_seconds() <= 10:
            config_data = iotcfg_data.cfg
            mylogger.info(f"{config_data=}")
            return jsonify({"status": "success", "message": "Config request sent", "config": config_data, "imei": imei})
        else:
            mylogger.info("Device timeout")
            config_data = iotcfg_data.cfg
            #虽然超时了，也还是返回一个最近的数据给客户端吧
            return jsonify({"status": "success", "message": "Config request sent", "config": config_data, "imei": imei})
            #return jsonify({"status": "error", "message": "Device timeout"}), 500
    else:
        mylogger.info("Failed to receive config data")
        return jsonify({"status": "error", "message": "Failed to receive config data"}), 500

@app.route('/api/config/set', methods=['POST'])
def set_config():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    cmd = request.json
    mylogger.info(f"获得客户端发送的请求:{cmd=}")
    if cmd.get('command')=='reboot':
        mqtt_client.publish(pub_topic % session.get('user'), json.dumps({"command": "reboot"}))
        return jsonify({"status": "success", "message": "Reboot request sent"})
    if cmd.get('command')=='report_status':
        mqtt_client.publish(pub_topic % session.get('user'), json.dumps({"command": "report_status"}))
        return jsonify({"status": "success", "message": "Report status request sent"})
    #判断cmd是否更新微码
    if cmd.get('command')=='update_firmware':
        firmware_version=cmd.get('value')
        url=f"{cfg.firmware_url_dir}/{cfg.app_name}{firmware_version}.bin"
        mylogger.info(f"获得客户端发送的更新微码地址:{url=}")
        mqtt_client.publish(pub_topic % session.get('user'), json.dumps({"command": "update_firmware", "value": url}))
        return jsonify({"status": "success", "message": "更新微码请求已下发，请等待设备更新后重启"})
    config=cmd
    mqtt_client.publish(pub_topic % session.get('user'), json.dumps({"command": "set_config", "value": config}))
    return jsonify({"status": "success", "message": "Config update request sent"})

#增加一个api接口，给定坐标，返回地址
@app.route('/api/address/get', methods=['GET'])
def get_address():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    lat = request.args.get('lat', default=0, type=float)
    lng = request.args.get('lng', default=0, type=float)
    mylogger.info(f"获得客户端发送的坐标:{lat=},{lng=}")
    address = get_address_by_coords(lat, lng)
    return jsonify({"status": "success", "message": "Address request sent", "address": address})

@app.route('/', methods=['GET'])
def home():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    ip = request.remote_addr
    if ip.find('127.0.0.1') > -1:
        ip = request.headers.get('X-Forwarded-For')
    browser = request.headers.get("User-Agent")
    mylogger.info(f"user={session.get('user')},{ip=},{browser=}")
    try:
        # 查询zip_data表中最后一条数据，并根据当前用户IMEI过滤
        latest_record = ZipData.query.filter_by(imei=session['user']).order_by(ZipData.timestamp.desc()).first()
        if not latest_record:
            return f'<h1>当前没有数据信息，请确保设备电池有电，并给设备开机，然后等设备上报数据<br>id={session.get('user')}<a href="{cfg.home_url}/logout">注销</a></h1>'
        # 获取地址信息
        address = get_address_by_coords(latest_record.lat, latest_record.lng)
    except Exception as e:
        mylogger.error(f"获取跟踪数据失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    #使用相关函数获得电池电量百分比
    battery_percentage = estimate_battery_percentage(latest_record.vbat)
    ts=latest_record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    return render_template('baidu_templ.html', lat=latest_record.lat, lng=latest_record.lng,
                           battery_status=f"{battery_percentage:.0f}", gps_info='', update_time=ts,
                           address=address, home_url=cfg.home_url,static_url=cfg.static_url,map_refresh_interval=cfg.map_refresh_interval,baidu_ak=cfg.baidu_web_ak)


@app.route('/his', methods=['GET'])
def his():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    session.permanent = True
    record = request.args.get('record')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    ip = request.remote_addr
    if ip.find('127.0.0.1') > -1:
        ip = request.headers.get('X-Forwarded-For')
    browser = request.headers.get("User-Agent")
    mylogger.info(f"init {record=},{start_time=},{end_time=},{ip=},{browser=}")
    if record:
        start_time = start_time.replace('T', ' ') + ':00'
        end_time = end_time.replace('T', ' ') + ':00'
        mylogger.info(f"record: {record=},{start_time=},{end_time=},{ip=},{browser=}")
        # 将字符串转换为datetime对象
        #start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        #end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        records = ZipData.query.filter(ZipData.timestamp.between(start_time, end_time), ZipData.imei == session['user']).all()  # 添加imei过滤条件
        # 格式化查询结果为指定JSON格式
        result = [{
            "pt": record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "lat": record.lat,
            "lng": record.lng
        } for record in records]
        for r in result:
            lng, lat = wgs84_to_bd09(r['lng'], r['lat'])  # 转换成百度坐标
            r['lat'] = lat
            r['lng'] = lng
        #mylogger.info(f"{result=}")
        distance = calculate_distance(result)
        return render_template('history_templ.html', data=result, history=f"{start_time}--{end_time}", distance=distance,baidu_ak=cfg.baidu_web_ak,home_url=cfg.home_url,static_url=cfg.static_url,his=1)
    user_info = User.query.filter_by(imei=session['user']).first()
    return render_template('select_history_date_templ.html', home_url=cfg.home_url,static_url=cfg.static_url,remark=user_info.remark)

def generate_short_url(long_url):
    # 使用MD5生成短链接的哈希值，取前8个字符作为短编码
    hash_object = hashlib.md5(long_url.encode())
    short_code = hash_object.hexdigest()[:8]
    return short_code

@app.route('/api/data/shortUrl', methods=['POST'])
def create_short_url():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    long_url = request.json.get('long_url')
    if not long_url:
        return jsonify({"status": "error", "message": "Missing long_url"}), 400
    short_code = generate_short_url(long_url)
    with app.app_context():
        # 检查是否已存在相同的短码
        existing_mapping = UrlMapping.query.filter_by(short_code=short_code).first()
        if existing_mapping:
            return jsonify({"status": "success", "short_url": f"/url/{short_code}"})
        # 创建新的映射
        new_mapping = UrlMapping(short_code=short_code, long_url=long_url)
        db.session.add(new_mapping)
        db.session.commit()
    return jsonify({"status": "success", "short_url": f"/url/{short_code}"})

@app.route('/url/<short_code>')
def redirect_to_long_url(short_code):
    #if not session.get('user'):  #这个对外的，不能要求登录
        #return redirect(f'{cfg.home_url}/login')
    with app.app_context():
        mapping = UrlMapping.query.filter_by(short_code=short_code).first()
        if not mapping:
            abort(404, description="Short URL not found")
        return redirect(mapping.long_url)

@app.route('/imei/<imei>')
def redirect_to_login_with_imei(imei):
    # 重定向到登录页面，并传递imei参数
    return redirect(f'{cfg.home_url}/login?imei={imei}')

@app.route('/gen_qrcode/<imei>')
def gen_qrcode(imei):
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    # 生成链接
    url = f"{cfg.home_url}/imei/{imei}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 返回包含二维码的HTML页面
    return render_template('qrcode.html', qrcode_img=img_str, url=url)

@app.route('/api/battery/estimate', methods=['GET'])
def estimate_battery_time():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        # 获取前端传入的电压值
        voltage_mv = request.args.get('voltage', default=0, type=int)
        mylogger.info(f"获得客户端发送的电压值: {voltage_mv}mV")
        
        # 调用电池估算函数
        remaining_time = estimate_remaining_time(voltage_mv)
        remaining_time=remaining_time/60 #前面算出来的是分钟，现在转换成小时
        battery_percentage = estimate_battery_percentage(voltage_mv)

        
        # 返回估算的剩余时间
        return jsonify({
            "status": "success",
            "voltage_mv": voltage_mv,
            "remaining_time_minutes": remaining_time,
            "battery_percentage": f"{battery_percentage:.1f}",
        })
    except Exception as e:
        mylogger.error(f"估算电池剩余时间失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/firmware/latest', methods=['GET'])
def get_latest_firmware():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        # 获取固件目录
        firmware_dir = cfg.firmware_dir
        if not os.path.exists(firmware_dir):
            mylogger.error("固件目录不存在")
            return jsonify({"status": "error", "message": "固件目录不存在"}), 404
        
        # 查找所有符合命名规则的固件文件
        firmware_files = [f for f in os.listdir(firmware_dir) if re.match(r'.*\d+\.\d+\.\d+\.\d+\.bin$', f)]
        if not firmware_files:
            mylogger.error("未找到符合条件的固件文件")
            return jsonify({"status": "error", "message": "未找到符合条件的固件文件"}), 404
        
        # 提取版本号并找到最大版本的文件
        max_version = None
        max_file = None
        for file in firmware_files:
            version_str = re.search(r'(\d+\.\d+\.\d+\.\d+)', file).group(1)
            version = tuple(map(int, version_str.split('.')))
            if max_version is None or version > max_version:
                max_version = version
                max_file = file
        
        # 返回最大版本的文件名和版本号
        return jsonify({
            "status": "success",
            "filename": max_file,
            "version": ".".join(map(str, max_version))
        })
    except Exception as e:
        mylogger.error(f"获取最新固件信息失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 增加登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户是否存在，先尝试用notify_phone查找
        users = User.query.filter_by(notify_phone=username).all()
        if not users:
            # 如果notify_phone找不到，再尝试用imei查找
            user = User.query.filter_by(imei=username).first()
            if user:
                users = [user]
        
        if not users:
            # 用户不存在，尝试使用默认密码登录
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            default_hash = hashlib.sha256(cfg.default_password.encode()).hexdigest()
            if hashed_password == default_hash:
                # 默认密码登录成功，创建新用户
                new_user = User(imei=username, password=hashed_password, password_changed=False)
                db.session.add(new_user)
                db.session.commit()
                session['user'] = username
                return redirect(f'{cfg.home_url}/change_password')
            else:
                return render_template("login_templ.html", prompt="登录失败，请重新登录", home_url=cfg.home_url, static_url=cfg.static_url,default_password=cfg.default_password)
        
        # 如果手机号对应多个IMEI，提示用户选择
        if len(users) > 1:
            return render_template("select_imei_templ.html", users=users, password=password,home_url=cfg.home_url, static_url=cfg.static_url)
        
        # 只有一个用户，执行正常登录流程
        user = users[0]
        res = checkUserPass(user.imei, password)
        if res:
            session['user'] = user.imei
            # 检查是否需要强制修改密码
            if not user.password_changed and hashlib.sha256(cfg.default_password.encode()).hexdigest() == user.password:
                return redirect(f'{cfg.home_url}/change_password')
            return redirect(cfg.home_url)
        else:
            return render_template("login_templ.html", prompt="登录失败，请重新登录", home_url=cfg.home_url, static_url=cfg.static_url)
    return render_template("login_templ.html", prompt="请登录", home_url=cfg.home_url, static_url=cfg.static_url)

# 增加登出路由
@app.route('/logout')
def logout():
    if session.get('user'):
        mylogger.info(f"user:{session['user']} logout")
        del session['user']
    return redirect(f'{cfg.home_url}/login')
@app.route('/select_imei', methods=['POST'])
def select_imei():
    if request.method == 'POST':
        imei = request.form.get('imei')
        password = request.form.get('password')
        
        # 验证用户登录
        res = checkUserPass(imei, password)
        if res:
            session['user'] = imei
            return redirect(cfg.home_url)
        else:
            redirect(f'{cfg.home_url}/login')
    return redirect(f'{cfg.home_url}/login')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            return render_template("change_password_templ.html", prompt="新密码和确认密码不一致",home_url=cfg.home_url,default_password=cfg.default_password)
        
        user = User.query.filter_by(imei=session['user']).first()
        if not user:
            return render_template("change_password_templ.html", prompt="用户不存在",home_url=cfg.home_url,default_password=cfg.default_password)
        
        # 验证旧密码
        hashed_old_password = hashlib.sha256(old_password.encode()).hexdigest()
        if hashed_old_password != user.password:
            return render_template("change_password_templ.html", prompt="旧密码错误",home_url=cfg.home_url,default_password=cfg.default_password)
        
        # 更新密码
        hashed_new_password = hashlib.sha256(new_password.encode()).hexdigest()
        user.password = hashed_new_password
        user.password_changed = True
        db.session.commit()
        
        return redirect(cfg.home_url)
    
    return render_template("change_password_templ.html", prompt="请修改密码",home_url=cfg.home_url,default_password=cfg.default_password)

def checkUserPass(imei, password):
    """
    验证用户密码是否正确
    :param imei: 用户的IMEI
    :param password: 用户输入的密码
    :return: 如果密码正确返回True，否则返回False
    """
    user = User.query.filter_by(imei=imei).first()
    if not user:
        return False
    
    # 计算输入密码的哈希值
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    # 比较哈希值
    return hashed_password == user.password

# 增加告警设置页面路由
@app.route('/alert', methods=['GET'])
def alert():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    
    # 查询当前用户的告警设置
    user_info = User.query.filter_by(imei=session['user']).first()
    #只把告警设置返回alert_config
    alert_config = {
        "email": user_info.notify_email,
        "phone": user_info.notify_phone,
        "xiatui_key": user_info.xiatui_key,
        "enable_xiatui": user_info.enable_xiatui,
        "enable_notify_email": user_info.enable_notify_email,
        "enable_notify_phone": user_info.enable_notify_phone,
    }
    mylogger.info(f"user:{session['user']} alert_config={alert_config}")
    return render_template('alert.html', alert_config=alert_config, home_url=cfg.home_url, static_url=cfg.static_url)

# 增加获取告警设置API
@app.route('/api/alert/get', methods=['GET'])
def get_alert_config():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    user_info = User.query.filter_by(imei=session['user']).first()
    if user_info:
        return jsonify({
            "status": "success",
            "remark": user_info.remark,
            "email": user_info.notify_email,
            "phone": user_info.notify_phone,
            "xiatui_key": user_info.xiatui_key,
            "enable_xiatui": user_info.enable_xiatui,
            "enable_notify_email": user_info.enable_notify_email,
            "enable_notify_phone": user_info.enable_notify_phone,
        })
    else:
        return jsonify({"status": "success", "email": "", "phone": "", "xiatui_key": ""})

# 增加更新告警设置API
@app.route('/api/alert/update', methods=['POST'])
def update_alert_config():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        data = request.json
        user_info = User.query.filter_by(imei=session['user']).first()
        user_info.remark = data.get('remark', '')
        user_info.notify_email = data.get('email', '')
        user_info.notify_phone = data.get('phone', '')
        user_info.xiatui_key = data.get('xiatui_key', '')
        user_info.enable_xiatui = data.get('enable_xiatui', True)
        user_info.enable_notify_email = data.get('enable_notify_email', True)
        user_info.enable_notify_phone = data.get('enable_notify_phone', True)

        db.session.commit()
        return jsonify({"status": "success", "message": "Alert config updated successfully"})
    except Exception as e:
        mylogger.error(f"更新告警设置失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/fence', methods=['GET'])
def fence():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    
    # 查询当前用户的电子围栏数据
    geofences = GeoFence.query.filter_by(imei=session['user']).all()
    #由于后台数据库统一存放的WGS84坐标系统，所以需要转换一下到BD09坐标后给前台进行展示
    #遍历围栏数据，进行坐标转换，并直接返回一个list的result
    geo_fence_list=[]
    for fence in geofences:
        fence_data = {
            'id': fence.id,
            'lat': fence.lat,
            'lng': fence.lng,
            'radius': fence.radius,
            'address': fence.address,
        }
        #数据库中存储的坐标是WGS84，需要转换一下到BD09坐标
        #print(f"WGS84: {fence_data['lng']},{fence_data['lat']}  ",end="")
        fence_data['lng'],fence_data['lat']=wgs84_to_bd09(fence_data['lng'],fence_data['lat'])
        #print(f"BD09: {fence_data['lng']}, {fence_data['lat']}")
        geo_fence_list.append(fence_data)

    # 将数据传递给模板
    return render_template('geo_fence.html', geofences=geo_fence_list, baidu_ak=cfg.baidu_web_ak,home_url=cfg.home_url,static_url=cfg.static_url)

@app.route('/add_geofence', methods=['GET'])
def add_geofence_page():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    
    # 渲染添加电子围栏的页面
    return render_template('modify_geofence.html', baidu_ak=cfg.baidu_web_ak, home_url=cfg.home_url, static_url=cfg.static_url)

@app.route('/api/geofence/add', methods=['POST'])
def add_geofence():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.json
        # 创建新的电子围栏
        new_geofence = GeoFence(
            imei=session['user'],
            lat=data.get('lat'),
            lng=data.get('lng'),
            radius=data.get('radius'),
            address=data.get('address'),
            timestamp=datetime.now()
        )
        #前端传过来的坐标时BD09坐标，入库时需要转换一下到WGS84坐标
        new_geofence.lng,new_geofence.lat=bd09_to_wgs84(new_geofence.lng,new_geofence.lat)
        db.session.add(new_geofence)
        db.session.commit()
        return jsonify({"status": "success", "message": "Geofence added successfully"})
    except Exception as e:
        mylogger.error(f"添加电子围栏失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/geofence/delete', methods=['POST'])
def delete_geofence():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.json
        geofence = GeoFence.query.filter_by(id=data.get('id'), imei=session['user']).first()
        if geofence:
            db.session.delete(geofence)
            db.session.commit()
            return jsonify({"status": "success", "message": "Geofence deleted successfully"})
        else:
            return jsonify({"status": "error", "message": "Geofence not found"}), 404
    except Exception as e:
        mylogger.error(f"删除电子围栏失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/edit_geofence', methods=['GET'])
def edit_geofence_page():
    if not session.get('user'):
        return redirect(f'{cfg.home_url}/login')
    
    # 获取要编辑的电子围栏ID
    geofence_id = request.args.get('id')
    if not geofence_id:
        return redirect(f'{cfg.home_url}/fence')
    
    # 查询电子围栏数据
    geofence = GeoFence.query.filter_by(id=geofence_id, imei=session['user']).first()
    if not geofence:
        return redirect(f'{cfg.home_url}/fence')
    
    # 将WGS84坐标转换为BD09坐标
    bd_lng, bd_lat = wgs84_to_bd09(geofence.lng, geofence.lat)
    
    # 将数据传递给模板
    return render_template('modify_geofence.html', 
                         geofence=geofence,
                         bd_lat=bd_lat,
                         bd_lng=bd_lng,
                         baidu_ak=cfg.baidu_web_ak,
                         home_url=cfg.home_url,
                         static_url=cfg.static_url)

@app.route('/api/geofence/update', methods=['POST'])
def update_geofence():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.json
        geofence_id = data.get('id')
        if not geofence_id:
            return jsonify({"status": "error", "message": "Missing geofence ID"}), 400

        geofence = GeoFence.query.filter_by(id=geofence_id, imei=session['user']).first()
        if not geofence:
            return jsonify({"status": "error", "message": "Geofence not found"}), 404

        # 更新电子围栏信息
        geofence.lat = data.get('lat')
        geofence.lng = data.get('lng')
        geofence.radius = data.get('radius')
        geofence.address = data.get('address')
        geofence.timestamp = datetime.now()
        #前端传过来的坐标时BD09坐标，入库时需要转换一下到WGS84坐标
        geofence.lng,geofence.lat=bd09_to_wgs84(geofence.lng,geofence.lat)
        db.session.commit()
        return jsonify({"status": "success", "message": "Geofence updated successfully"})
    except Exception as e:
        mylogger.error(f"更新电子围栏失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cvt/wgs84_to_bd09', methods=['GET'])
def wgs84_to_bd09_api():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        lat = request.args.get('lat', default=0, type=float)
        lng = request.args.get('lng', default=0, type=float)
        if not lat or not lng:
            return jsonify({"status": "error", "message": "Missing lat or lng parameter"}), 400
        
        # 调用现有的 wgs84_to_bd09 函数进行坐标转换
        bd_lng, bd_lat = wgs84_to_bd09(lng, lat)
        
        return jsonify({
            "status": "success",
            "bd_lat": bd_lat,
            "bd_lng": bd_lng
        })
    except Exception as e:
        mylogger.error(f"坐标转换失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/share/track', methods=['POST'])
def share_track():
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.json
        imei = session['user']
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # 计算MD5值
        hash_input = f"{imei}{start_time}{end_time}"
        md5_hash = hashlib.md5(hash_input.encode()).hexdigest()
        
        # 将imei/start_time/end_time存入ShareTracker表
        with app.app_context():
            # 先查询是否已存在相同ID的记录
            existing_record = ShareTracker.query.filter_by(id=md5_hash).first()
            
            if existing_record:
                # 存在则更新现有记录
                existing_record.start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                existing_record.end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            else:
                # 不存在则创建新记录
                new_share_tracker = ShareTracker(
                    id=md5_hash,
                    imei=imei,
                    start_time=datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S'),
                    end_time=datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                )
                db.session.add(new_share_tracker)
            
            db.session.commit()
        
        # 返回MD5值
        return jsonify({
            "status": "success",
            "md5": md5_hash
        })
    except Exception as e:
        mylogger.error(f"分享轨迹失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sharetrack/<md5>')
def share_track_page(md5):
    # 根据md5值查询ShareTracker表，获取imei、start_time和end_time
    share_tracker = ShareTracker.query.filter_by(id=md5).first()
    if not share_tracker:
        return "<h1>未查找到对应的分享记录</h1>"
    
    imei = share_tracker.imei
    start_time = share_tracker.start_time
    end_time = share_tracker.end_time
    
    # 使用imei、start_time和end_time从ZipData表中筛选出数据
    records = ZipData.query.filter(
        ZipData.imei == imei,
        ZipData.timestamp.between(start_time, end_time)
    ).all()
    
    # 格式化查询结果为指定JSON格式
    result = [{
        "pt": record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        "lat": record.lat,
        "lng": record.lng
    } for record in records]
    
    # 将WGS84坐标转换为BD09坐标
    for r in result:
        r['lng'], r['lat'] = wgs84_to_bd09(r['lng'], r['lat'])
    
    # 计算轨迹总距离
    distance = calculate_distance(result)
    
    # 将数据传递给模板
    return render_template('history_templ.html', data=result, history=f"{start_time}--{end_time}", distance=distance,baidu_ak=cfg.baidu_web_ak,home_url=cfg.home_url,static_url=cfg.static_url)

@app.route('/api/locate/nearby', methods=['GET'])
def nearby_locators():
    #还没注册的，也没登录过的，就没有登录一说，就不可能有session，因此不能校验登录与否
    #if not session.get('user'):
        #return jsonify({"status": "error", "message": "Unauthorized"}), 401

    phone_lat = request.args.get('phone_lat', default=0, type=float)
    phone_lng = request.args.get('phone_lng', default=0, type=float)

    # 查询 user 表中所有的不同 imei
    user_imies = db.session.query(User.imei).distinct().all()
    user_imies_set = {imei[0] for imei in user_imies}

    # 计算时间阈值，即当前时间往前推30分钟
    time_threshold = datetime.now() - timedelta(minutes=30)

    # 查询 iot_data 表中不在 user_imies_set 中，并且 timestamp 在最近30分钟内的数据
    records = IotData.query.filter(
        ~IotData.imei.in_(user_imies_set),
        IotData.timestamp >= time_threshold
    ).all()

    # 去重 imei 的结果集
    result_imeis = set()

    # 遍历查询结果并计算距离
    for record in records:
        if record.lat==0:
            lat=record.agps_lat
            lng=record.agps_lng
        else:
            lat = record.lat
            lng = record.lng
        distance = geodesic((lat, lng), (phone_lat, phone_lng)).meters
        if distance < 5000:
            result_imeis.add(record.imei)

    # 返回结果
    return jsonify(list(result_imeis))

def run_mqtt():
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.connect(cfg.mqtt_server, cfg.mqtt_port, 60)
    mqtt_client.loop_forever()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 添加初始测试数据
        if IotData.query.count() == 0:
            init_data = IotData(
                imei='860678075954729',  # 确保imei字段存在
                timestamp=datetime.now(),
                temp=0,
                vbat=0,
                lat=0,
                lng=0,
                agps_lat=0,
                agps_lng=0,
                valid=True
            )
            db.session.add(init_data)
            db.session.commit()

    # 启动MQTT后台任务
    mqtt_thread = Thread(target=run_mqtt)
    mqtt_thread.daemon = True
    mqtt_thread.start()

    # 启动电子围栏检查后台任务
    from check_fence import check_geofence
    geofence_thread = Thread(target=check_geofence)
    geofence_thread.daemon = True
    geofence_thread.start()
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    #openssl req -x509 -newkey rsa:4096 -nodes -out server.crt -keyout server.key -days 365
    context.load_cert_chain('server.crt', 'server.key')
    if cfg.flask_ssl:
        app.run(host='0.0.0.0', debug=True, use_reloader=False, port=cfg.web_port,ssl_context=context)
    else:
        app.run(host='0.0.0.0', debug=True, use_reloader=False, port=cfg.web_port)