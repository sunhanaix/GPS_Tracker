local cfg = require("config")

local myWIFI = {}
myWIFI.res={} -- 扫描结果

-- 注意, wlan.scan()是异步API,启动扫描后会马上返回

-- wifi扫描成功后, 会有WLAN_SCAN_DONE消息, 读取即可
sys.subscribe("WLAN_SCAN_DONE", function ()
    local results = wlan.scanResult()
    log.info("扫描wifi，", "results", #results)

    -- 按rssi值降序排序
    table.sort(results, function(a, b) return a.rssi > b.rssi end)

    -- 只取前5个结果
    local top5Results = {}
    for i = 1, math.min(5, #results) do
        table.insert(top5Results, results[i])
    end

    -- 格式化bssid为十六进制
    for k, v in pairs(top5Results) do
        v["bssid"] = v["bssid"]:toHex()
        log.info("wifi扫描的结果：", v["ssid"], v["rssi"], v["bssid"])
    end

    myWIFI.res.wifi = top5Results
    myWIFI.res.wifi_ts = os.time()
end)

function myWIFI.scan()
    wlan.scan()
end

-- 下面演示的是初始化wifi后定时扫描,请按实际业务需求修改
sys.taskInit(function()
    sys.wait(1000)
    wlan.init()
    while 1 do
        wlan.scan()
        --错开些时间，避免争用天线（wifi和4G是一个天线）
        sys.wait(3600000) --默认一小时至少强制更新一回，避免争用天线（wifi和4G是一个天线）
    end
end)

return myWIFI