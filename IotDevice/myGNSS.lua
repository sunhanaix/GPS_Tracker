local myGNSS = {
    version = "1.0.1"
}

local sys = require("sys")
local cfg = require("config")
myGNSS.res={}
myGNSS.opts={}

myGNSS.res={
    lat=0,
    lng=0,
    gps_ts=0,
    agps_lat=0,
    agps_lng=0,
    agps_ts=0,
    cellinfo={},
}

function myGNSS.setup(opts)
    myGNSS.opts = opts
    if not myGNSS.opts.uart_id then
        myGNSS.opts.uart_id = 2
    end
end

function myGNSS.start()
    -- 初始化串口
    -- libgnss库初始化
    libgnss.clear() -- 清空数据,兼初始化
    -- LED和ADC初始化
    gpio.setup(cfg.gnss.led_pin, 0) -- GNSS定位成功灯
    -- 串口初始化
    uart.setup(cfg.gnss.uart_id, cfg.gnss.baudrate)
    local gps_uart_id = myGNSS.opts.uart_id
    local opts = myGNSS.opts
    local write = myGNSS.writeCmd
    uart.setup(gps_uart_id, myGNSS.opts.baudrate)
    log.info("myGNSS opts",json.encode(opts))
    -- 是否为调试模式
    if opts.debug then
        libgnss.debug(true)
    end
    if myGNSS.opts.uart_forward then
        uart.setup(myGNSS.opts.uart_forward, myGNSS.opts.baudrate)
        log.info("libgnss.bind(gps_uart_id, myGNSS.opts.uart_forward)")
        libgnss.bind(gps_uart_id, myGNSS.opts.uart_forward)
    else
        log.info("libgnss.bind(gps_uart_id)")
        libgnss.bind(gps_uart_id)
    end

    -- 是否需要切换定位系统呢?
    if opts.sys then
        if type(opts.sys) == "number" then
            if opts.sys == 1 then
                log.info("try 启用GPS纯定位模式（H01）")
                uart.write(gps_uart_id, "$CFGSYS,H01\r\n") --纯GPS模式
            elseif opts.sys == 2 then
                log.info("try 启用GPS+GLONASS混合模式（H10），myGNSS.opts.sys=", opts.sys)
                uart.write(gps_uart_id, "$CFGSYS,H10\r\n") --纯北斗模式
            elseif opts.sys == 5 then
                log.info("try 启用GPS+GLONASS混合模式（H101），myGNSS.opts.sys=", opts.sys)
                uart.write(gps_uart_id, "$CFGSYS,H101\r\n") --GPS+北斗+GLONASS混合模式
            else
                log.info("try 启用GPS+北斗混合模式（H11），myGNSS.opts.sys=", opts.sys)
                uart.write(gps_uart_id, "$CFGSYS,H11\r\n") --GPS+北斗混合模式（H11）
            end
        end
    end

    if not opts.nmea_ver or opts.nmea_ver == 41 then
        uart.write(gps_uart_id, "$CFGNMEA,h51\r\n") -- 切换到NMEA 4.1
    end

    -- 打开全部NMEA语句
    if opts.rmc_only then
        uart.write(gps_uart_id, "$CFGMSG,0,0,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,1,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,2,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,3,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,4,1\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,5,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,6,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,7,0\r\n")
        sys.wait(20)
    elseif myGNSS.opts.no_nmea then
        uart.write(gps_uart_id, "$CFGMSG,0,0,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,1,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,2,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,3,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,4,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,5,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,6,0\r\n")
        sys.wait(20)
        uart.write(gps_uart_id, "$CFGMSG,0,7,0\r\n")
        sys.wait(20)
    else
        uart.write(gps_uart_id, "$CFGMSG,0,0,1\r\n") -- GGA
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,1,1\r\n") -- GLL
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,2,1\r\n") -- GSA
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,3,1\r\n") -- GSV
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,4,1\r\n") -- RMC
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,5,1\r\n") -- VTG
        sys.wait(10)
        uart.write(gps_uart_id, "$CFGMSG,0,6,1\r\n") -- ZDA
        sys.wait(10)
        -- uart.write(gps_uart_id, "$CFGMSG,0,7,1\r\n") -- GST
        -- sys.wait(10)
    end
     -- 设置更快的定位更新率
    uart.write(gps_uart_id, "$CFGPRT,1,0,115200,3,0,0*18\r\n")
    sys.wait(20)
    uart.write(gps_uart_id, "$CFGMSG,1,1000*1F\r\n") -- 1Hz更新率
    sys.wait(20)

    -- 设置更优的卫星搜索策略
    uart.write(gps_uart_id, "$CFGSBAS,1,1,1,1*59\r\n") -- 启用SBAS
    sys.wait(20)
