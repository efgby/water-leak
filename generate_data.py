# generate_data.py
"""
数据生成模块 - 根据毕业设计PDF第4.2节实现
漏损率计算公式: Ra = (Qa - Qae) / Q × 100
其中: Ra为漏损率(%), Qa为节点进水量, Qae为节点出水量, Q为实际流量
"""
import random
import time
from datetime import datetime
import numpy as np
import pandas as pd
from database import insert_dataframe, get_connection, execute_sql
from config import LEAK_THRESHOLD


def calculate_leakage_rate(node_inflow: float, node_outflow: float, instant_usage: float) -> float:
    """
    根据PDF第4.2节的公式计算漏损率
    Ra = (Qa - Qae) / Q × 100
    """
    if instant_usage <= 0:
        return 0.0
    leakage_rate = ((node_inflow - node_outflow) / instant_usage) * 100
    return max(0.0, min(100.0, leakage_rate))  # 确保在0-100之间


def generate_water_locations(num_meters: int = 50) -> pd.DataFrame:
    """
    生成水表位置信息
    """
    random.seed(42)
    np.random.seed(42)
    
    # 基础经纬度（北京地区）
    base_lng, base_lat = 116.397, 39.908
    
    rows = []
    for water_id in range(1, num_meters + 1):
        longitude = base_lng + np.random.normal(0, 0.035)
        latitude = base_lat + np.random.normal(0, 0.025)
        
        rows.append({
            "water_id": water_id,
            "longitude": round(float(longitude), 6),
            "latitude": round(float(latitude), 6),
            "total_usage": 0.0,
            "average_leakage_rate": 0.0
        })
    
    return pd.DataFrame(rows)


def generate_water_records(num_meters: int = 50, records_per_meter: int = 12) -> pd.DataFrame:
    """
    生成流量计记录
    每个水表生成多条记录，数据服从正态分布
    """
    rows = []
    current_timestamp = int(time.time())
    
    # 模拟一些有漏损问题的水表
    leak_prone_meters = set(np.random.choice(
        range(1, num_meters + 1), 
        size=max(5, num_meters // 5), 
        replace=False
    ))
    
    for water_id in range(1, num_meters + 1):
        for i in range(records_per_meter):
            # 基础流量（正态分布）
            base_inflow = np.random.normal(50, 10)
            base_inflow = max(1.0, base_inflow)
            
            # 是否存在漏损
            if water_id in leak_prone_meters and random.random() < 0.3:
                # 高漏损情况
                leakage_rate_val = np.random.uniform(LEAK_THRESHOLD + 1, 35)
                node_outflow = base_inflow * (1 - leakage_rate_val / 100)
            else:
                # 低漏损情况
                leakage_rate_val = np.random.uniform(2, 9)
                node_outflow = base_inflow * (1 - leakage_rate_val / 100)
            
            instant_usage = node_outflow + np.random.normal(2, 1)
            instant_usage = max(1.0, instant_usage)
            
            # 重新计算漏损率（使用公式）
            actual_leakage_rate = calculate_leakage_rate(
                base_inflow, node_outflow, instant_usage
            )
            
            record_timestamp = current_timestamp - (records_per_meter - i - 1) * 3600
            
            rows.append({
                "water_id": water_id,
                "record_date": record_timestamp,
                "instant_usage": round(float(instant_usage), 3),
                "node_outflow": round(float(node_outflow), 3),
                "node_inflow": round(float(base_inflow), 3),
                "leakage_rate": round(float(actual_leakage_rate), 3)
            })
    
    return pd.DataFrame(rows)


def generate_water_residents(num_workers: int = 5) -> pd.DataFrame:
    """
    生成维修人员信息
    """
    worker_names = ["张工", "李工", "王工", "赵工", "陈工"][:num_workers]
    leak_statuses = ["未检测", "已检测", "处理中", "已完成"]
    
    rows = []
    for i, worker_name in enumerate(worker_names, 1):
        rows.append({
            "resident_id": i,
            "water_id": i,
            "resident_name": worker_name,
            "leak_detection": random.choice(leak_statuses),
            "processing_status": random.choice(["待处理", "处理中", "已完成"])
        })
    
    return pd.DataFrame(rows)


def update_water_location_stats():
    """
    更新water_location表中的total_usage和average_leakage_rate
    这是解决问题1的关键：同步流量记录中的统计数据到位置表
    """
    sql = """
    UPDATE water_location wl
    JOIN (
        SELECT water_id, 
               SUM(instant_usage) AS total_usage,
               AVG(leakage_rate) AS average_leakage_rate
        FROM water_record
        GROUP BY water_id
    ) wr ON wl.water_id = wr.water_id
    SET wl.total_usage = wr.total_usage,
        wl.average_leakage_rate = wr.average_leakage_rate
    """
    execute_sql(sql)


def main():
    """
    生成所有初始数据
    """
    print("开始生成初始数据...")
    
    # 生成水表位置信息
    locations = generate_water_locations(50)
    insert_dataframe('water_location', locations)
    print(f"✓ 生成 {len(locations)} 条水表位置信息")
    
    # 生成流量计记录
    records = generate_water_records(50, records_per_meter=12)
    insert_dataframe('water_record', records)
    print(f"✓ 生成 {len(records)} 条流量计记录")
    
    # 生成维修人员
    residents = generate_water_residents(5)
    insert_dataframe('water_resident', residents)
    print(f"✓ 生成 {len(residents)} 条维修人员信息")
    
    # 更新water_location表的统计数据（解决问题1）
    print("\n📊 正在更新水表统计数据...")
    update_water_location_stats()
    print("✓ 水表统计数据已更新")
    
    print("\n✅ 数据生成完成！")


if __name__ == "__main__":
    main()
