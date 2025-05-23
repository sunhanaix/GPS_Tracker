import os,sys,re,json,time,random
from hashlib import md5
import requests
import air_config as cfg

mylogger=cfg.logger

#使用乐讯通短信平台发送短信
#http://yun.loktong.com/login/login
def MD5(ss):
    return md5(ss.encode()).hexdigest().upper()

def send_valid_sms(phone,code): #给指定号码的用户，发送验证码
    '''
    :param phone: 要发送短信的手机号码
    :param code:  验证码
    :return:  返回成功True或者失败False/None
    '''
    url='http://www.lokapi.cn/smsUTF8.aspx'
    data={
        'action':'sendtemplate',
        'username':cfg.sms_username,
        'password': MD5(cfg.sms_password),
        'token':cfg.sms_validate_token,
        'templateid':cfg.sms_validate_template_id,
        'param':f'{phone}|{code}',
        'timestamp': int(time.time()*1000),
    }
    body = f"action={data['action']}&username={data['username']}&password={data['password']}&token={data['token']}&timestamp={data['timestamp']}"
    sign=MD5(body)
    data['sign']=sign
    if cfg.debug:
        mylogger.debug(f"body={body}")
        mylogger.debug(f"data={data}")
    r=requests.post(url,data=data)
    if not r:
        mylogger.error("send_sms() post failure")
        return False
    try:
        res=r.json()
    except Exception as e:
        mylogger.error(f"send_sms() result can not be converted to dict,result={r.text}")
        return False
    if not 'code' in res:
        mylogger.error(f"send_sms() not code in result,result={res}")
        return False
    if int(res['code'])==0:
        return True
    else:
        mylogger.error(f"send_sms() code != ,result={res}")
        return False

def send_notify_sms(phone,dev_id,address): #发送通知短信
    url='http://www.lokapi.cn/smsUTF8.aspx'
    #由于模版设置了dev_id为s15，不能超过15个字符，所以只能使用dev_id的前15个字符
    dev_id=dev_id[:15]
    #地址只能发送不超过20个汉字
    address=re.sub(r'[^\u4e00-\u9fa5]', '', address)[:20]
    data={
        'action':'sendtemplate',
        'username':cfg.sms_username,
        'password': MD5(cfg.sms_password),
        'token':cfg.sms_notify_token,  # 使用通知专用token
        'templateid':cfg.sms_notify_template_id,
        'param':f'{phone}|{dev_id}|{address}',  # 参数字符串按模板要求构造
        'timestamp': int(time.time()*1000),
    }
    body = f"action={data['action']}&username={data['username']}&password={data['password']}&token={data['token']}&timestamp={data['timestamp']}"
    # 签名生成需要按参数顺序拼接
    data['sign'] = MD5(body)
    if cfg.debug:
        mylogger.debug(f"send_notify_sms data: {data}")
    
    try:
        r = requests.post(url, data=data, timeout=10)
        res = r.json()
        if res.get('code') == '0':
            return True
        else:
            mylogger.error(f"发送失败: {res}")
            return False
    except Exception as e:
        mylogger.error(f"请求异常: {str(e)}")
        return False

def sms_remain():  #剩余短信条数查询
    url='http://www.lokapi.cn/smsUTF8.aspx'
    data={
        'action':'overage',
        'username':cfg.sms_username,
        'password': MD5(cfg.sms_password),
        'token':'dcaf3795',
        'timestamp': int(time.time()*1000),
    }
    body = f"action={data['action']}&username={data['username']}&password={data['password']}&token={data['token']}&timestamp={data['timestamp']}"
    sign=MD5(body)
    data['sign']=sign
    if cfg.debug:
        mylogger.info(f"body={body}")
        mylogger.info(f"data={data}")
    r=requests.post(url,data=data)
    if not r:
        mylogger.error("sms_remain() post failure")
        return False
    try:
        res=r.json()
    except Exception as e:
        mylogger.error(f"sms_remain() result can not be converted to dict,result={r.text}")
        return False
    if not 'code' in res:
        mylogger.error(f"sms_remain() not code in result,result={res}")
        return False
    if int(res['code'])==0:
        return res['overage']
    else:
        mylogger.error(f"sms_remain() code != ,result={res}")
        return False


if __name__=='__main__':
    code=random.randint(100000,999999)
    res=send_valid_sms('13812341234',code)
    #res=send_notify_sms('13812341234', '860678075954729', '天安门广场')
    #res = sms_remain()
    if res:
        mylogger.info(f"send ok,res={res}")
    else:
        mylogger.info("send failure")