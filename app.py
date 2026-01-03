"""
Veterans Verify - Flask Main App
ChatGPT Veterans Verification Automation System

Reference test_band_gemini_mail project architecture
Implement bulk temporary email creation + ChatGPT registration + Veterans verification
"""
import os
import json
import random
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, Optional

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from config import Config, setup_logging

# 初始化日志
setup_logging()
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Flask 应用
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# 配置
config = Config()

# 延迟初始化账号管理器
account_manager = None


def get_account_manager():
    """Get Account Manager (Lazy Initialization)"""
    global account_manager
    if account_manager is None:
        from account_manager import AccountManager
        from veteran_data import VeteranDataManager

        vet_manager = VeteranDataManager()
        account_manager = AccountManager(config, vet_manager)
        logger.info("[App] AccountManager initialization completed")
    return account_manager


# ==================== 认证 ====================

def check_auth():
    """检查认证"""
    # API Token 认证
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        if token == os.getenv('ADMIN_TOKEN'):
            return True

    # X-API-Key 认证
    api_key = request.headers.get('X-API-Key')
    if api_key and api_key == os.getenv('ADMIN_TOKEN'):
        return True

    # Session 认证
    if session.get('authenticated'):
        return True

    return False


def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页"""
    if not check_auth():
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        expected_username = os.getenv('ADMIN_USERNAME', 'admin')
        expected_password = os.getenv('ADMIN_PASSWORD', '')

        # 调试日志
        logger.info(f"[Login] 尝试登录: username={username}")
        logger.debug(f"[Login] 期望: username={expected_username}, password={'*' * len(expected_password) if expected_password else '(空)'}")

        if (username == expected_username and password == expected_password):
            session['authenticated'] = True
            logger.info(f"[Login] Login successful: {username}")
            return redirect(url_for('index'))
        else:
            logger.warning(f"[Login] Login failed: {username}")
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """API 登录"""
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')

    if (username == os.getenv('ADMIN_USERNAME', 'admin') and
        password == os.getenv('ADMIN_PASSWORD')):
        return jsonify({
            'success': True,
            'token': os.getenv('ADMIN_TOKEN', ''),
            'message': 'Login successful'
        })

    return jsonify({
        'success': False,
        'message': 'Invalid username or password'
    }), 401


@app.route('/logout')
def logout():
    """登出"""
    session.pop('authenticated', None)
    return redirect(url_for('login'))


# ==================== 账号 API ====================

@app.route('/api/accounts', methods=['POST'])
@require_auth
def create_account():
    """
    创建账号（支持批量）

    参数：
    - count: 创建数量（默认1）
    - interval: 批量创建间隔秒数（默认0）
    - profile_group: Profile 分组
    - async: 是否异步模式（默认true）
    """
    data = request.get_json() or {}

    try:
        count = int(data.get('count', 1))
    except (ValueError, TypeError):
        count = 1

    try:
        interval = float(data.get('interval', 0))
    except (ValueError, TypeError):
        interval = 0.0

    count = max(1, min(100, count))  # 限制 1-100
    interval = max(0.0, min(60.0, interval))

    profile_group = (data.get('profile_group') or '').strip()
    async_mode = data.get('async', True)

    manager = get_account_manager()

    # 批量创建
    if count > 1:
        manager.batch_create_accounts(count, interval, profile_group)
        return jsonify({
            'success': True,
            'message': f'Submitted {count} creation tasks',
            'count': count
        })

    # 单个创建
    account, error = manager.create_account(
        profile_group=profile_group,
        async_mode=async_mode
    )

    if not account:
        return jsonify({
            'success': False,
            'error': error or 'Account creation failed'
        }), 500

    return jsonify({
        'success': True,
        'message': 'Account created successfully',
        'account': account.to_dict()
    })


@app.route('/api/accounts', methods=['GET'])
@require_auth
def get_accounts():
    """获取账号列表"""
    status_filter = request.args.get('status')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    manager = get_account_manager()
    result = manager.get_accounts(
        status_filter=status_filter,
        page=page,
        per_page=per_page
    )

    return jsonify({
        'success': True,
        **result
    })


@app.route('/api/accounts/<email>', methods=['GET'])
@require_auth
def get_account(email: str):
    """获取单个账号"""
    manager = get_account_manager()
    account = manager.get_account(email)

    if not account:
        return jsonify({
            'success': False,
            'error': '账号不存在'
        }), 404

    return jsonify({
        'success': True,
        'account': account.to_dict()
    })


@app.route('/api/accounts/<email>', methods=['DELETE'])
@require_auth
def delete_account(email: str):
    """删除账号"""
    manager = get_account_manager()
    if manager.delete_account(email):
        return jsonify({
            'success': True,
            'message': '账号已删除'
        })
    return jsonify({
        'success': False,
        'error': '账号不存在'
    }), 404


@app.route('/api/accounts/<email>/retry', methods=['POST'])
@require_auth
def retry_account(email: str):
    """重试失败的账号"""
    manager = get_account_manager()
    if manager.retry_account(email):
        return jsonify({
            'success': True,
            'message': '重试已开始'
        })
    return jsonify({
        'success': False,
        'error': '账号不存在或状态不是失败'
    }), 400


@app.route('/api/accounts/stop-all', methods=['POST'])
@require_auth
def stop_all():
    """停止所有任务"""
    manager = get_account_manager()
    manager.stop_all()
    return jsonify({
        'success': True,
        'message': '已停止所有任务'
    })


@app.route('/api/accounts/export', methods=['GET'])
@require_auth
def export_accounts():
    """导出成功的账号"""
    manager = get_account_manager()
    result = manager.get_accounts(status_filter='success', per_page=10000)

    export_data = {
        'exported_at': datetime.now().isoformat(),
        'count': len(result['accounts']),
        'accounts': result['accounts']
    }

    return jsonify(export_data)


# ==================== 系统 API ====================

@app.route('/api/status', methods=['GET'])
@require_auth
def api_status():
    """系统状态"""
    manager = get_account_manager()
    status = manager.get_status()

    return jsonify({
        'success': True,
        **status,
        'config': {
            'max_workers': config.get_max_workers(),
            'headless': config.get_headless(),
            'email_configs': len(config.get_email_configs())
        }
    })


@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """获取设置"""
    return jsonify({
        'success': True,
        'settings': {
            'max_workers': config.get_max_workers(),
            'headless': config.get_headless(),
            'email_configs': config.get_email_configs(),
            'human_delay': config.get_human_delay(),
            'request_interval': config.get_request_interval(),
            'cooldown_range': config.get_cooldown_range(),
        }
    })


@app.route('/api/email-configs', methods=['GET'])
@require_auth
def get_email_configs():
    """获取邮箱配置"""
    configs = config.get_email_configs()
    # 隐藏敏感信息
    safe_configs = []
    for cfg in configs:
        safe_configs.append({
            'worker_domain': cfg.get('worker_domain', ''),
            'email_domain': cfg.get('email_domain', ''),
            'admin_password': '***' if cfg.get('admin_password') else ''
        })
    return jsonify({
        'success': True,
        'configs': safe_configs
    })


@app.route('/api/veteran-data/stats', methods=['GET'])
@require_auth
def get_veteran_stats():
    """获取军人数据统计"""
    manager = get_account_manager()
    if manager.veteran_data_manager:
        stats = manager.veteran_data_manager.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    return jsonify({
        'success': False,
        'error': '军人数据管理器未初始化'
    }), 500


@app.route('/api/manual/submit-sheerid', methods=['POST'])
@require_auth
def manual_submit_sheerid():
    """Manual: Submit SheerID Form"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    email = data.get('email', '').strip()
    proxy = data.get('proxy', '').strip() or None

    if not url or not email:
        return jsonify({'success': False, 'error': 'URL and Email are required'}), 400

    manager = get_account_manager()
    manager.run_manual_sheerid_task(url, email, proxy=proxy)

    return jsonify({'success': True, 'message': 'SheerID submission task started'})