end

function myGNSS.writeCmd(cmd)
    log.info("myGNSS", "写入指令", cmd:trim())
    uart.write(myGNSS.opts.uart_id, cmd)
end

function myGNSS.reboot(mode)
    local cmd = "$RESET,0,"
    if not mode then
        mode = 0
    end
    if mode == 2 then
        cmd = cmd .. "hff\r\n"
    elseif mode == 1 then
        cmd = cmd .. "h01\r\n"
    else
        cmd = cmd .. "h00\r\n"
    end
    uart.write(myGNSS.opts.uart_id, cmd)
    if mode == 2 then
        myGNSS.agps_tm = nil
    end
    libgnss.clear()
end

function myGNSS.stop()
    uart.close(myGNSS.opts.uart_id)
end

--封装一个getRMC函数，传递给libgnss
function myGNSS.getRMC(mode)
    return libgnss.getRmc(mode)
end

function myGNSS.refresh()
    mobile.reqCellInfo(15)
    myGNSS.agps(1)
end

sys.subscribe("CELL_INFO_UPDATE", function()
    --[[
    1. 基本网络标识
        字段	含义	示例值	说明
        mcc	Mobile Country Code（移动国家代码）	460	标识国家（中国为 460）。
        mnc	Mobile Network Code（移动网络代码）	0	标识运营商（中国移动 00/02，联通 01，电信 03）。
        tac	Tracking Area Code（跟踪区代码）	4277	用于手机的位置管理（类似路由区域）。
        cid	Cell ID（小区标识）	17628165	唯一标识一个基站小区（通常为 eNodeB ID + Cell ID 组合）。
     2. 频率与带宽
        字段	含义	示例值	说明
        earfcn	E-UTRA Absolute Radio Frequency Channel Number（频点号）	38950	唯一标识 LTE 频段（如 Band 40 对应 2300MHz）。
        band	LTE Band（频段编号）	40	中国常用 Band 1/3/5/8/34/38/39/40/41 等。
        dlbandwidth	Downlink Bandwidth（下行带宽）	5	单位：MHz（5 表示 5MHz）。
        ulbandwidth	Uplink Bandwidth（上行带宽）	5	单位：MHz（TDD 制式时与下行相同）。
        tdd	双工模式	1	1 表示 TDD（时分双工），0 表示 FDD（频分双工）。
    3. 信号质量指标
        字段	含义	示例值	说明
        rsrp	Reference Signal Received Power（参考信号接收功率）	-86	单位 dBm，值越大越好（-85 优于 -100）。
        rsrq	Reference Signal Received Quality（参考信号接收质量）	-9	单位 dB，值越大越好（-5 优于 -15）。
        rssi	Received Signal Strength Indicator（接收信号强度）	-57	单位 dBm，包含干扰和噪声（通常比 RSRP 高）。
        snr	Signal-to-Noise Ratio（信噪比）	33	单位 dB，值越大信号越纯净（>20 为优）。
        pci	Physical Cell ID（物理小区标识）	214	用于区分相邻小区（范围 0~503）。
    4. 一些官网API定位，比如https://iot.openluat.com/lbs/bs
        在基站（蜂窝网络）定位中，通常需要以下 4 个关键参数 来唯一标识一个基站小区：
        MCC（国家代码）、MNC（运营商代码）、LAC/TAC（位置区/跟踪区代码）、CI/ECI（小区标识）。
        定位所需参数	对应 cellinfo 中的字段	示例值	说明
        MCC	mcc	460	中国代码（460=中国，其他如 310=美国）。
        MNC	mnc	0	运营商代码（中国移动=00/02，联通=01，电信=03）。
        LAC/TAC	tac	4277	LTE 中称为 TAC（Tracking Area Code），2G/3G 中称为 LAC。
        CI/ECI	cid	17628165	LTE 中称为 ECI（E-UTRAN Cell ID），2G/3G 中称为 CI（Cell ID）。
    ]]
    local cellinfo = mobile.getCellInfo()
    -- 按信号强度rsrq排序
    table.sort(cellinfo, function(a, b) return a.rsrq > b.rsrq end)
    myGNSS.res.cellinfo = {}
    -- 取前5个
    for i = 1, math.min(#cellinfo, 5) do
        table.insert(myGNSS.res.cellinfo, cellinfo[i])
    end
end)

local function do_agps()
    -- 首先, 发起位置查询
    local lat, lng
    if mobile then
        log.info("in AGPS 开始基站扫描" )
        mobile.reqCellInfo(15) --进行基站扫描
        log.info("in AGPS 等待CELL_INFO_UPDATE状态" )
        sys.waitUntil("CELL_INFO_UPDATE", 6000) --等到扫描成功，超时时间15S
        log.info("in AGPS 等待IP_READY状态" )
        sys.waitUntil("IP_READY", 15000)
        log.info("in AGPS 用基站信息定位，免费版本" )
        local lbsLoc2 = require("lbsLoc2")
        lat, lng, t = lbsLoc2.request(5000)--仅需要基站定位给出的经纬度
        -- local lat, lng, t = lbsLoc2.request(5000, "bs.openluat.com")
        log.info("in AGPS lbsLoc2 lat=", lat, "lng=",lng,"t=",json.encode(t or {}) )
        if lat and lng then
            lat = tonumber(lat)
            lng = tonumber(lng)
            myGNSS.res.agps_lat=lat
            myGNSS.res.agps_lng=lng
            myGNSS.res.agps_ts=os.time()
            log.info("second lbsLoc2 lat=", lat, "lng=",lng)
            -- 转换单位
            local lat_dd,lat_mm = math.modf(lat)
            local lng_dd,lng_mm = math.modf(lng)
            lat = lat_dd * 100 + lat_mm * 60
            lng = lng_dd * 100 + lng_mm * 60
            log.info("in AGPS，处理后的经纬度： lat=", lat, "lng=",lng)
        end
    elseif wlan then
        -- wlan.scan()
        -- sys.waitUntil("WLAN_SCAN_DONE", 5000)
    end
    if not lat then
        -- 获取最后的本地位置
        local locStr = io.readFile("/hxxtloc")
        if locStr then
            local jdata = json.decode(locStr)
            if jdata and jdata.lat then
                lat = jdata.lat
                lng = jdata.lng
            end
        end
    end
    -- 然后, 判断星历时间和下载星历
    local now = os.time()
    local agps_time = tonumber(io.readFile("/hxxt_tm") or "0") or 0
    log.info("myGNSS", "星历更新时间", agps_time, "当前时间", now, "星历时间差", now - agps_time)
    if now - agps_time > 3600 then
        local url = myGNSS.opts.url
        if not myGNSS.opts.url then
            if myGNSS.opts.sys and 2 == myGNSS.opts.sys then
                -- 单北斗
                url = "http://download.openluat.com/9501-xingli/HXXT_BDS_AGNSS_DATA.dat"
                log.info("url=",url)
            else
                url = "http://download.openluat.com/9501-xingli/HXXT_GPS_BDS_AGNSS_DATA.dat"
                log.info("url=",url)
            end
        end
        local code = http.request("GET", url, nil, nil, {dst="/hxxt.dat"}).wait()
        if code and code == 200 then
            log.info("myGNSS", "下载星历成功", url)
            io.writeFile("/hxxt_tm", tostring(now))
        else
            log.info("myGNSS", "下载星历失败", code)
        end
    else
        log.info("myGNSS", "星历不需要更新", now - agps_time)
    end

    local gps_uart_id = myGNSS.opts.uart_id or 2

    -- 写入星历
    local agps_data = io.readFile("/hxxt.dat")
    if agps_data and #agps_data > 1024 then
        log.info("myGNSS", "写入星历数据", "长度", #agps_data)
        for offset=1,#agps_data,512 do
            --log.info("gnss", "AGNSS", "write >>>", #agps_data:sub(offset, offset + 511))
            uart.write(gps_uart_id, agps_data:sub(offset, offset + 511))
            -- 写入辅助数据后，发送热启动命令
            uart.write(gps_uart_id, "$CFGRST,0,1*1D\r\n") -- 热启动
            sys.wait(100) -- 等100ms反而更成功
        end
        -- uart.write(gps_uart_id, agps_data)
    else
        log.info("myGNSS", "没有星历数据")
        return
    end

    -- 写入参考位置
    -- "lat":23.4068813,"min":27,"valid":true,"day":27,"lng":113.2317505
    if not lat or not lng then
        -- lat, lng = 23.4068813, 113.2317505
        log.info("myGNSS", "没有GPS坐标", lat, lng)
        return -- TODO 暂时不写入参考位置
    end
    if socket.sntp then
        socket.sntp()
        sys.waitUntil("NTP_UPDATE", 1000)
    end
    local date = os.date("!*t")
    if date.year > 2023 then
        local str = string.format("$AIDTIME,%d,%d,%d,%d,%d,%d,000", date["year"], date["month"], date["day"],
            date["hour"], date["min"], date["sec"])
        log.info("myGNSS", "参考时间", str)
        uart.write(gps_uart_id, str .. "\r\n")
        sys.wait(20)
    end

    local str = string.format("$AIDPOS,%.7f,%s,%.7f,%s,1.0\r\n",
    lat > 0 and lat or (0 - lat), lat > 0 and 'N' or 'S',
    lng > 0 and lng or (0 - lng), lng > 0 and 'E' or 'W')
    log.info("myGNSS", "写入AGPS参考位置", str)
    uart.write(gps_uart_id, str)

    -- 结束
    myGNSS.agps_tm = now
end

function myGNSS.agps(force)
    -- 如果不是强制写入AGPS信息, 而且是已经定位成功的状态,那就没必要了
    if not force and libgnss.isFix() then return end
    -- 先判断一下时间
    local now = os.time()
    if force or not myGNSS.agps_tm or now - myGNSS.agps_tm > 3600 then
        -- 执行AGPS
        log.info("myGNSS", "开始执行AGPS")
        do_agps()
    else
        log.info("myGNSS", "暂不需要写入AGPS")
    end
    return myGNSS.lat, myGNSS.lng
end

function myGNSS.saveloc(lat, lng)
    if not lat or not lng then
        if libgnss.isFix() then
            local rmc = libgnss.getRmc(3)
            if rmc then
                lat, lng = rmc.lat, rmc.lng
                myGNSS.res.lat=lat
                myGNSS.res.lng=lng
                myGNSS.res.gps_ts=os.time()
            end
        end
    end
    if lat and lng then
        log.info("待保存的GPS位置", lat, lng)
        local locStr = string.format('{"lat":%7f,"lng":%7f}', lat, lng)
        log.info("myGNSS", "保存GPS位置", locStr)
        io.writeFile("/hxxtloc", locStr)
    end
end

sys.subscribe("GNSS_STATE", function(event, ticks)
    -- event取值有
    -- FIXED 定位成功
    -- LOSE  定位丢失
    -- ticks是事件发生的时间,一般可以忽略
    log.info("收到GNSS_STATE通知，event=",event,"ticks=",ticks)
    log.info("nmea", "gsv", json.encode(libgnss.getGsv())) --total_sats是总可见的卫星数
    log.info("nmea", "gsa", json.encode(libgnss.getGsa(), "11g")) -- "sats":[9,6,16] 显示当前使用的卫星编号，fix_type // 定位模式, 1-未定位, 2-2D定位, 3-3D定位
    log.info("GGA", json.encode(libgnss.getGga(2), "11g")) --fix_quality：定位状态标识 0 - 无效,1 - 单点定位,2 - 差分定位；"satellites_tracked":14,  // 参与定位的卫星数量；"hdop":0.0335,            // 水平精度因子，0.00 - 99.99，不定位时值为 99.99
    log.info("GLL", json.encode(libgnss.getGll(2), "11g")) --"status":"A",        // 定位状态, A有效, B无效；"mode":"A",          // 定位模式, V无效, A单点解, D差分解
    local onoff = libgnss.isFix() and 1 or 0
    gpio.setup(cfg.gnss.led_pin, onoff)
    local rmc = libgnss.getRmc(2)
    myGNSS.res.gps_ts=os.time()
    if rmc then
        myGNSS.res.lat=rmc.lat
        myGNSS.res.lng=rmc.lng
    else
        myGNSS.res.lat=0
        myGNSS.res.lng=0
    end
    if event == "FIXED" then
        local locStr = libgnss.locStr()
        log.info("GPS定位成功, locStr=", locStr)
        local rmc = libgnss.getRmc(2)
        if rmc then
            myGNSS.saveloc(rmc.lat,rmc.lng)
        else
            myGNSS.saveloc()
        end
    end
    -- 新增信号质量监测
    local gsv = libgnss.getGsv()
    if gsv then
        log.info("GNSS", "可见卫星数:", gsv.total_sats)
        local strong_sats = 0
        for _, sat in ipairs(gsv.sats or {}) do
            if sat.snr and tonumber(sat.snr) > 30 then -- 信噪比大于30认为是强信号
                strong_sats = strong_sats + 1
            end
        end
        log.info("GNSS", "强信号卫星数:", strong_sats)

        -- 如果信号弱，考虑主动刷新AGPS
        if event == "LOSE" or strong_sats < 3 then
            sys.timerStart(myGNSS.agps, 5000, 1) -- 5秒后尝试AGPS更新
        end
    end
end)

sys.taskInit(function()
    log.info("GPS", "start")
    pm.power(pm.GPS, true)
    myGNSS.setup(cfg.gnss)
    myGNSS.start()
    -- 调试日志,可选
    sys.wait(200) -- GPNSS芯片启动需要时间,大概150ms
    -- 绑定uart,底层自动处理GNSS数据
    log.debug("提醒", "室内无GNSS信号,定位不会成功, 要到空旷的室外,起码要看得到天空")
    myGNSS.agps(1) --强制更新agps信息
end)

-- 下面演示的是初始化gnss后的定时扫描
sys.taskInit(function()
    sys.wait(1000)
    while 1 do
        if myGNSS.res.lat==0 then --如果定位失败，则更新一次agps信息
            myGNSS.agps(1)
        end
        sys.wait(3600000) --默认一小时至少强制更新一回，避免争用天线（wifi和4G是一个天线）
    end
end)


sys.timerLoopStart(function()
    local gsv = libgnss.getGsv()
    local rmc = libgnss.getRmc(2)
    if gsv then
        log.info("gsv信息:", json.encode(gsv))
        log.info("可见卫星数:", gsv.total_sats, "强信号卫星:", #gsv.sats)
        log.info("lat=", rmc.lat, "lng=", rmc.lng)
    end
end, 5000)

return myGNSS
