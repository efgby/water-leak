# app.py
"""
Streamlit 前端界面 - 智慧供水管网监控系统
"""
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from config import LEAK_THRESHOLD

API_BASE_URL = "http://127.0.0.1:8000"

# 页面配置
st.set_page_config(page_title="智慧供水管网监控系统", layout="wide", initial_sidebar_state="expanded")

# 初始化session_state（用于跟踪选中的水表行）
if 'selected_row' not in st.session_state:
    st.session_state.selected_row = None

# 样式美化
st.markdown("""
<style>
    .metric {
        text-align: center;
        padding: 20px;
    }
</style>
""", unsafe_allow_html=True)

# 页面标题和描述
st.title("💧 智慧供水管网漏损分析系统")
st.markdown("---")

# ===================== 首页KPI指标区域 =====================

try:
    dashboard = requests.get(f"{API_BASE_URL}/dashboard").json()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📍 水表总数", dashboard['total_locations'])
    col2.metric("📊 流量记录数", dashboard['total_records'])
    col3.metric("👷 维修人员数", dashboard['total_workers'])
    col4.metric("⚠️ 漏损异常数", dashboard['abnormal_leakage_count'])
except Exception as e:
    st.error(f"❌ 无法获取仪表板数据: {str(e)}")

st.markdown("---")

# ===================== 标签页导航 =====================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📍 水表管理", "📈 流量分析", "👷 人员管理", "🚨 漏损分析", "⚙️ 数据操作", "🤖 AI 调度"])

# ===================== TAB1: 水表管理 =====================

