import requests, json, re, os
from datetime import datetime

# 初始化 session
session = requests.session()

# 从环境变量中获取配置
url = os.environ.get('URL')  # 初始域名
config = os.environ.get('CONFIG')  # 用户名和密码配置
SCKEY = os.environ.get('SCKEY')  # Server酱推送密钥

def send_notification(content):
    """推送通知到Server酱"""
    if SCKEY:
        push_url = f'https://sctapi.ftqq.com/{SCKEY}.send?title=机场签到&desp={content}'
        try:
            requests.post(push_url)
            print('推送成功')
        except Exception as e:
            print(f'推送失败: {e}')

def get_latest_domain():
    """获取最新的有效域名"""
    global url
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            if "官网域名已更改" in response.text or "Domain deprecated" in response.text:
                print("检测到域名变更通知，正在提取新域名...")
                # 正则提取新域名
                patterns = [
                    r'<h2>.*?(?:域名|domain)[：:]\s*([a-zA-Z0-9.-]+)</h2>',  # 方法1：从<h2>标签提取
                    r'https?://([a-zA-Z0-9.-]+)/auth/login',              # 方法2：从JavaScript提取
                    r'(?:域名|domain)[：:]\s*([a-zA-Z0-9.-]+)'            # 方法3：宽松匹配
                ]
                for pattern in patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        new_domain = match.group(1)
                        print(f"提取到新域名: {new_domain}")
                        return new_domain
                print("⚠️ 检测到域名变更但无法提取新域名")
            else:
                print("✅ 当前域名正常")
                return None
    except Exception as e:
        print(f"域名 {url} 检测失败: {e}")
        return None

def update_domain(new_domain):
    """更新全局域名并动态生成URL"""
    global url
    url = f"https://{new_domain}"
    print(f"已切换至最新域名: {url}")
    return f"{url}/auth/login", f"{url}/user/checkin"

def sign(order, user, pwd):
    """执行签到流程"""
    login_url, check_url = f"{url}/auth/login", f"{url}/user/checkin"
    
    header = {
        'origin': url,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    }
    data = {'email': user, 'passwd': pwd}

    try:
        # 登录尝试（最多重试2次）
        for retry in range(2):
            print(f'\n=== 账号{order} 第{retry+1}次登录 ===')
            try:
                response = session.post(login_url, headers=header, data=data, timeout=15)
                response.raise_for_status()
                result = json.loads(response.text)
                print(result.get('msg', '无返回信息'))

                if result.get('ret') == 1:  # 登录成功
                    print("✅ 登录成功")
                    break
                else:  # 登录失败，尝试更新域名
                    new_domain = get_latest_domain()
                    if new_domain:
                        login_url, check_url = update_domain(new_domain)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"登录异常: {e}")
                if retry == 1:  # 最后一次尝试失败后推送
                    send_notification("登录失败：请检查网络或配置")
                    return
        else:
            send_notification("登录失败：重试次数用尽")
            return

        # 执行签到
        print("\n=== 执行签到 ===")
        response = session.post(check_url, headers=header, timeout=15)
        result = json.loads(response.text)
        msg = result.get('msg', '无签到结果')
        print(f"签到结果: {msg}")
        send_notification(msg)

    except Exception as e:
        error_msg = f"签到失败: {str(e)}"
        print(error_msg)
        send_notification(error_msg)
    finally:
        print(f'\n=== 账号{order} 流程结束 ===')

if __name__ == '__main__':
    # 校验环境变量
    if not url or not config:
        print("❌ 错误：请设置 URL 和 CONFIG 环境变量")
        exit()

    # 处理多账户
    accounts = config.splitlines()
    if len(accounts) % 2 != 0:
        send_notification("配置错误：账号/密码不匹配")
        exit()

    for idx in range(len(accounts)//2):
        user = accounts[idx*2]
        pwd = accounts[idx*2+1]
        sign(idx+1, user, pwd)
