import pandas as pd
from scipy.interpolate import interp1d
from datetime import datetime

# 读取并预处理数据
df = pd.read_csv('vbat_data.txt', sep='|', names=['time', 'vbat'], parse_dates=['time'])  # 添加names参数指定列名
end_time = df['time'].iloc[-1]  # 放电结束时间

# 计算剩余时间（分钟）
df['remaining'] = (end_time - df['time']).dt.total_seconds() / 60

# 数据预处理（按电压降序排列，去重保留最后出现的时间点）
df_sorted = df.sort_values('vbat', ascending=False).drop_duplicates('vbat', keep='last')

# 准备插值数据（需要转换为升序排列）
vbat = df_sorted['vbat'].values[::-1]  # 电压升序
remaining = df_sorted['remaining'].values[::-1]  # 剩余时间升序，原始数据按电压降序处理后反转成升序，因为interp1d要求x值单调递增

# 创建插值函数：基于已知的（电压，剩余时间）数据点构建分段线性函数
battery_model = interp1d(
    vbat,
    remaining,
    kind='linear', #采用线性插值法，在相邻数据点间用直线连接
    bounds_error=False, #当输入电压超出数据范围时不会报错
    fill_value=(0, remaining[-1])  # <2871返回0，>4118返回最大剩余时间
)


def estimate_remaining_time(voltage_mv):
    """估算电池剩余时间
    :param voltage_mv: 当前电压值（毫伏）
    :return: 剩余时间（分钟）
    """
    return float(battery_model(voltage_mv))


def estimate_battery_percentage(voltage_mv):
    """估算电池百分比
    :param voltage_mv: 当前电压值（毫伏）
    :return: 电池百分比（0到100之间的浮点数）
    """
    remaining_time = estimate_remaining_time(voltage_mv)
    total_time = remaining[-1]  # 总的可用时间
    if total_time == 0:
        return 0.0
    return (remaining_time / total_time) * 100


# 示例使用
if __name__ == '__main__':
    test_voltages = [4118, 3700, 3000, 2871,3467,3711]

    for v in test_voltages:
        print(f"电压 {v}mV -> 剩余时间: {estimate_remaining_time(v):.1f} 分钟")
        print(f"电压 {v}mV -> 电池百分比: {estimate_battery_percentage(v):.1f}%")

# 输出示例：
# 电压 4118mV -> 剩余时间: 1376.9 分钟
# 电压 4118mV -> 电池百分比: 100.0%
# 电压 3700mV -> 剩余时间: 863.2 分钟
# 电压 3700mV -> 电池百分比: 62.7%
# 电压 3000mV -> 剩余时间: 102.5 分钟
# 电压 3000mV -> 电池百分比: 7.4%
# 电压 2871mV -> 剩余时间: 0.0 分钟
# 电压 2871mV -> 电池百分比: 0.0%