local cfg = require("config")
local mygnss = require("myGNSS")

local mqttc = nil
fskv.init()

adc.setRange(adc.ADC_RANGE_3_8) --air780E开启ADC0,1分压电阻，范围0~3.8V
adc.open(adc.CH_VBAT)
adc.open(adc.CH_CPU)
log.info("CH_VBAT=", adc.CH_VBAT, "CH_CPU=", adc.get(adc.CH_CPU))


-- 系统似乎没有现成的合并两个dict的函数，自己实现一个
local function mergeTables(...)
    local result = {}
    for _, tbl in ipairs{...} do
        for k, v in pairs(tbl) do
            if type(v) == "string" then
                result[k] = v:gsub("[\x00-\x1F\x7F-\xFF]", "") -- 过滤非打印字符
            else
                result[k] = v
            end
        end
    end
    return result
end
--系统不带深拷贝，自己实现一个深拷贝
local function deepCopy(orig)
    local copy = {}
    for k, v in pairs(orig) do
        if type(v) == "table" then
            v = deepCopy(v)
        end
        copy[k] = v
    end
    return copy
end

function fota_cb(ret)
    log.info("fota", ret)
    if ret == 0 then
        log.info("fota更新微码成功")
        rtos.reboot()
    else
        log.info("fota更新微码失败！")
    end
end

function upload_stat(up_cfg)
    -- 关掉省电模式，好能够使用GPS等
    pm.power(pm.WORK_MODE, 0)
    pm.power(pm.GPS, true)
    local status={
        csq = mobile.csq(),
        rssi = mobile.rssi(),
        rsrq = mobile.rsrq(),
        rsrp = mobile.rsrp(),
        snr = mobile.snr(),
        sn= mobile.sn(),
        imsi = mobile.imsi(),
        imei = cfg.imei,
        ip=socket.localIP(),
        vbat = adc.get(adc.CH_VBAT),
        temp = adc.get(adc.CH_CPU),
        memsys = {rtos.meminfo("sys")},
        memlua = {rtos.meminfo()},
    }
    log.info("device status=",json.encode(status))

    mygnss.refresh()
    --sys.waitUntil("CELL_INFO_UPDATE")
    sys.waitUntil("GNSS_STATE",3000)
    local gnss_info=mygnss.res
    log.info("gnss info=",json.encode(gnss_info))

    local wifi_info={}
    wifi_info.wifi = {}
    wifi_info.wifi_ts=os.time()

    stat=mergeTables(status,gnss_info,wifi_info)
    stat.uptime=fskv.get("uptime")
    stat.up_vbat=fskv.get("up_vbat")
    if up_cfg then
        stat.cfg=cfg
    else
        stat.cfg=nil
    end
    log.info("stat", json.encode(stat))
    if mqttc and mqttc:ready() then
        local payload = json.encode(stat)
        mqttc:publish(cfg.mqtt.pub_topic, payload, 1)
    end
    if cfg.power_mode==0 then
        log.info("正常耗电模式")
    elseif cfg.power_mode==1 then
        log.info("省电模式")  --省电模式下，流量还没关，还能上网
        pm.power(pm.GPS, false)
        pm.power(pm.WORK_MODE, 1)
    else
        log.info("极省电模式，目前还不支持")
        pm.power(pm.GPS, false)
        pm.power(pm.WORK_MODE, 1)  --极度省电模式下，pm.power(pm.WORK_MODE, 2)，系统进入睡眠，等到下次唤醒时，才能继续运行，实现模式要另外处理
    end
end