@app.route('/api/manual/verify-token', methods=['POST'])
@require_auth
def manual_verify_token():
    """Manual: Verify Email Token"""
    data = request.get_json() or {}
    verify_url = data.get('url', '').strip()
    proxy = data.get('proxy', '').strip() or None

    if not verify_url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    manager = get_account_manager()
    manager.run_manual_token_task(verify_url, proxy=proxy)

    return jsonify({'success': True, 'message': 'Token verification task started'})


@app.route('/api/manual/generate-sheerid', methods=['POST'])
@require_auth
def manual_generate_sheerid():
    """Manual: Generate SheerID Link from JWT"""
    data = request.get_json() or {}
    jwt_token = data.get('jwt', '').strip()
    proxy = data.get('proxy', '').strip() or None

    if not jwt_token:
        return jsonify({'success': False, 'error': 'JWT Token is required'}), 400

    manager = get_account_manager()
    manager.run_manual_generate_sheerid_task(jwt_token, proxy=proxy)

    return jsonify({'success': True, 'message': 'Generation task started'})


@app.route('/api/proxies', methods=['GET'])
@require_auth
def get_proxies():
    """Get list of proxies from proxies.txt"""
    proxies = []
    proxy_file = os.path.join(os.getcwd(), 'proxies.txt')
    
    if os.path.exists(proxy_file):
        try:
            with open(proxy_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.append(line)
        except Exception as e:
            logger.error(f"Failed to read proxies.txt: {e}")
    
    return jsonify({
        'success': True, 
        'proxies': proxies
    })


@app.route('/api/manual/tasks', methods=['GET'])
@require_auth
def get_manual_tasks():
    """Get manual task history"""
    manager = get_account_manager()
    return jsonify({
        'success': True,
        'tasks': manager.manual_tasks
    })
@app.route('/api/manual/generate-status', methods=['GET'])
@require_auth
def manual_generate_status():
    """Manual: Get Generation Status"""
    manager = get_account_manager()
    return jsonify({
        'success': True,
        'status': getattr(manager, 'manual_gen_status', 'idle'),
        'result': getattr(manager, 'manual_gen_result', None)
    })


# ==================== 健康检查 ====================

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})


@app.route('/api/health')
def api_health():
    """API 健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


# ==================== 启动 ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', '7870'))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    logger.info(f"[App] Veterans Verify started on port {port}")
    logger.info(f"[App] Visit http://127.0.0.1:{port}")

    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
