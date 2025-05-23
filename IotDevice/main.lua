-- LuaTools需要PROJECT和VERSION这两个信息
PROJECT = "FindDog"
VERSION = "0.9.5.20250512"

-- sys库是标配
_G.sys = require("sys")
require("sysplus")

log.info("main", PROJECT, VERSION)
-- 初始化存储
fskv.init()
fskv.set("version",VERSION) --记录版本号放在fskv中，通过它传递给config.lua，否则config.lua引用main.lua取值会造成循环引用

local cfg = require("config")
log.info("config", json.encode(cfg))

if wdt then
    --添加硬狗防止程序卡死，在支持的设备上启用这个功能
    wdt.init(cfg.wdt.init_wait*1000) --初始化watchdog设置
    sys.timerLoopStart(wdt.feed, cfg.wdt.feed_interval*1000) --多久喂一次狗
end

_G.gps_uart_id = cfg.gnss.uart_id

require "myMQTT"

-- 用户代码已结束---------------------------------------------
-- 结尾总是这一句
sys.run()
-- sys.run()之后后面不要加任何语句!!!!!