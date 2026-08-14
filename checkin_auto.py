#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星芽网站自动签到脚本
API 接口：
  - 登录: POST /api/user/login (username, password)
  - 签到: POST /api/user/checkin (需要 Bearer Token)
"""

import os
import sys
import json
import time
import socket
import logging
import ipaddress
from datetime import datetime
from typing import Dict, List, Optional
import urllib.request
import urllib.error
import urllib.parse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# API 配置
API_BASE = os.getenv('XINGYA_API_BASE', 'https://xingya.site')
LOGIN_PATH = '/api/user/login'
CHECKIN_PATH = '/api/user/checkin'

# 账号列表（5个有效账号）
DEFAULT_ACCOUNTS = [
    {"email": "3312423979@qq.com", "password": "2560492318"},
    {"email": "rensk66@qq.com", "password": "2560492318"},
    {"email": "3470884203@qq.com", "password": "2560492318"},
    {"email": "3181227118@qq.com", "password": "2560492318"},
    {"email": "2560492318@qq.com", "password": "2560492318"},
]


def validate_host(url: str) -> bool:
    """验证 URL host，拒绝 localhost、环回、私有和保留地址，防止 SSRF"""
    try:
        parsed = urllib.parse.urlparse(url)
        
        # 只允许 http/https
        if parsed.scheme not in ['http', 'https']:
            return False
        
        host = parsed.hostname
        if not host:
            return False
        
        host_lower = host.lower()
        
        # 禁止的主机名
        forbidden = ['localhost', 'localhost.localdomain']
        if host_lower in forbidden:
            return False
        
        # 解析 DNS 获取 IP
        try:
            ip_str = socket.gethostbyname(host)
            ip = ipaddress.ip_address(ip_str)
        except (socket.gaierror, ValueError):
            return False
        
        # 拒绝私有、环回、保留地址
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False
        
        # IPv4 额外检查
        if isinstance(ip, ipaddress.IPv4Address):
            # 拒绝 0.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16, 224.0.0.0/4
            octets = [int(x) for x in ip_str.split('.')]
            if octets[0] in [0, 127] or (octets[0] == 169 and octets[1] == 254) or octets[0] >= 224:
                return False
        
        return True
    except Exception:
        return False


def http_request(method: str, url: str, headers: Optional[Dict] = None, 
                 data: Optional[Dict] = None, timeout: int = 10) -> Dict:
    """发送 HTTP 请求（安全版本，防止 SSRF）"""
    if not validate_host(url):
        raise ValueError(f"Forbidden host: {url}")
    
    headers = headers or {}
    headers.setdefault('User-Agent', 'Mozilla/5.0')
    headers.setdefault('Content-Type', 'application/json')
    
    body = json.dumps(data).encode('utf-8') if data else None
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {
                'status': response.status,
                'data': json.loads(response.read().decode('utf-8'))
            }
    except urllib.error.HTTPError as e:
        return {
            'status': e.code,
            'data': json.loads(e.read().decode('utf-8')) if e.fp else {}
        }
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise


def login(email: str, password: str) -> Optional[str]:
    """登录并返回 access_token"""
    url = f"{API_BASE}{LOGIN_PATH}"
    data = {"username": email, "password": password}
    
    try:
        resp = http_request('POST', url, data=data)
        result = resp['data']
        
        if result.get('success') and result.get('data', {}).get('access_token'):
            return result['data']['access_token']
        else:
            logger.error(f"Login failed: {result.get('message', 'Unknown error')}")
            return None
    except Exception as e:
        logger.error(f"Login error: {e}")
        return None


def checkin(token: str) -> Dict:
    """执行签到"""
    url = f"{API_BASE}{CHECKIN_PATH}"
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        resp = http_request('POST', url, headers=headers, data={})
        return resp['data']
    except Exception as e:
        logger.error(f"Checkin error: {e}")
        return {'success': False, 'message': str(e)}


def process_account(index: int, email: str, password: str) -> Dict:
    """处理单个账号的签到流程"""
    logger.info(f"***{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*** account: 账号{index}")
    
    # 登录
    token = login(email, password)
    if not token:
        logger.info(f"  ***账号{index}*** login failed")
        return {'success': False, 'account': index, 'error': 'login_failed'}
    
    # 签到
    result = checkin(token)
    
    if result.get('success'):
        quota = result.get('data', {}).get('quota_awarded', 0)
        date = result.get('data', {}).get('checkin_date', '')
        logger.info(f"  ***账号{index}*** ✅ 签到成功 - 获得额度: {quota}, 日期: {date}")
        return {'success': True, 'account': index, 'quota': quota, 'date': date}
    else:
        message = result.get('message', 'Unknown error')
        logger.info(f"  ***账号{index}*** ❌ 签到失败: {message}")
        return {'success': False, 'account': index, 'error': message}


def main():
    """主函数"""
    # 从环境变量读取账号（可选）
    accounts_json = os.getenv('XINGYA_ACCOUNTS_JSON')
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
        except Exception as e:
            logger.error(f"Failed to parse XINGYA_ACCOUNTS_JSON: {e}")
            accounts = DEFAULT_ACCOUNTS
    else:
        accounts = DEFAULT_ACCOUNTS
    
    logger.info(f"=== 星芽网站自动签到 ===")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"账号数量: {len(accounts)}\n")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for i, account in enumerate(accounts, start=1):
        email = account.get('email')
        password = account.get('password')
        
        if not email or not password:
            logger.info(f"***账号{i}*** 配置错误，跳过")
            failed_count += 1
            continue
        
        result = process_account(i, email, password)
        results.append(result)
        
        if result.get('success'):
            success_count += 1
        else:
            failed_count += 1
        
        # 延迟，避免请求过快
        if i < len(accounts):
            time.sleep(1)
    
    # 汇总
    logger.info(f"\nFinished: accounts={len(accounts)}, success={success_count}, failed={failed_count}")
    
    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
