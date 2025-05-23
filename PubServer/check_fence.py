import time
from datetime import datetime, timedelta
from geopy.distance import geodesic
from models import db, ZipData, GeoFence
import air_config as cfg
import models
from alert import send_email, send_sms, send_xiatui_alert
from  Baidu import get_address_by_coords,wgs84_to_bd09,bd09_to_wgs84
app=models.app

mylogger=cfg.logger
def check_geofence():
    """
    后台任务：定期检查设备坐标是否超出电子围栏范围
    """
    while True:
        try:
            # 查询所有设备的最新坐标
            with app.app_context():
                # 优化查询：先获取每个设备的最新时间戳，再查询对应的记录
                latest_timestamps = db.session.query(
                    ZipData.imei,
                    db.func.max(ZipData.timestamp).label('latest_timestamp')
                ).group_by(ZipData.imei).subquery()

                latest_records = db.session.query(ZipData).join(
                    latest_timestamps,
                    (ZipData.imei == latest_timestamps.c.imei) &
                    (ZipData.timestamp == latest_timestamps.c.latest_timestamp)
                ).all()

                imei_records = {record.imei: record for record in latest_records}

                # 查询所有电子围栏
                fences = GeoFence.query.all()

                # 检查每个设备是否超出电子围栏范围
                for imei, record in imei_records.items():
                    device_coord = (record.lat, record.lng)
                    #设置一个初始标志位，是否超出围栏，然后遍历所有电子围栏，每一个都超出，才算超出围栏，进行告警
                    inside_flag=True #默认假设处于围栏内
                    for fence in fences:
                        if fence.imei == imei:
                            fence_coord = (fence.lat, fence.lng)
                            distance = geodesic(device_coord, fence_coord).meters
                            if distance > fence.radius:
                                inside_flag=False
                            else:
                                inside_flag=True #只要有一个没超出，则说明没有超出围栏
                                break
                    if not inside_flag: #如果所有围栏都超出了，则进行告警
                        address = get_address_by_coords(record.lat, record.lng)
                        # 记录日志
                        mylogger.warning(f"告警: 设备 {imei} 超出电子围栏范围，跑到了{address}")

                        # 获取用户信息
                        user = models.User.query.filter_by(imei=imei).first()

                        if user:
                            # 检查上次告警时间是否在1小时内
                            if user.notify_time and (datetime.now() - user.notify_time).total_seconds() < cfg.geofence_alert_cooldown:
                                mylogger.warning(f"设备 {imei} 超出电子围栏范围，但冷却时间内已发送过告警，不再重复发送")
                                continue

                            message = f"设备 {imei} 超出电子围栏范围，跑到了{address}"

                            # 发送短信通知
                            if user.enable_notify_phone and user.notify_phone:
                                send_sms(user.notify_phone, imei,address)

                            # 发送邮件通知
                            if user.enable_notify_email and user.notify_email:
                                send_email(user.notify_email, message)

                            # 使用虾推key发送通知
                            if user.enable_xiatui and user.xiatui_key:
                                 send_xiatui_alert(user.xiatui_key, message)

                            # 更新上次告警时间
                            user.notify_time = datetime.now()
                            mylogger.info(f"更新{imei}的冷却时间到当前时间{user.notify_time}")
                            db.session.commit()
                    else:
                        mylogger.warning(f"设备 {imei} 没有超出电子围栏范围")
                        # 如果设备返回电子围栏内，则更新上次告警时间
                        user = models.User.query.filter_by(imei=imei).first()
                        if user:
                            user.notify_time = datetime.now()
                            mylogger.info(f"更新{imei}的冷却时间到当前时间{user.notify_time}")
                            db.session.commit()

                # 等待一段时间后再次检查
                time.sleep(cfg.geofence_check_interval)

        except Exception as e:
            mylogger.error(f"检查电子围栏失败: {str(e)}",  exc_info=True)
            time.sleep(cfg.geofence_check_interval)

if __name__ == "__main__":
    check_geofence()