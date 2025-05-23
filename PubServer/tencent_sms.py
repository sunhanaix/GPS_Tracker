import os,sys,re,json
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.sms.v20210111 import sms_client, models
# 导入可选配置类
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
import air_config as cfg
mylogger=cfg.logger
cred = credential.Credential(cfg.tencent_SecretId, cfg.tencent_SecretKey)
httpProfile = HttpProfile()
httpProfile.reqMethod = "POST"
httpProfile.reqTimeout = 10
httpProfile.endpoint = "sms.tencentcloudapi.com"
clientProfile = ClientProfile()
clientProfile.signMethod = "TC3-HMAC-SHA256"
clientProfile.language = "en-US"
clientProfile.httpProfile = httpProfile
def send_valid_sms(phone,code):
    client = sms_client.SmsClient(cred, "ap-beijing", clientProfile)
    req = models.SendSmsRequest()
    req.SmsSdkAppId = cfg.tencent_sms_appid
    req.SignName = cfg.tencent_sms_sign
    req.TemplateId = cfg.tencent_sms_validate_template_id
    req.TemplateParamSet = [str(code)]
    req.PhoneNumberSet = [str(phone)]
    req.SessionContext = ""
    try:
        resp = client.SendSms(req)
        #print(resp.to_json_string())
        if resp.SendStatusSet[0].Code == "Ok":
            return True
        else:
            mylogger.error(f"发送验证码失败:{resp.to_json_string()}",exc_info=True)
            return False
    except TencentCloudSDKException as err:
        mylogger.error(f"发送验证码失败:{err}",exc_info=True)
        print(err)
    except Exception as e:
        mylogger.error(f"发送验证码失败:{e}",exc_info=True)

def get_sms_status():
    client = sms_client.SmsClient(cred, "ap-beijing",clientProfile)
    req = models.PullSmsSendStatusRequest()
    req.SmsSdkAppId = cfg.tencent_sms_appid
    # 拉取最大条数，最多100条
    req.Limit = 10
    resp = client.PullSmsSendStatus(req)
    # 输出json格式的字符串回包
    print(resp.to_json_string(indent=2))

def send_notify_sms(phone,dev_id,address):
    client = sms_client.SmsClient(cred, "ap-beijing",clientProfile)
    req = models.SendSmsRequest()
    req.SmsSdkAppId = cfg.tencent_sms_appid
    req.SignName = cfg.tencent_sms_sign
    req.TemplateId = cfg.tencent_sms_notify_template_id
    req.TemplateParamSet = [str(dev_id),str(address)]
    req.PhoneNumberSet = [str(phone)]
    req.SessionContext = ""
    try:
        resp = client.SendSms(req)
        #print(resp.to_json_string())
        if resp.SendStatusSet[0].Code == "Ok":
            return True
        else:
            mylogger.error(f"发送通知短信失败:{resp.to_json_string()}",exc_info=True)
            return False
    except TencentCloudSDKException as err:
        mylogger.error(f"发送通知短信失败:{err}",exc_info=True)
        print(err)
    except Exception as e:
        mylogger.error(f"发送通知短信失败:{e}",exc_info=True)


if __name__ == '__main__':
    phone='13812341234'
    code=332244
    device_id='123456789012345'
    address='天安门广场'
    send_valid_sms(phone,code)
    #send_notify_sms(phone,device_id,address)
    get_sms_status()