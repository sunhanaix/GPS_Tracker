import sys,os,requests
import air_config as cfg
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import parseaddr, formataddr
from loktong_sms import send_notify_sms

mylogger=cfg.logger
def send_sms(phone_number, dev_id,address):
    """发送短信通知"""
    mylogger.info(f"发送短信到 {phone_number},{dev_id=},{address=}")
    try:
        send_notify_sms(phone_number,dev_id,address)
    except Exception as e:
        mylogger.error(f"短信发送失败: {str(e)}")

def send_email(email_address, message):
    """发送邮件通知"""
    # 获取SMTP配置
    smtp_server = cfg.SMTP_SERVER
    smtp_port = cfg.SMTP_PORT
    from_addr = cfg.FROM_EMAIL
    password = cfg.EMAIL_PASSWORD

    # 构建邮件消息
    msg = MIMEMultipart()
    msg['From'] = formataddr((parseaddr(from_addr)[1], from_addr))
    msg['To'] = email_address
    msg['Subject'] = Header('定位器紧急通知', 'utf-8').encode()  # 支持中文主题

    # 添加邮件正文
    msg.attach(MIMEText(message, 'plain', 'utf-8'))

    # SMTP发送逻辑
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        #server.set_debuglevel(1)
        server.login(from_addr, password)
        server.sendmail(from_addr, [email_address], msg.as_string())
        server.quit()
        mylogger.info(f"邮件成功发送至 {email_address}")
    except Exception as e:
        mylogger.error(f"邮件发送失败: {str(e)}", file=sys.stderr)

def send_xiatui_alert(api_key, message):
    """发送虾推通知"""
    mydata={
        'text':message,
        'desp':message,
        }
    #给"虾推啥"发条消息，由它推给微信
    #mylogger.warning(msg)
    post_url=f'http://wx.xtuis.cn/{api_key}.send'
    try:
        r=requests.post(post_url, data=mydata)
        #判断是否发送成功
        if r.status_code==200:
            mylogger.info(f"虾推发送通知成功: {message}")
        else:
            mylogger.error(f"虾推发送通知失败")
    except Exception as e:
        mylogger.error(f"虾推发送通知失败: {str(e)}")