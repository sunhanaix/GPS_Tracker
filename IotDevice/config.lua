-- 配置参数类信息
imei=mobile.imei()
local config = {
    imei=imei,
    luatos_version=rtos.version(),
    -- MQTT 配置
    mqtt = {
        broker = "x.x.x.x",
        port = 1883,
        user = "sunbeat",
        passwd = "A$e!2d9202",
        autoreconn_interval = 3,  -- 多少秒重连一次
        update_interval = 60,  --多少秒mqtt上报一次数据
        pub_topic = "/tracker/" .. imei .. "/up/stat",
        pub_cmd_topic = "/tracker/" .. imei .. "/up/cmd",
        sub_topic = "/tracker/" .. imei .. "/down/cmd",
    },
    power_mode=0,  --省电模式，0:正常模式， 1:低功耗模式，2:极度省电模式
    wdt={ --watchdog配置
        init_wait = 9, --初始化watchdog设置为9s
        feed_interval = 5, --5s喂一次狗
    },

    -- GNSS 配置
    gnss = {
        led_pin= 24, --定位状态指示灯引脚定义
        uart_id = 2, -- GNSS串口定义
        uart_forward = uart.VUART_0, --GNSS串口转发uart虚拟串口定义
        baudrate = 115200, -- Air780EG工程样品的GPS的默认波特率是9600, 量产版是115200,以下是临时代码
        sys=5, --GPS+北斗+GLONASS混合模式
        debug = false
    },

}

-- 初始化存储
fskv.init()
config.version=fskv.get("version")
-- 检查fskv中是否存在配置数据
local fskv_config = fskv.get("config")
if not fskv_config then
    -- 如果fskv中没有数据，则将默认配置写入fskv
    fskv.set("config", config)
else
    -- 如果fskv中有数据，则从fskv中读取配置数据并覆盖默认配置
    fskv_config.version=config.version
    config = fskv_config
end

return config
