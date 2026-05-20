# api.py
"""
RESTful API 接口 - 根据毕业设计PDF实现
实现水表位置管理、流量记录管理、维修人员管理等功能
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from datetime import datetime
from database import init_db, read_sql, insert_dataframe, get_connection, execute_sql
from generate_data import generate_water_locations, generate_water_records, generate_water_residents, calculate_leakage_rate, update_water_location_stats
from agent import get_agent
from config import LEAK_THRESHOLD

app = FastAPI(
    title="供水管网漏损分析系统",
    description="基于Spring Boot和MySQL的供水管网漏损分析系统（Python版本演示）",
    version="1.0.0"
)

# 跨域支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时初始化数据库
@app.on_event("startup")
def startup():
    init_db()
    print("✓ 数据库初始化完成")


# ===================== 首页API =====================

@app.get("/dashboard")
def get_dashboard():
    """
    首页数据展示 - 返回KPI指标
    """
    try:
        total_locations = read_sql("SELECT COUNT(*) AS cnt FROM water_location")['cnt'].iloc[0]
        total_records = read_sql("SELECT COUNT(*) AS cnt FROM water_record")['cnt'].iloc[0]
        total_workers = read_sql("SELECT COUNT(*) AS cnt FROM water_resident")['cnt'].iloc[0]
        
        # 统计漏损异常（漏损率 > 12%）
        abnormal_count = read_sql(
            "SELECT COUNT(*) AS cnt FROM water_record WHERE leakage_rate > %s",
            (LEAK_THRESHOLD,)
        )['cnt'].iloc[0]
        
        return {
            "total_locations": int(total_locations),
            "total_records": int(total_records),
            "total_workers": int(total_workers),
            "abnormal_leakage_count": int(abnormal_count),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 水表位置信息API (water_location) =====================

@app.get("/locations")
def list_locations(skip: int = 0, limit: int = 100):
    """
    获取水表位置列表
    """
    try:
        df = read_sql(
            f"SELECT * FROM water_location LIMIT {limit} OFFSET {skip}"
        )
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/locations/{water_id}")
def get_location(water_id: int):
    """
    获取单个水表位置信息
    """
    try:
        df = read_sql(
            "SELECT * FROM water_location WHERE water_id = %s",
            (water_id,)
        )
        if df.empty:
            raise HTTPException(status_code=404, detail="水表不存在")
        return df.iloc[0].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/locations")
def create_location(data: dict):
    """
    创建新的水表位置信息
    """
    try:
        df = pd.DataFrame([{
            "longitude": data["longitude"],
            "latitude": data["latitude"],
            "total_usage": data.get("total_usage", 0.0),
            "average_leakage_rate": data.get("average_leakage_rate", 0.0)
        }])
        insert_dataframe("water_location", df)
        return {"message": "水表创建成功", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/locations/{water_id}")
def update_location(water_id: int, data: dict):
    """
    更新水表位置信息
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                update_fields = []
                update_values = []
                
                if "longitude" in data:
                    update_fields.append("longitude = %s")
                    update_values.append(data["longitude"])
                if "latitude" in data:
                    update_fields.append("latitude = %s")
                    update_values.append(data["latitude"])
                if "total_usage" in data:
                    update_fields.append("total_usage = %s")
                    update_values.append(data["total_usage"])
                if "average_leakage_rate" in data:
                    update_fields.append("average_leakage_rate = %s")
                    update_values.append(data["average_leakage_rate"])
                
                if not update_fields:
                    raise HTTPException(status_code=400, detail="没有要更新的字段")
                
                update_values.append(water_id)
                sql = f"UPDATE water_location SET {', '.join(update_fields)} WHERE water_id = %s"
                cursor.execute(sql, update_values)
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="水表不存在")
        
        return {"message": "水表更新成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/locations/{water_id}")
