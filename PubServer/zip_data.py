#!/usr/local/bin/python3.12
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import air_config as cfg
import models

app=models.app
IotData=models.IotData
ZipData=models.ZipData
db=models.db
def copy_and_filter_data(imei):  # 新增imei参数，默认值为当前设备IMEI
    with app.app_context():
        # 创建zip_data表
        db.create_all()

        # 获取zip_data表中最大的id
        max_id = db.session.query(db.func.max(ZipData.id)).filter_by(imei=imei).scalar()  # 根据imei过滤数据
        if max_id is None:
            max_id = 0

        # 查询iot_data表中id大于max_id的数据
        iot_data_records = db.session.query(IotData).filter(IotData.id > max_id, IotData.imei == imei).order_by(IotData.timestamp).all()  # 根据imei过滤数据

        last_lat = None
        last_lng = None
        i=0
        for record in iot_data_records:
            i+=1
            #每10条记录，提交一次数据库事务，以及显示当前进度
            if i % 10 == 0:
                db.session.commit()
                print(f'已处理{i}条记录')
            # 确定lat和lng的值
            lat = record.lat if record.lat != 0 else record.agps_lat
            lng = record.lng if record.lng != 0 else record.agps_lng

            # 如果当前记录的lat和lng与上一条记录相同，则删除上一条记录
            if lat == last_lat and lng == last_lng:
                last_record = ZipData.query.order_by(ZipData.timestamp.desc()).first()
                if last_record:
                    db.session.delete(last_record)
                    db.session.commit()

            # 检查目标端最新记录与当前记录的坐标是否相同
            latest_zip_record = ZipData.query.order_by(ZipData.timestamp.desc()).first()
            if latest_zip_record and lat == latest_zip_record.lat and lng == latest_zip_record.lng:
                db.session.delete(latest_zip_record)
                db.session.commit()

            # 插入新记录到zip_data表
            zip_record = ZipData(
                id=record.id,
                imei=imei,  # 添加imei字段
                timestamp=record.timestamp,
                vbat=record.vbat,
                lat=lat,
                lng=lng
            )
            db.session.add(zip_record)
            db.session.commit()

            # 更新last_lat和last_lng
            last_lat = lat
            last_lng = lng
        print(f'数据处理完成，共处理{i}条数据')


if __name__ == '__main__':
    with app.app_context():
        # 确保数据库表结构已更新
        db.create_all()
        
        # 获取所有唯一的imei设备
        imei_list = db.session.query(IotData.imei).distinct().all()
        for imei_tuple in imei_list:
            imei = imei_tuple[0]
            print(f'开始处理设备IMEI: {imei}')
            copy_and_filter_data(imei)
            print(f'设备IMEI: {imei} 处理完成')