with tab1:
    st.subheader("水表位置管理")
    
    # 获取所有水表和维修人员信息
    try:
        locations_response = requests.get(f"{API_BASE_URL}/locations?limit=100")
        locations_data = locations_response.json()
        
        residents_response = requests.get(f"{API_BASE_URL}/residents?limit=100")
        residents_data = residents_response.json()
        
        if locations_data:
            locations_df = pd.DataFrame(locations_data)
            
            # 合并维修人员信息（解决问题2）
            if residents_data:
                residents_df = pd.DataFrame(residents_data)
                locations_df = locations_df.merge(
                    residents_df[['water_id', 'resident_name', 'processing_status']], 
                    on='water_id', 
                    how='left'
                )
            
            # 创建颜色映射函数
            def get_status_color(status):
                """按维修状态返回Plotly颜色"""
                status_map = {
                    '待处理': '#FF0000',    # 红色
                    '处理中': '#FFA500',    # 橙色
                    '已完成': '#00AA00',    # 绿色
                }
                return status_map.get(status, '#0000FF')  # 蓝色（未关联）
            
            # 为每条数据添加颜色列
            locations_df['color'] = locations_df['processing_status'].apply(get_status_color)
            
            # 创建悬停文本
            locations_df['hover_text'] = locations_df.apply(
                lambda row: f"<b>水表ID: {row['water_id']}</b><br>" +
                           f"位置: ({row['latitude']:.4f}, {row['longitude']:.4f})<br>" +
                           f"总使用量: {row['total_usage']:.2f} m³<br>" +
                           f"平均漏损率: {row['average_leakage_rate']:.2f}%<br>" +
                           f"维修人员: {row.get('resident_name', '未分配')}<br>" +
                           f"状态: {row.get('processing_status', '无')}",
                axis=1
            )
            
            # 显示地图和统计
            col_map, col_stats = st.columns([3, 1])
            
            with col_map:
                st.markdown("##### 📍 地理位置分布（按维修状态着色）")
                st.markdown("""
                **地图标记说明：**  
                - 🔴 **红色** - 待处理 | 🟠 **橙色** - 处理中 | 🟢 **绿色** - 已完成 | 🔵 **蓝色** - 未关联
                """)
                
                # 确定聚焦位置：如果选中某行，则聚焦到该点；否则显示所有点的中心
                if st.session_state.selected_row is not None and st.session_state.selected_row < len(locations_df):
                    selected_data = locations_df.iloc[st.session_state.selected_row]
                    center_lat = selected_data['latitude']
                    center_lon = selected_data['longitude']
                    zoom = 15  # 聚焦时放大
                else:
                    center_lat = locations_df['latitude'].mean()
                    center_lon = locations_df['longitude'].mean()
                    zoom = 12  # 默认视图
                
                # 创建Plotly scatter_mapbox
                fig = go.Figure()
                
                # 按状态分组添加点，使用不同的trace以便在图例中显示
                for status in ['待处理', '处理中', '已完成', None]:
                    if status is None:
                        mask = locations_df['processing_status'].isna()
                        status_label = '未关联'
                        color = '#0000FF'
                    else:
                        mask = locations_df['processing_status'] == status
                        status_label = status
                        color = get_status_color(status)
                    
                    if mask.sum() > 0:
                        subset = locations_df[mask]
                        fig.add_trace(go.Scattermapbox(
                            lon=subset['longitude'],
                            lat=subset['latitude'],
                            mode='markers',
                            marker=dict(
                                size=12,
                                color=color,
                                opacity=0.8
                            ),
                            text=subset['hover_text'],
                            hovertemplate='%{text}<extra></extra>',
                            name=status_label,
                            customdata=subset.index  # 用于识别选中的行
                        ))
                
                # 更新地图布局
                fig.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lat=center_lat, lon=center_lon),
                        zoom=zoom
                    ),
                    height=450,
                    margin=dict(r=0, t=0, l=0, b=0),
                    hovermode='closest',
                    legend=dict(
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01,
                        bgcolor="rgba(255, 255, 255, 0.8)"
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with col_stats:
                st.markdown("##### 📊 统计")
                st.metric("总水表数", len(locations_df))
                st.metric("平均使用量", f"{locations_df['total_usage'].mean():.2f} m³")
                st.metric("平均漏损率", f"{locations_df['average_leakage_rate'].mean():.2f}%")
                
                if residents_data:
                    st.divider()
                    待处理数 = len(locations_df[locations_df['processing_status'] == '待处理'])
                    处理中数 = len(locations_df[locations_df['processing_status'] == '处理中'])
                    已完成数 = len(locations_df[locations_df['processing_status'] == '已完成'])
                    
                    st.markdown("**按状态统计:**")
                    st.info(f"🔴 待处理\n{待处理数} 块")
                    st.warning(f"🟠 处理中\n{处理中数} 块")
                    st.success(f"🟢 已完成\n{已完成数} 块")
            
            # 显示详细表格（点击行时触发聚焦）
            st.markdown("##### 📋 水表详细列表")
            display_cols = ['water_id', 'longitude', 'latitude', 'total_usage', 'average_leakage_rate']
            
            # 添加人员列（如果存在）
            if 'resident_name' in locations_df.columns:
                display_cols.extend(['resident_name', 'processing_status'])
            
            display_df = locations_df[display_cols].copy()
            
            # 使用数据编辑器实现可交互的表格            
            # 创建可交互表格
            column_config = {
                'water_id': st.column_config.NumberColumn('水表ID', width='small'),
                'longitude': st.column_config.NumberColumn('经度', format='%.4f', width='small'),
                'latitude': st.column_config.NumberColumn('纬度', format='%.4f', width='small'),
                'total_usage': st.column_config.NumberColumn('总使用量(m³)', format='%.2f', width='medium'),
                'average_leakage_rate': st.column_config.NumberColumn('平均漏损率(%)', format='%.2f', width='medium'),
            }
            
            if 'resident_name' in display_df.columns:
                column_config['resident_name'] = st.column_config.TextColumn('维修人员', width='small')
                column_config['processing_status'] = st.column_config.TextColumn('处理状态', width='small')
            
            # 添加索引列用于行选择
            display_df_with_index = display_df.reset_index(drop=True)
            
            # 显示表格，保存选中行信息
            selected_rows = st.dataframe(
                display_df_with_index,
                column_config=column_config,
                use_container_width=True,
                hide_index=False,
                on_select="rerun"
            )
            
            # 检查是否有选中的行
            if selected_rows.selection.rows:
                st.session_state.selected_row = selected_rows.selection.rows[0]
                # 重新运行以更新地图聚焦
                st.rerun()
            
        else:
            st.info("📭 暂无水表数据")
    except Exception as e:
        st.error(f"❌ 获取水表数据失败: {str(e)}")


# ===================== TAB2: 流量分析 =====================

with tab2:
    st.subheader("流量记录分析")
    
    # 筛选条件
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_water_id = st.number_input("选择水表ID", min_value=1, value=1)
    with col2:
        limit = st.slider("显示记录数", min_value=10, max_value=100, value=50)
    with col3:
        st.empty()
    
    try:
        # 获取选定水表的流量记录
        records_response = requests.get(
            f"{API_BASE_URL}/records?water_id={selected_water_id}&limit={limit}"
        )
        records_data = records_response.json()
        
        if records_data:
            records_df = pd.DataFrame(records_data)
            
            # 数据转换（Unix时间戳转换为日期）
            records_df['record_date'] = pd.to_datetime(records_df['record_date'], unit='s')
            records_df = records_df.sort_values('record_date')
            
            # 绘制流量趋势图
            st.markdown("##### 瞬时用量趋势")
            fig_usage = px.line(records_df, x='record_date', y='instant_usage',
                               title='瞬时用量变化', labels={'instant_usage': '用量(m³)', 'record_date': '时间'})
            st.plotly_chart(fig_usage, use_container_width=True)
            
            # 绘制漏损率趋势图
            st.markdown("##### 漏损率趋势")
            fig_leakage = px.line(records_df, x='record_date', y='leakage_rate',
                                 title='漏损率变化', labels={'leakage_rate': '漏损率(%)', 'record_date': '时间'})
            fig_leakage.add_hline(y=12, line_dash="dash", line_color="red", annotation_text="警告值(12%)")
            st.plotly_chart(fig_leakage, use_container_width=True)
            
            # 显示流量数据表格
            st.markdown("##### 详细流量记录")
            display_records = records_df[['record_id', 'water_id', 'record_date', 'instant_usage', 
                                         'node_inflow', 'node_outflow', 'leakage_rate']]
            st.dataframe(display_records, use_container_width=True)
            
            # 统计信息
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("平均用量", f"{records_df['instant_usage'].mean():.2f} m³")
            col2.metric("平均进水", f"{records_df['node_inflow'].mean():.2f} m³")
            col3.metric("平均出水", f"{records_df['node_outflow'].mean():.2f} m³")
            col4.metric("平均漏损率", f"{records_df['leakage_rate'].mean():.2f}%")
        else:
            st.info(f"📭 水表 {selected_water_id} 暂无流量记录")
    except Exception as e:
        st.error(f"❌ 获取流量数据失败: {str(e)}")


# ===================== TAB3: 人员管理 =====================

with tab3:
    st.subheader("维修人员管理")
    
    try:
        residents_response = requests.get(f"{API_BASE_URL}/residents?limit=100")
        residents_data = residents_response.json()
        
        if residents_data:
            residents_df = pd.DataFrame(residents_data)
            
            # 人员统计（解决问题2 - 按状态统计）
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总人员数", len(residents_df))
            
            待处理数 = len(residents_df[residents_df['processing_status'] == '待处理'])
            col2.metric("🔴 待处理",待处理数)
            
            处理中数 = len(residents_df[residents_df['processing_status'] == '处理中'])
            col3.metric("🟠 处理中", 处理中数)
            
            已完成数 = len(residents_df[residents_df['processing_status'] == '已完成'])
            col4.metric("🟢 已完成", 已完成数)
            
            # 按处理状态分组展示
            st.markdown("##### 维修人员列表（按处理状态）")
            
            # 创建选项卡按状态显示
            status_tabs = st.tabs(["📋 全部人员", "🔴 待处理", "🟠 处理中", "🟢 已完成"])
            
            with status_tabs[0]:
                st.markdown("**所有维修人员**")
                display_df = residents_df[['resident_id', 'water_id', 'resident_name', 'leak_detection', 'processing_status']]
                st.dataframe(display_df, use_container_width=True)
            
            with status_tabs[1]:
                待处理_df = residents_df[residents_df['processing_status'] == '待处理']
                if not 待处理_df.empty:
                    display_df = 待处理_df[['resident_id', 'water_id', 'resident_name', 'leak_detection', 'processing_status']]
                    st.dataframe(display_df, use_container_width=True)
                    st.warning(f"有 {len(待处理_df)} 项任务待处理")
                else:
                    st.success("✅ 暂无待处理任务")
            
            with status_tabs[2]:
                处理中_df = residents_df[residents_df['processing_status'] == '处理中']
                if not 处理中_df.empty:
                    display_df = 处理中_df[['resident_id', 'water_id', 'resident_name', 'leak_detection', 'processing_status']]
                    st.dataframe(display_df, use_container_width=True)
                    st.info(f"正在处理 {len(处理中_df)} 项任务")
                else:
                    st.info("暂无处理中的任务")
            
            with status_tabs[3]:
                已完成_df = residents_df[residents_df['processing_status'] == '已完成']
                if not 已完成_df.empty:
                    display_df = 已完成_df[['resident_id', 'water_id', 'resident_name', 'leak_detection', 'processing_status']]
                    st.dataframe(display_df, use_container_width=True)
                    st.success(f"已完成 {len(已完成_df)} 项任务")
                else:
                    st.info("暂无已完成的任务")
        else:
            st.info("📭 暂无维修人员数据")
    except Exception as e:
        st.error(f"❌ 获取人员数据失败: {str(e)}")


# ===================== TAB4: 漏损分析 =====================

with tab4:
    st.subheader("漏损监测和分析")
    
    try:
        # 获取漏损总结
        summary_response = requests.get(f"{API_BASE_URL}/analysis/leakage-summary")
        summary_data = summary_response.json()
        
        # 显示漏损概览指标
        col1, col2, col3 = st.columns(3)
        col1.metric("总记录数", summary_data['total_records'])
        col2.metric("异常数量", summary_data['abnormal_count'])
        col3.metric("异常占比", f"{summary_data['abnormal_rate']:.2f}%")
        
        st.info(f"⚠️ 系统漏损率警告阈值: **{summary_data['threshold']}%**（按GB 17446-2012标准）")
        
        # 获取漏损严重的水表
        st.markdown("##### 漏损严重的水表（Top 10）")
        
        try:
            records_all = pd.DataFrame(requests.get(f"{API_BASE_URL}/records?limit=1000").json())
            if not records_all.empty:
                # 计算每个水表的平均漏损率
                leakage_by_meter = records_all.groupby('water_id')['leakage_rate'].agg(['mean', 'max', 'count'])
                leakage_by_meter = leakage_by_meter.sort_values('mean', ascending=False).head(10)
                leakage_by_meter.columns = ['平均漏损率', '最大漏损率', '记录数']
                
                st.dataframe(leakage_by_meter, use_container_width=True)
                
                # 绘制漏损分布图表
                fig_dist = px.bar(leakage_by_meter.reset_index(), x='water_id', y='平均漏损率',
                                 title='水表漏损率分布（Top 10）',
                                 labels={'water_id': '水表ID', '平均漏损率': '漏损率(%)'})
                fig_dist.add_hline(y=12, line_dash="dash", line_color="red", annotation_text="警告值")
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                st.info("📭 暂无记录数据")
        except Exception as e:
            st.error(f"❌ 获取漏损分析数据失败: {str(e)}")
            
    except Exception as e:
        st.error(f"❌ 获取漏损概览失败: {str(e)}")


# ===================== TAB5: 数据操作 =====================

with tab5:
    st.subheader("数据管理工具")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 生成演示数据")
        st.warning("⚠️ 此操作将在数据库中插入50个水表、600条流量记录和5个人员信息")
        
        if st.button("🔄 生成演示数据", key="generate_data_btn"):
            with st.spinner("正在生成数据..."):
                try:
                    response = requests.post(f"{API_BASE_URL}/generate-demo-data")
                    result = response.json()
                    
                    st.success("✅ 演示数据生成成功！")
                    st.info(f"""
                    📊 生成统计：
                    - 水表位置: {result['locations_count']} 条
                    - 流量记录: {result['records_count']} 条
                    - 维修人员: {result['residents_count']} 条
                    """)
                except Exception as e:
                    st.error(f"❌ 数据生成失败: {str(e)}")
    
    with col2:
        st.markdown("##### 系统信息")
        st.info(f"""
        📱 API 服务地址: {API_BASE_URL}
        🕐 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        📌 系统名称: 供水管网漏损分析系统
        🔖 版本: 1.0.0
        """)


# ===================== TAB6: AI 调度决策 =====================

with tab6:
    st.subheader("🤖 AI 智能调度系统")
    st.markdown("*AI Agent 自动分析水表异常、生成维修调度和故障诊断*")
    
    # 初始化 session state
    if 'ai_report' not in st.session_state:
        st.session_state.ai_report = None
    if 'selected_diagnosis_id' not in st.session_state:
        st.session_state.selected_diagnosis_id = None
    
    # 控制按钮行
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🧠 感知 & 分析", key="perceive_btn"):
            with st.spinner("AI Agent 正在分析系统状态..."):
                try:
                    # 触发感知
                    requests.post(f"{API_BASE_URL}/agent/perceive")
                    # 触发决策
                    requests.post(f"{API_BASE_URL}/agent/decide")
                    # 获取报告
                    response = requests.get(f"{API_BASE_URL}/agent/report")
                    st.session_state.ai_report = response.json()
                    st.success("✅ 分析完成！")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 分析失败: {str(e)}")
    
    with col2:
        if st.button("⚡ 执行调度", key="execute_btn"):
            if st.session_state.ai_report:
                with st.spinner("执行调度中..."):
                    try:
                        response = requests.post(f"{API_BASE_URL}/agent/execute?confirm=true")
                        result = response.json()
                        if result['status'] == 'success':
                            st.success(f"✅ 调度执行成功！\n{result['message']}")
                        else:
                            st.warning(f"⚠️ {result['message']}")
                    except Exception as e:
                        st.error(f"❌ 执行失败: {str(e)}")
            else:
                st.warning("请先点击「感知 & 分析」生成调度")
    
    with col3:
        if st.button("🔄 刷新报告", key="refresh_btn"):
            try:
                response = requests.get(f"{API_BASE_URL}/agent/report")
                st.session_state.ai_report = response.json()
                st.success("✅ 报告已刷新")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 刷新失败: {str(e)}")
    
    with col4:
        st.empty()  # 占位
    
    st.divider()
    
    # 显示系统概览
    if st.session_state.ai_report:
        report = st.session_state.ai_report
        
        # 摘要卡片
        st.markdown("##### 📊 系统摘要")
        col1, col2, col3, col4 = st.columns(4)
        
        summary = report.get('system_summary', {})
        col1.metric("总水表数", summary.get('total_meters', 0))
        col2.metric("异常水表", summary.get('abnormal_count', 0))
        col3.metric("平均漏损率", f"{summary.get('avg_leakage_rate', 0):.2f}%")
        col4.metric("待处理任务", summary.get('pending_tasks', 0))
        
        st.divider()
        
        # 显示调度表
        schedule = report.get('schedule', [])
        if schedule:
            st.markdown("##### 📋 优先维修顺序")
            
            # 创建调度表的数据
            schedule_display = []
            for item in schedule:
                schedule_display.append({
                    '优先级': item['priority'],
                    '水表ID': item['water_id'],
                    '漏损率%': f"{item['severity']:.2f}",
                    '严重程度': '🔴 严重' if item['severity'] > LEAK_THRESHOLD * 3 else (
                        '🟠 中度' if item['severity'] > LEAK_THRESHOLD * 1.5 else '🟡 轻度'
                    ),
                    '指派人员': item['assigned_resident'],
                    '状态': item['status']
                })
            
            schedule_df = pd.DataFrame(schedule_display)
            st.dataframe(schedule_df, use_container_width=True, hide_index=True)
            
            # 为每条调度项添加诊断弹窗
            st.markdown("##### 📌 故障诊断详情")
            
            # 创建两列用于显示诊断
            for idx, item in enumerate(schedule[:5]):  # 显示前5个的详细诊断
                water_id = item['water_id']
                
                with st.expander(f"💬 水表 {water_id} 的诊断信息", expanded=(idx == 0)):
                    try:
                        # 获取诊断信息
                        response = requests.get(f"{API_BASE_URL}/agent/diagnosis/{water_id}")
                        diagnosis = response.json()
                        
                        if 'reason' in diagnosis:
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                st.markdown("**诊断结果**")
                                severity = diagnosis.get('severity_level', '未知')
                                if severity == '严重':
                                    st.error(f"🔴 {severity}")
                                elif severity == '中度':
                                    st.warning(f"🟠 {severity}")
                                elif severity == '轻度':
                                    st.info(f"🟡 {severity}")
                                else:
                                    st.success(f"🟢 {severity}")
                                
                                st.markdown("**趋势**")
                                trend = diagnosis.get('trend', '无法判断')
                                if '上升' in trend:
                                    st.warning(f"📈 {trend}")
                                elif '下降' in trend:
                                    st.success(f"📉 {trend}")
                                else:
                                    st.info(f"〰️ {trend}")
                            
                            with col2:
                                st.markdown("**原因分析**")
                                st.write(diagnosis.get('reason', '暂无'))
                                st.markdown("**建议措施**")
                                st.write(diagnosis.get('advice', '暂无'))
                        else:
                            st.info("诊断数据加载中...")
                    except Exception as e:
                        st.error(f"获取诊断失败: {str(e)}")
        else:
            st.info("📭 暂无调度数据，请先点击「感知 & 分析」")
    else:
        st.info("👇 点击「感知 & 分析」按钮让 AI Agent 分析系统状态")


st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>© 2024 智慧供水管网监控系统 - 基于毛梦瑶硕士学位论文</div>", 
           unsafe_allow_html=True)