def delete_location(water_id: int):
    """
    删除水表位置信息
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM water_location WHERE water_id = %s", (water_id,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="水表不存在")
        
        return {"message": "水表删除成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 流量计记录API (water_record) =====================

@app.get("/records")
def list_records(water_id: int = None, skip: int = 0, limit: int = 100):
    """
    获取流量计记录列表
    """
    try:
        if water_id:
            df = read_sql(
                f"SELECT * FROM water_record WHERE water_id = %s ORDER BY record_date DESC LIMIT {limit} OFFSET {skip}",
                (water_id,)
            )
        else:
            df = read_sql(
                f"SELECT * FROM water_record ORDER BY record_date DESC LIMIT {limit} OFFSET {skip}"
            )
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/records/{record_id}")
def get_record(record_id: int):
    """
    获取单条流量计记录
    """
    try:
        df = read_sql(
            "SELECT * FROM water_record WHERE record_id = %s",
            (record_id,)
        )
        if df.empty:
            raise HTTPException(status_code=404, detail="记录不存在")
        return df.iloc[0].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/records")
def create_record(data: dict):
    """
    创建新的流量计记录
    """
    try:
        # 计算漏损率
        leakage_rate = calculate_leakage_rate(
            data["node_inflow"],
            data["node_outflow"],
            data["instant_usage"]
        )
        
        df = pd.DataFrame([{
            "water_id": data["water_id"],
            "record_date": data.get("record_date", int(datetime.now().timestamp())),
            "instant_usage": data["instant_usage"],
            "node_outflow": data["node_outflow"],
            "node_inflow": data["node_inflow"],
            "leakage_rate": leakage_rate
        }])
        insert_dataframe("water_record", df)
        return {"message": "记录创建成功", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/records/{record_id}")
def update_record(record_id: int, data: dict):
    """
    更新流量计记录
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                update_fields = []
                update_values = []
                
                if "instant_usage" in data:
                    update_fields.append("instant_usage = %s")
                    update_values.append(data["instant_usage"])
                if "node_outflow" in data:
                    update_fields.append("node_outflow = %s")
                    update_values.append(data["node_outflow"])
                if "node_inflow" in data:
                    update_fields.append("node_inflow = %s")
                    update_values.append(data["node_inflow"])
                if "leakage_rate" in data:
                    update_fields.append("leakage_rate = %s")
                    update_values.append(data["leakage_rate"])
                
                if not update_fields:
                    raise HTTPException(status_code=400, detail="没有要更新的字段")
                
                update_values.append(record_id)
                sql = f"UPDATE water_record SET {', '.join(update_fields)} WHERE record_id = %s"
                cursor.execute(sql, update_values)
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="记录不存在")
        
        return {"message": "记录更新成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/records/{record_id}")
def delete_record(record_id: int):
    """
    删除流量计记录
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM water_record WHERE record_id = %s", (record_id,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="记录不存在")
        
        return {"message": "记录删除成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 维修人员管理API (water_resident) =====================

@app.get("/residents")
def list_residents(skip: int = 0, limit: int = 100):
    """
    获取维修人员列表
    """
    try:
        df = read_sql(
            f"SELECT * FROM water_resident LIMIT {limit} OFFSET {skip}"
        )
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/residents/{resident_id}")
def get_resident(resident_id: int):
    """
    获取单个维修人员信息
    """
    try:
        df = read_sql(
            "SELECT * FROM water_resident WHERE resident_id = %s",
            (resident_id,)
        )
        if df.empty:
            raise HTTPException(status_code=404, detail="人员不存在")
        return df.iloc[0].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/residents")
def create_resident(data: dict):
    """
    创建新的维修人员信息
    """
    try:
        df = pd.DataFrame([{
            "water_id": data["water_id"],
            "resident_name": data["resident_name"],
            "leak_detection": data.get("leak_detection", "未检测"),
            "processing_status": data.get("processing_status", "待处理")
        }])
        insert_dataframe("water_resident", df)
        return {"message": "人员创建成功", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/residents/{resident_id}")
def update_resident(resident_id: int, data: dict):
    """
    更新维修人员信息
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                update_fields = []
                update_values = []
                
                if "resident_name" in data:
                    update_fields.append("resident_name = %s")
                    update_values.append(data["resident_name"])
                if "leak_detection" in data:
                    update_fields.append("leak_detection = %s")
                    update_values.append(data["leak_detection"])
                if "processing_status" in data:
                    update_fields.append("processing_status = %s")
                    update_values.append(data["processing_status"])
                
                if not update_fields:
                    raise HTTPException(status_code=400, detail="没有要更新的字段")
                
                update_values.append(resident_id)
                sql = f"UPDATE water_resident SET {', '.join(update_fields)} WHERE resident_id = %s"
                cursor.execute(sql, update_values)
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="人员不存在")
        
        return {"message": "人员更新成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/residents/{resident_id}")
