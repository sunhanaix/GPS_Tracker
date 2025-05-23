import os,sys,re,json,logging,random
##自己的MQTT Server信息
mqtt_server = 'x.x.x.x' #MQTT服务器地址
mqtt_port = 1883
mqtt_user='sunbeat' #MQTT用户名
mqtt_password='A$e!2d9202' #MQTT密码
app_name=os.path.basename(sys.argv[0])
mqtt_client_id=f'{app_name}-client{random.randint(100,999)}'

battery_feature={
    #'vbat_min':2725,
    'vbat_min':3231,
    'vbat_max':4034,
#    'vbat_max':4172,
}

db_file='iot_data.db' #数据库文件名
default_password='88888888' #定位器IMEI串号对应的的默认密码
baidu_ak='uXczF9m32qrU2P3wCPLG8Yuwxxxxx' #python调用百度地图接口使用的ak，需要自己去百度申请
baidu_web_ak='jTcFZKmaSpevmx4hfXKYvcxxxxx' #百度地图的浏览器使用的ak，需要自己去百度申请

map_refresh_interval=60 #百度地图刷新间隔
exp_days = 90  # 设置浏览器cookie过期时间
#判断当前程序运行的环境，如果linux，则使用公网地址，否则使用本地地址
home_url = 'https://x.x.x.x/tracker'
static_url = f'{home_url}/static'
app_name='Tracker'
firmware_dir = 'static/firmware'
firmware_url_dir=f'{{static_url}}/firmware'
geofence_check_interval=60 #地理围栏检查间隔（s）
geofence_alert_cooldown=3600 #地理围栏报警的冷却时间（s），避免频繁报警
flask_ssl=False  #是否启用flask的ssl，生产环境，建议不要起。ssl由nginx/apache代理来做。测试环境，可以启用。因为没有https的话，chrome不支持申请定位权限
web_port=45018

#设置邮件服务器、发件者等消息
FROM_EMAIL='xxxx@qq.com'
EMAIL_PASSWORD='nyzlzbhxxxxxx'  #对于开启二次验证的邮箱，这里要填写授权码，而不是web登录的密码
SMTP_SERVER='smtp.qq.com'
SMTP_PORT=465

#设置乐讯通的 短信服务器、发件者等消息
sms_username='13512341234'  #乐讯通的账号
sms_password='pass1234' #乐讯通的密码
sms_notify_template_id='62D656FE' #短信通知的模板id
sms_notify_token='a73329c0'  #短信通知的token
sms_validate_template_id='6EA1E4A2' #短信验证码的模板id
sms_validate_token='dcaf2243' #短信验证码的token

#设置腾讯云短信的相关配置
tencent_SecretId='AKIDoRpxoPlsjJdgTxxxxxxx'
tencent_SecretKey='B6l9H9l7D3vlNkrjLhxxxxx'
tencent_sms_appid='223151234'
tencent_sms_appkey='2faf44842c375bd7f12f1e12345'
tencent_sms_validate_template_id='2420123'
tencent_sms_notify_template_id='2420456'
tencent_sms_sign='定位器'

debug=1
#以下部分可以不用修改
#当前程序运行的绝对路径
app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
#程序输出的log名字，这里用了"程序名.log"的格式
log_file = os.path.basename(sys.argv[0]).split('.')[0] + '.log'
log_file=os.path.join(app_path,log_file)
#定log输出格式，配置同时输出到标准输出与log文件
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
log_format= logging.Formatter(
    '%(asctime)s - %(name)s - %(filename)s- %(levelname)s - %(message)s')
log_fh = logging.FileHandler(log_file)
log_fh.setLevel(logging.DEBUG)
log_fh.setFormatter(log_format)
log_ch = logging.StreamHandler()
log_ch.setLevel(logging.DEBUG)
log_ch.setFormatter(log_format)
logger.addHandler(log_fh)
logger.addHandler(log_ch)
