from typing import Iterable, Optional

import pandas as pd
import pymysql

from config import (
    MYSQL_CHARSET,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


def get_connection(database: Optional[str] = None):
    """
    获取 MySQL 连接。

    注意：
    这里不要使用 DictCursor。
    pandas.read_sql 和 DictCursor 在当前项目中容易出现解析异常。
    """
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=database if database is not None else MYSQL_DATABASE,
        charset=MYSQL_CHARSET,
        autocommit=False,
    )


def create_database_if_not_exists() -> None:
    """
    如果数据库不存在，则自动创建。
    """
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset=MYSQL_CHARSET,
        autocommit=True,
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}`
                DEFAULT CHARACTER SET utf8mb4
                DEFAULT COLLATE utf8mb4_unicode_ci
                """
            )
    finally:
        conn.close()


def init_db() -> None:
    """
    初始化数据库表结构 - 按照毕业设计PDF第5.3节设计
    """
    create_database_if_not_exists()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # water_location 表：水表位置信息
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS water_location (
                    water_id INT PRIMARY KEY AUTO_INCREMENT,
                    longitude DOUBLE NOT NULL COMMENT '位置经度',
                    latitude DOUBLE NOT NULL COMMENT '位置纬度',
                    total_usage DOUBLE NOT NULL DEFAULT 0 COMMENT '累计用量',
                    average_leakage_rate DOUBLE NOT NULL DEFAULT 0 COMMENT '平均漏损率',
                    INDEX idx_location (longitude, latitude)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水表位置信息表'
                """
            )

            # water_record 表：流量计记录列表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS water_record (
                    record_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    water_id INT NOT NULL COMMENT '水表编号',
                    record_date BIGINT NOT NULL COMMENT '记录日期（时间戳）',
                    instant_usage DOUBLE NOT NULL COMMENT '瞬时用量',
                    node_outflow DOUBLE NOT NULL COMMENT '节点流出',
                    node_inflow DOUBLE NOT NULL COMMENT '节点流入',
                    leakage_rate DOUBLE NOT NULL COMMENT '漏损率',
                    INDEX idx_water_id (water_id),
                    INDEX idx_record_date (record_date),
                    CONSTRAINT fk_water_location
                        FOREIGN KEY (water_id) REFERENCES water_location(water_id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流量计记录列表'
                """
            )

            # water_resident 表：维修员工管理信息
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS water_resident (
                    resident_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    water_id INT NOT NULL COMMENT '水表编号',
                    resident_name VARCHAR(255) NOT NULL COMMENT '员工姓名',
                    leak_detection VARCHAR(255) NOT NULL COMMENT '漏损监测',
                    processing_status VARCHAR(255) NOT NULL COMMENT '处理状态',
                    INDEX idx_water_id (water_id),
                    CONSTRAINT fk_water_resident
                        FOREIGN KEY (water_id) REFERENCES water_location(water_id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='维修员工管理信息表'
                """
            )

        conn.commit()


def reset_db() -> None:
    """
    重置数据库表。
    """
    create_database_if_not_exists()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("DROP TABLE IF EXISTS water_resident")
            cursor.execute("DROP TABLE IF EXISTS water_record")
            cursor.execute("DROP TABLE IF EXISTS water_location")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        conn.commit()

    init_db()


def insert_dataframe(table_name: str, df: pd.DataFrame) -> None:
    """
    将 DataFrame 批量插入 MySQL。
    """
    if df.empty:
        return

    columns = list(df.columns)
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join([f"`{col}`" for col in columns])
    sql = f"INSERT INTO `{table_name}` ({column_sql}) VALUES ({placeholders})"

    values = []
    for _, row in df.iterrows():
        clean_row = []
        for col in columns:
            value = row[col]
            if pd.isna(value):
                value = None
            clean_row.append(value)
        values.append(tuple(clean_row))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, values)
        conn.commit()


def read_sql(query: str, params: Optional[Iterable] = None) -> pd.DataFrame:
    """
    查询 MySQL 并返回 DataFrame。
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

    return pd.DataFrame(list(rows), columns=columns)


def execute_sql(query: str, params: Optional[Iterable] = None) -> None:
    """
    执行 INSERT / UPDATE / DELETE 等 SQL。
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
        conn.commit()


def update_meter_status(water_id: int, status: str) -> None:
    """
    更新水表状态。
    """
    execute_sql(
        "UPDATE water_meter SET status = %s WHERE water_id = %s",
        (status, water_id),
    )