def delete_resident(resident_id: int):
    """
    删除维修人员信息
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM water_resident WHERE resident_id = %s", (resident_id,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="人员不存在")
        
        return {"message": "人员删除成功", "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 漏损分析API =====================

@app.get("/analysis/leakage-summary")
def get_leakage_summary():
    """
    获取漏损分析总结
    """
    try:
        # 获取所有漏损数据
        all_records = read_sql("SELECT * FROM water_record")
        abnormal_records = read_sql(
            f"SELECT * FROM water_record WHERE leakage_rate > {LEAK_THRESHOLD}"
        )
        
        return {
            "total_records": len(all_records),
            "abnormal_count": len(abnormal_records),
            "abnormal_rate": round(len(abnormal_records) / len(all_records) * 100, 2) if len(all_records) > 0 else 0,
            "threshold": LEAK_THRESHOLD,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/leakage-by-meter")
def get_leakage_by_meter(water_id: int):
    """
    获取单个水表的漏损分析数据
    """
    try:
        records = read_sql(
            "SELECT * FROM water_record WHERE water_id = %s ORDER BY record_date DESC",
            (water_id,)
        )
        
        if records.empty:
            raise HTTPException(status_code=404, detail="该水表无记录")
        
        avg_leakage = records['leakage_rate'].mean()
        max_leakage = records['leakage_rate'].max()
        min_leakage = records['leakage_rate'].min()
        abnormal_count = len(records[records['leakage_rate'] > LEAK_THRESHOLD])
        
        return {
            "water_id": water_id,
            "average_leakage_rate": round(avg_leakage, 2),
            "max_leakage_rate": round(max_leakage, 2),
            "min_leakage_rate": round(min_leakage, 2),
            "abnormal_count": abnormal_count,
            "total_records": len(records),
            "threshold": LEAK_THRESHOLD,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== 数据生成API =====================

@app.post("/generate-demo-data")
def generate_demo_data():
    """
    生成演示数据
    """
    try:
        # 生成水表位置
        locations = generate_water_locations(50)
        insert_dataframe("water_location", locations)
        
        # 生成流量记录
        records = generate_water_records(50, records_per_meter=12)
        insert_dataframe("water_record", records)
        
        # 生成维修人员
        residents = generate_water_residents(5)
        insert_dataframe("water_resident", residents)
        
        # 更新water_location表的统计数据（问题1修复）
        update_water_location_stats()
        
        return {
            "message": "演示数据生成成功",
            "locations_count": len(locations),
            "records_count": len(records),
            "residents_count": len(residents),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===================== AI Agent API =====================

@app.post("/agent/perceive")
def agent_perceive():
    """
    触发 Agent 感知模块：读取当前系统状态
    """
    try:
        agent = get_agent()
        result = agent.perceive()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/decide")
def agent_decide():
    """
    触发 Agent 决策模块：生成调度方案和诊断
    需要先调用 perceive() 获取最新数据
    """
    try:
        agent = get_agent()
        
        # 确保有最新数据
        agent.perceive()
        
        # 执行决策
        result = agent.decide()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/execute")
def agent_execute(confirm: bool = True):
    """
    执行 Agent 的调度决策
    - 更新维修人员状态为 '处理中'
    - 可选：更新water_location表
    
    Args:
        confirm: 是否确认执行（默认True）
    """
    try:
        agent = get_agent()
        result = agent.execute(confirm=confirm)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/schedule")
def agent_get_schedule(limit: int = None):
    """
    获取调度方案
    
    Args:
        limit: 返回前N个优先级任务（可选）
    
    Returns:
        调度列表（按优先级排序）
    """
    try:
        agent = get_agent()
        schedule = agent.get_schedule(limit=limit)
        return {
            "schedule": schedule,
            "count": len(schedule),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/diagnosis/{water_id}")
def agent_get_diagnosis(water_id: int):
    """
    获取单个水表的诊断信息
    
    Args:
        water_id: 水表ID
    
    Returns:
        诊断结果（原因、建议、趋势、严重程度等）
    """
    try:
        agent = get_agent()
        diagnosis = agent.get_diagnosis(water_id)
        return diagnosis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/state")
def agent_get_state():
    """
    获取 Agent 内部状态
    用于前端仪表板快速查看系统状态
    """
    try:
        agent = get_agent()
        state = agent.get_state()
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/report")
def agent_get_full_report():
    """
    获取完整的 Agent 决策报告
    包含：感知状态、调度方案（前10个）、系统摘要
    用于前端完整展示
    """
    try:
        agent = get_agent()
        report = agent.get_full_report()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