function on_downlink(topic, payload)
    log.info("检测到mqtt订阅topic", topic, "过来的消息", "负载:", payload)
    local cmd = json.decode(payload)
    if not cmd then
        log.error("json.decode失败", cmd) -- cmd 在这里包含错误信息
        return
    end
    if cmd.command == "set_update_interval" then
        log.info("收到命令", cmd.command, "参数", cmd.value)
        cfg.mqtt.update_interval = cmd.value
        log.info("尝试写入配置，然后等待重启")
        fskv.set("config", cfg)
        --sys.wait(1000) --前面的on_downlink已经是在协程中了，这里要是阻塞，会报错syscall outside of coroutine
        pm.reboot()
    elseif cmd.command == "set_feed_interval" then
        log.info("收到命令", cmd.command, "参数", cmd.value)
        cfg.wdt.feed_interval = cmd.value
        log.info("尝试写入配置，然后等待重启")
        fskv.set("config", cfg)
        --sys.wait(1000) --前面的on_downlink已经是在协程中了，这里要是阻塞，会报错syscall outside of coroutine
        pm.reboot()
    elseif cmd.command == "report_status" then
        log.info("收到命令", cmd.command)
        sys.taskInit(upload_stat)  -- 将upload_stat包装为协程
    elseif cmd.command == "reboot" then
        log.info("收到命令", cmd.command)
        --sys.wait(1000) --前面的on_downlink已经是在协程中了，这里要是阻塞，会报错syscall outside of coroutine
        pm.reboot()
    elseif cmd.command == "get_config" then
        log.info("收到命令", cmd.command)
        local cmd_data={}
        cmd_data.ts=os.time()
        cmd_data.cfg = deepCopy(cfg)
        --把cmd_data.cfg.mqtt.user 和 cfg.mqtt.passwd 置空，防止敏感信息泄漏
        cmd_data.cfg.mqtt.user = nil
        cmd_data.cfg.mqtt.passwd = nil
        if mqttc and mqttc:ready() then
            mqttc:publish(cfg.mqtt.pub_cmd_topic, json.encode(cmd_data), 1)
        else
            log.error("MQTT连接未就绪，尝试重新连接")
            mqttc:connect()
            mqttc:publish(cfg.mqtt.pub_cmd_topic, json.encode(cmd_data), 1)
        end
    elseif cmd.command == "set_config" then
        log.info("收到命令", cmd.command, "参数", cmd.value)
        --判断是否有cmd.value.mqtt.update_interval，有的话，就替换掉cfg.mqtt.update_interval
        if cmd.value.update_interval  then
            cfg.mqtt.update_interval = cmd.value.update_interval
        end
        if cmd.value.feed_interval then
            cfg.wdt.feed_interval = cmd.value.feed_interval
        end
        --判断power_mode是否在cmd.value中
        if type(cmd.value.power_mode) ~= "nil" then
            cfg.power_mode = cmd.value.power_mode
        end
        log.info("当前配置为:",json.encode(cfg))
        log.info("尝试写入配置，然后等待重启")
        fskv.set("config", cfg)
        pm.reboot()
    --增加响应更新固件版本请求
    elseif cmd.command == "update_firmware" then
        log.info("收到命令", cmd.command, "参数", cmd.value)
        if cmd.value then
            log.info("开始更新固件")
            libfota = require "libfota"
            firmware_url=cmd.value
            log.info("firmware_url=",firmware_url)
            libfota.request(fota_cb, firmware_url)
        end
    end
end

sys.taskInit(function()
    sys.waitUntil("IP_READY", 15000)
    sys.waitUntil("NTP_UPDATE", 1000)
    fskv.set("uptime", os.time()) --记录下上次启动的时间
    fskv.set("up_vbat", adc.get(adc.CH_VBAT))  --记录下上次启动的电压
    mqttc = mqtt.create(nil, cfg.mqtt.broker, cfg.mqtt.port)
    mqttc:auth(mobile.imei(), cfg.mqtt.user, cfg.mqtt.passwd)
    log.info("mqtt", mobile.imei(), mobile.imei(), mobile.muid())
    mqttc:keepalive(30) -- 默认值240s
    mqttc:autoreconn(true, cfg.mqtt.autoreconn_interval*1000) -- 自动重连机制
    mqttc:on(function(mqtt_client, event, data, payload) -- mqtt回调注册
        --[[
            event可能出现的值有
              conack -- 服务器鉴权完成,mqtt连接已经建立, 可以订阅和发布数据了,没有附加数据
              recv   -- 接收到数据,由服务器下发, data为topic值(string), payload为业务数据(string).metas是元数据(table), 一般不处理.
                         -- metas包含以下内容
                         -- qos 取值范围0,1,2
                         -- retain 取值范围 0,1
                         -- dup 取值范围 0,1
              sent   -- 发送完成, qos0会马上通知, qos1/qos2会在服务器应答会回调, data为消息id
              disconnect -- 服务器断开连接,网络问题或服务器踢了客户端,例如clientId重复,超时未上报业务数据
              pong   -- 收到服务器心跳应答,没有附加数据
            ]]
        -- 用户自定义代码，按event处理
        if event == "conack" then
            sys.publish("mqtt_conack") -- 小写字母的topic均为sys自定义topic
            mqtt_client:subscribe(cfg.mqtt.sub_topic)
        elseif event == "recv" then -- 服务器下发的数据
            log.info("mqtt", "downlink", "topic", data, "payload", payload)
            local dl = json.decode(data)
            local topic=data
            on_downlink(topic, payload)
        elseif event == "sent" then -- publish成功后的事件
            log.info("mqtt", "sent", "pkgid", data)
        end
    end)
    mqttc:connect()
    sys.waitUntil("mqtt_conack")
    log.info("mqtt连接成功")
    --[[
        sys.waitUntil 是一个协程阻塞函数，只能在 sys.taskInit 创建的协程或事件回调中使用。
        upload_stat 函数被 sys.timerLoopStart 直接调用，而定时器回调默认不在协程环境中运行，导致非法调用阻塞函数。
        将 upload_stat 包装为协程就可以了
    ]]
    upload_stat()
    sys.timerLoopStart(function()  sys.taskInit(upload_stat) end, cfg.mqtt.update_interval*1000)
    while true do
        sys.wait(60*1000)
    end
    mqttc:close()
    mqttc = nil
end)

