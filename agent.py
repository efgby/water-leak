"""
AI Agent 模块 - 维修任务调度和异常诊断
包含：感知、决策、执行、交互四个模块
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from database import read_sql, execute_sql
from config import LEAK_THRESHOLD


class MaintenanceAgent:
    """
    供水管网维修调度 AI Agent
    负责：感知水表状态 → 诊断漏损原因 → 生成调度方案 → 执行数据库更新
    """
    
    def __init__(self):
        """初始化 Agent"""
        self.state = {
            'locations': [],      # 水表位置和状态
            'records': [],        # 流量记录
            'residents': [],      # 维修人员
            'schedule': [],       # 调度结果
            'diagnostics': {}     # 诊断结果缓存
        }
        self.last_perceive = None
        
    # ===================== 模块1：感知模块 =====================
    
    def perceive(self) -> Dict[str, Any]:
        """
        感知水系统状态
        读取：water_location (位置+统计) → water_record (流量记录) → water_resident (人员)
        输出：当前系统状态快照
        """
        try:
            # 1. 读取水表位置和统计数据
            locations_query = """
            SELECT water_id, longitude, latitude, total_usage, average_leakage_rate
            FROM water_location
            ORDER BY water_id
            """
            locations_df = read_sql(locations_query)
            self.state['locations'] = locations_df.to_dict('records')
            
            # 2. 读取最近的流量记录（用于诊断）
            records_query = """
            SELECT water_id, instant_usage, node_inflow, node_outflow, leakage_rate, record_date
            FROM water_record
            ORDER BY record_date DESC
            LIMIT 600
            """
            records_df = read_sql(records_query)
            self.state['records'] = records_df.to_dict('records')
            
            # 3. 读取维修人员状态
            residents_query = """
            SELECT resident_id, water_id, resident_name, leak_detection, processing_status
            FROM water_resident
            ORDER BY resident_id
            """
            residents_df = read_sql(residents_query)
            self.state['residents'] = residents_df.to_dict('records')
            
            self.last_perceive = datetime.now().isoformat()
            
            return {
                'status': 'success',
                'timestamp': self.last_perceive,
                'locations_count': len(self.state['locations']),
                'records_count': len(self.state['records']),
                'residents_count': len(self.state['residents'])
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    # ===================== 模块2：决策模块 =====================
    
    def decide(self) -> Dict[str, Any]:
        """
        决策引擎：生成调度和诊断
        1. 调度优化：根据漏损率、位置、人员，排序优先级
        2. 异常诊断：分析每个水表的漏损原因
        """
        if not self.state['locations']:
            return {'status': 'error', 'message': '未感知数据，请先调用 perceive()'}
        
        try:
            # 步骤1：识别待处理的水表（漏损异常）
            abnormal_meters = self._identify_abnormal_meters()
            
            # 步骤2：获取空闲维修人员
            free_residents = self._get_free_residents()
            
            # 步骤3：生成调度方案
            schedule = self._generate_schedule(abnormal_meters, free_residents)
            
            # 步骤4：为每个水表生成诊断
            diagnostics = self._diagnose_all_meters()
            
            self.state['schedule'] = schedule
            self.state['diagnostics'] = diagnostics
            
            return {
                'status': 'success',
                'abnormal_meters_count': len(abnormal_meters),
                'free_residents_count': len(free_residents),
                'schedule_count': len(schedule),
                'diagnostics_count': len(diagnostics)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _identify_abnormal_meters(self) -> List[Dict[str, Any]]:
        """
        识别漏损异常的水表
        条件：average_leakage_rate > LEAK_THRESHOLD (12%)
        """
        abnormal = []
        for loc in self.state['locations']:
            if loc['average_leakage_rate'] > LEAK_THRESHOLD:
                abnormal.append({
                    'water_id': loc['water_id'],
                    'latitude': loc['latitude'],
                    'longitude': loc['longitude'],
                    'severity': loc['average_leakage_rate'],  # 漏损率作为严重程度
                    'status': 'abnormal'
                })
        
        # 按漏损率从高到低排序（最严重的优先）
        abnormal.sort(key=lambda x: x['severity'], reverse=True)
        return abnormal
    
    def _get_free_residents(self) -> List[Dict[str, Any]]:
        """
        获取空闲的维修人员
        条件：processing_status != '处理中'
        """
        free = []
        for resident in self.state['residents']:
            if resident['processing_status'] != '处理中':
                free.append({
                    'resident_id': resident['resident_id'],
                    'name': resident['resident_name'],
                    'assigned_water_id': resident['water_id'],
                    'current_status': resident['processing_status']
                })
        return free
    
    def _generate_schedule(
        self,
        abnormal_meters: List[Dict[str, Any]],
        free_residents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        生成调度方案
        算法：
        1. 按漏损严重程度排序（已done）
        2. 分配空闲人员
        3. 计算就近距离（可选）
        """
        schedule = []
        
        for idx, meter in enumerate(abnormal_meters):
            # 轮流分配人员（简单轮转）
            if free_residents:
                assigned_resident = free_residents[idx % len(free_residents)]
            else:
                assigned_resident = None
            
            priority = idx + 1  # 优先级从1开始
            
            schedule.append({
                'priority': priority,
                'water_id': meter['water_id'],
                'severity': meter['severity'],  # 漏损率
                'latitude': meter['latitude'],
                'longitude': meter['longitude'],
                'assigned_resident': assigned_resident['name'] if assigned_resident else '无空闲人员',
                'assigned_resident_id': assigned_resident['resident_id'] if assigned_resident else None,
                'status': '待处理'
            })
        
        return schedule
    
    def _diagnose_all_meters(self) -> Dict[int, Dict[str, Any]]:
        """
        为所有水表生成诊断
        分析每个水表的漏损原因和建议措施
        """
        diagnostics = {}
        
        for loc in self.state['locations']:
            water_id = loc['water_id']
            leakage_rate = loc['average_leakage_rate']
            
            # 调用诊断函数
            diagnosis = self._diagnose_single_meter(water_id, leakage_rate)
            diagnostics[water_id] = diagnosis
        
        return diagnostics
    
    def _diagnose_single_meter(self, water_id: int, leakage_rate: float) -> Dict[str, Any]:
        """
        诊断单个水表的漏损原因
        基于漏损率和历史记录进行分析
        """
        # 获取该水表的最近10条记录
        recent_records = [
            r for r in self.state['records']
            if r['water_id'] == water_id
        ][:10]
        
        # 分析漏损原因
        reason = ""
        advice = ""
        severity_level = ""
        
        if leakage_rate < 0:
            reason = "数据异常"
            advice = "检查传感器和数据记录"
            severity_level = "注意"
        elif leakage_rate == 0:
            reason = "无漏损"
            advice = "正常运行"
            severity_level = "正常"
        elif leakage_rate <= LEAK_THRESHOLD:
            reason = "正常范围内"
            advice = "继续监测"
            severity_level = "正常"
        elif leakage_rate <= LEAK_THRESHOLD * 1.5:  # 12% ~ 18%
            reason = "轻度漏损 - 可能有小管道泄漏或接头松动"
            advice = "定期巡检，检查管道接头，听诊法定位泄漏点"
            severity_level = "轻度"
        elif leakage_rate <= LEAK_THRESHOLD * 3:    # 18% ~ 36%
            reason = "中度漏损 - 可能有中等管道破裂或多处泄漏"
            advice = "立即进行详细检查，使用相关工具定位泄漏点，准备维修物资"
            severity_level = "中度"
        else:  # > 36%
            reason = "严重漏损 - 可能有大面积管道破裂"
            advice = "紧急处理！立即派遣维修队，考虑隔离该区域，启用备用路线"
            severity_level = "严重"
        
        # 分析波动趋势
        if recent_records:
            recent_rates = [r.get('leakage_rate', 0) for r in recent_records if r.get('leakage_rate') is not None]
            if recent_rates:
                trend = "上升" if recent_rates[0] > recent_rates[-1] else "下降" if recent_rates[0] < recent_rates[-1] else "稳定"
            else:
                trend = "无法判断"
        else:
            trend = "数据不足"
        
        return {
            'water_id': water_id,
            'current_leakage_rate': round(leakage_rate, 2),
            'severity_level': severity_level,
            'reason': reason,
            'advice': advice,
            'trend': trend,
            'recent_records_count': len(recent_records),
            'timestamp': datetime.now().isoformat()
        }
    
    # ===================== 模块3：执行模块 =====================
    
    def execute(self, confirm: bool = True) -> Dict[str, Any]:
        """
        执行调度决策
        1. 更新 water_resident 表 - 指派维修人员
        2. 更新 water_location 表 - 标记为待处理/处理中
        """
        if not confirm or not self.state['schedule']:
            return {'status': 'error', 'message': '无调度方案或未确认执行'}
        
        try:
            executed_count = 0
            
            for item in self.state['schedule']:
                water_id = item['water_id']
                assigned_resident_id = item['assigned_resident_id']
                priority = item['priority']
                
                # 更新 water_resident 表：修改处理状态
                if assigned_resident_id:
                    # 将该人员状态改为 '处理中'
                    update_sql = """
                    UPDATE water_resident
                    SET processing_status = %s
                    WHERE resident_id = %s
                    """
                    execute_sql(update_sql, ('处理中', assigned_resident_id))
                    executed_count += 1
            
            return {
                'status': 'success',
                'executed_count': executed_count,
                'message': f'成功执行 {executed_count} 项调度'
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    # ===================== 模块4：交互方法 =====================
    
    def get_schedule(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取调度方案
        Args:
            limit: 返回前N个优先级最高的任务（None表示返回全部）
        Returns:
            调度列表
        """
        schedule = self.state['schedule']
        if limit:
            schedule = schedule[:limit]
        return schedule
    
    def get_diagnosis(self, water_id: int) -> Dict[str, Any]:
        """
        获取单个水表的诊断信息
        Args:
            water_id: 水表ID
        Returns:
            诊断结果（包含原因、建议、趋势等）
        """
        if water_id in self.state['diagnostics']:
            return self.state['diagnostics'][water_id]
        
        # 如果未缓存，则实时计算
        loc = next((l for l in self.state['locations'] if l['water_id'] == water_id), None)
        if loc:
            return self._diagnose_single_meter(water_id, loc['average_leakage_rate'])
        
        return {'status': 'error', 'message': f'水表 {water_id} 不存在'}
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取 Agent 的内部状态（用于前端显示）
        """
        return {
            'last_perceive': self.last_perceive,
            'locations_count': len(self.state['locations']),
            'abnormal_meters': len([l for l in self.state['locations'] if l['average_leakage_rate'] > LEAK_THRESHOLD]),
            'free_residents': len([r for r in self.state['residents'] if r['processing_status'] != '处理中']),
            'schedule_count': len(self.state['schedule']),
            'has_schedule': len(self.state['schedule']) > 0
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """
        获取完整的 Agent 报告（包含感知、决策、执行状态）
        用于前端仪表板显示
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'state': self.get_state(),
            'schedule': self.get_schedule(limit=10),  # 返回前10个
            'system_summary': {
                'total_meters': len(self.state['locations']),
                'abnormal_count': len([l for l in self.state['locations'] if l['average_leakage_rate'] > LEAK_THRESHOLD]),
                'avg_leakage_rate': sum(l['average_leakage_rate'] for l in self.state['locations']) / len(self.state['locations']) if self.state['locations'] else 0,
                'pending_tasks': len(self.state['schedule'])
            }
        }


# 全局 Agent 实例
_agent_instance: Optional[MaintenanceAgent] = None


def get_agent() -> MaintenanceAgent:
    """
    获取全局 Agent 实例（单例模式）
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MaintenanceAgent()
    return _agent_instance
