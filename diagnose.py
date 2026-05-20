# diagnose.py
"""
诊断脚本 - 检查系统配置和依赖
"""
import sys
import subprocess

def check_mysql():
    """检查MySQL连接"""
    print("\n" + "="*60)
    print("🔍 检查 MySQL 连接...")
    print("="*60)
    
    try:
        import pymysql
        from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
        
        print(f"✓ 配置信息：")
        print(f"  - Host: {MYSQL_HOST}")
        print(f"  - Port: {MYSQL_PORT}")
        print(f"  - User: {MYSQL_USER}")
        print(f"  - Database: {MYSQL_DATABASE}")
        
        # 尝试连接
        print("\n🔄 正在连接数据库...")
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        conn.close()
        print("✅ MySQL 连接成功！")
        return True
    except pymysql.err.OperationalError as e:
        print(f"❌ MySQL 连接失败！")
        print(f"错误信息: {e}")
        print("\n💡 可能的原因：")
        print("  1. MySQL 服务未启动")
        print("  2. 数据库用户名或密码错误")
        print("  3. 数据库主机地址或端口错误")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False

def check_dependencies():
    """检查依赖包"""
    print("\n" + "="*60)
    print("🔍 检查依赖包...")
    print("="*60)
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'streamlit',
        'pandas',
        'pymysql',
        'plotly',
        'requests'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - 缺失")
            missing.append(package)
    
    if missing:
        print(f"\n❌ 缺失的包: {', '.join(missing)}")
        print(f"运行命令安装: pip install {' '.join(missing)}")
        return False
    else:
        print("\n✅ 所有依赖包都已安装！")
        return True

def check_files():
    """检查项目文件"""
    print("\n" + "="*60)
    print("🔍 检查项目文件...")
    print("="*60)
    
    import os
    required_files = [
        'api.py',
        'app.py',
        'config.py',
        'database.py',
        'generate_data.py',
        'requirements.txt',
        '.env'
    ]
    
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - 缺失")
            missing.append(file)
    
    if missing:
        print(f"\n❌ 缺失的文件: {', '.join(missing)}")
        return False
    else:
        print("\n✅ 所有项目文件都存在！")
        return True

def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  🔧 供水管网漏损系统 - 诊断工具".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # 检查文件
    files_ok = check_files()
    
    # 检查依赖
    deps_ok = check_dependencies()
    
    # 检查MySQL
    mysql_ok = check_mysql()
    
    # 总结
    print("\n" + "="*60)
    print("📋 诊断总结")
    print("="*60)
    
    status = {
        '✅ 项目文件': files_ok,
        '✅ 依赖包': deps_ok,
        '✅ MySQL数据库': mysql_ok
    }
    
    for check, result in status.items():
        print(f"{check}: {'✅ 正常' if result else '❌ 异常'}")
    
    if all(status.values()):
        print("\n✅ 系统诊断完成！所有检查都通过。")
        print("\n🚀 现在可以运行：")
        print("  终端1: python api.py")
        print("  终端2: streamlit run app.py")
        return 0
    else:
        print("\n❌ 存在未解决的问题，请检查上面的错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())