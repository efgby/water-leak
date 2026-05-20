# 智慧供水管网漏损监测系统 MySQL 版

这是第一版工程项目的 MySQL 版本，使用：

- FastAPI：后端接口
- MySQL：业务数据库
- RandomForest：漏损风险预测模型
- Streamlit：可视化页面
- PyMySQL：连接 MySQL

## 1. 创建 Conda 环境

```powershell
conda create -n water-leak python=3.10 -y
conda activate water-leak
```

## 2. 安装依赖

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

## 3. 配置 MySQL

先确认你的 MySQL 服务已经启动。

进入 MySQL 后创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS water_leak_system
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;
```

## 4. 创建 .env 文件

复制 `.env.example` 为 `.env`，然后修改成你自己的 MySQL 用户名和密码：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=water_leak_system
MYSQL_CHARSET=utf8mb4
```

## 5. 生成模拟数据

```powershell
python generate_data.py
```

## 6. 训练模型

```powershell
python train_model.py
```

## 7. 启动 FastAPI 后端

```powershell
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/docs
```

## 8. 启动 Streamlit 前端

新开一个终端：

```powershell
conda activate water-leak
cd D:\water-leak-system-mysql
streamlit run app.py
```

打开：

```text
http://localhost:8501
```

## 常见问题

### 1. pymysql.err.OperationalError: Access denied

说明 `.env` 里的用户名或密码不对。

### 2. Unknown database

说明还没有创建数据库，先执行：

```sql
CREATE DATABASE water_leak_system DEFAULT CHARACTER SET utf8mb4;
```

### 3. Can't connect to MySQL server

说明 MySQL 服务没有启动，或者端口不是 3306。

