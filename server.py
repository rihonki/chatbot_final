import os
import json
import tornado.ioloop
import tornado.web
import tornado.websocket
import uuid
import datetime
import openai
import logging
import random
import requests
import hashlib
from database import get_db, close_db
# 导入新闻爬虫
from news_crawler import NewsCrawler

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatHandler(tornado.websocket.WebSocketHandler):
    # 存储所有活动的WebSocket连接
    clients = {}
    # 存储在线用户信息
    online_users = {}
    # 存储AI配置信息
    ai_config = None
    # 存储已认证用户会话
    authenticated_users = {}
    
    @classmethod
    def load_ai_config(cls):
        """从config.json加载AI配置信息"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                cls.ai_config = config.get('ai_config', {})
                logger.info("AI配置加载成功")
        except Exception as e:
            logger.error(f"加载AI配置失败: {e}")
            # 使用默认配置
            cls.ai_config = {
                "api_key": "sk-heafrvmzonzqknnsuotejboskpjsgustuddvhcyqbavcdpfx",
                "base_url": "https://api.siliconflow.cn/v1",
                "model_name": "Qwen/Qwen2.5-7B-Instruct",
                "temperature": 0.7,
                "max_tokens": 1024,
                "system_prompt": "角色：抖音网红那艺娜的老公\n\n姓名：张兵\n\n性别：男\n\n功能：\n\n--接受用户提问，进行回复。那艺娜的相关信息如下\n\n\"1、代表作《爱如火》和《贝如塔》\n\n2、口头禅'你妈妈才是男的'\"\n\n限定：\n\n--如果用户发送\"@张兵 那艺娜\"，回复：砰砰砰\n\n--如果用户询问张兵恋情相关问题，则回复\"我从来没说过我爱娜娜\"",
                "fallback_responses": ["砰砰砰", "娜艺那", "嗨娜娜，你卡了"]
            }
    
    def check_origin(self, origin):
        return True
    
    def open(self):
        self.id = str(uuid.uuid4())
        self.username = None
        ChatHandler.clients[self.id] = self
        logger.info(f"新的连接: {self.id}")
    
    def on_message(self, message):
        try:
            data = json.loads(message)
            
            # 处理用户登录
            if data['type'] == 'login':
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                
                # 验证输入
                if not username or not password:
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': False,
                        'message': '用户名和密码不能为空'
                    }))
                    return
                
                # 检查用户名是否包含禁止的内容
                if '张兵' in username or 'zhangbing' in username.lower():
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': False,
                        'message': '用户名包含禁止内容，请重新输入'
                    }))
                    return
                
                # 检查用户是否已在线
                if username in ChatHandler.online_users.values():
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': False,
                        'message': '该用户已在线，请稍后再试'
                    }))
                    return
                
                # 验证用户凭据
                db = get_db()
                password = data.get('password', '').strip()
                
                # 检查用户名和密码是否为空
                if not username or not password:
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': False,
                        'message': '用户名和密码不能为空'
                    }))
                    return
                
                # 使用login_user方法验证用户名和密码
                success, message = db.login_user(username, password)
                if success:
                    # 登录成功，记录用户信息
                    self.username = username
                    ChatHandler.online_users[self.id] = username
                    ChatHandler.authenticated_users[self.id] = username
                    
                    # 生成会话ID并保存会话
                    session_id = str(uuid.uuid4())
                    self.session_id = session_id
                    user_id = db.get_user_id(username)
                    db.save_session(session_id, user_id)
                    
                    # 通知当前用户登录成功
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': True,
                        'message': f'欢迎 {username}！',
                        'username': username,
                        'online_users': list(ChatHandler.online_users.values())
                    }))
                    
                    # 通知其他用户有新用户上线
                    join_message = {
                        'type': 'user_joined',
                        'username': username,
                        'online_users': list(ChatHandler.online_users.values()),
                        'message': f"{username} 加入了聊天室",
                        'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                    }
                    self.broadcast_message(join_message, exclude=self.id)
                    
                    # 保存系统消息到数据库
                    db.save_message('系统', 'system_message', f"{username} 加入了聊天室")
                    
                    # 加载历史消息
                    history_messages = db.get_history_messages(limit=100)
                    self.write_message(json.dumps({
                        'type': 'history',
                        'messages': history_messages
                    }))
                else:
                    # 登录失败
                    self.write_message(json.dumps({
                        'type': 'login_response',
                        'success': False,
                        'message': message
                    }))
                
            # 处理聊天消息
            elif data['type'] == 'message':
                if not self.username:
                    return
                
                message_content = data['content']
                
                # 检查是否是特殊命令（@电影或@张兵）
                if message_content.startswith('@电影'):
                    # 实现电影播放功能，使用指定的解析地址
                    parts = message_content.split(' ', 1)
                    if len(parts) > 1 and parts[1].strip():
                        url = parts[1].strip()
                        # 使用指定的解析地址
                        parse_service = 'https://jx.m3u8.tv/jiexi/?url='
                        # 构建完整的iframe src地址
                        iframe_src = f'{parse_service}{url}'
                        
                        # 广播包含iframe的消息给所有用户
                        movie_message_data = {
                            'type': 'movie_message',
                            'username': self.username,
                            'content': message_content,
                            'iframe_src': iframe_src,
                            'iframe_width': 400,
                            'iframe_height': 400,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        self.broadcast_message(movie_message_data)
                        
                        # 保存电影消息到数据库
                        db = get_db()
                        additional_data = {
                            'iframe_src': iframe_src,
                            'iframe_width': 400,
                            'iframe_height': 400
                        }
                        db.save_message(self.username, 'movie_message', message_content, additional_data)
                        
                        # 同时发送确认消息给命令发送者
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'movie',
                            'content': message_content,
                            'message': '电影链接已成功解析并展示'
                        }))
                    else:
                        # 如果没有提供URL，显示错误消息
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'movie',
                            'content': message_content,
                            'message': '请提供有效的电影URL，格式：@电影 url'
                        }))
                elif message_content.startswith('@音乐'):
                    # 实现音乐播放功能（支持指定URL或随机获取）
                    try:
                        # 解析命令参数
                        parts = message_content.split(' ', 1)
                        music_info = {}
                        is_vip_music = False
                        
                        # 检查是否提供了URL参数
                        if len(parts) > 1 and parts[1].strip():
                            user_url = parts[1].strip()
                            logger.info(f"用户指定的音乐URL: {user_url}")
                            
                            # 创建基本音乐信息
                            music_info = {
                                'name': '用户指定音乐',
                                'singer': '未知艺术家',
                                'url': user_url,
                                'image': 'https://via.placeholder.com/100x100?text=Music'
                            }
                            
                            # 简单检测是否可能是VIP音乐的URL模式
                            vip_keywords = ['vip', 'pay', 'member', 'premium', 'subscribe']
                            url_lower = user_url.lower()
                            
                            # 检查URL中是否包含VIP相关关键词
                            for keyword in vip_keywords:
                                if keyword in url_lower:
                                    is_vip_music = True
                                    break
                            
                            # 如果不是VIP音乐，尝试测试URL是否可访问
                            if not is_vip_music:
                                try:
                                    test_response = requests.head(user_url, timeout=3, allow_redirects=True)
                                    logger.info(f"URL测试状态码: {test_response.status_code}")
                                    
                                    # 检查重定向后的URL是否包含VIP关键词
                                    final_url = test_response.url.lower()
                                    for keyword in vip_keywords:
                                        if keyword in final_url:
                                            is_vip_music = True
                                            break
                                    
                                    # 检查内容类型是否为音频
                                    content_type = test_response.headers.get('Content-Type', '').lower()
                                    if 'audio' not in content_type:
                                        logger.warning(f"URL不是音频文件，Content-Type: {content_type}")
                                except Exception as test_e:
                                    logger.warning(f"URL测试失败: {str(test_e)}")
                        else:
                            # 没有提供URL，调用API获取随机音乐
                            api_key = "4cf665b5f52395a0"
                            api_url = f"https://v2.xxapi.cn/api/randomkuwo?api-key={api_key}"
                            
                            logger.info(f"获取随机音乐：URL={api_url}")
                            
                            # 发送请求获取音乐信息
                            response = requests.get(api_url, timeout=5)
                            logger.info(f"音乐API响应状态码: {response.status_code}")
                            logger.info(f"音乐API响应内容: {response.text}")
                            
                            try:
                                music_data = response.json()
                                logger.info(f"音乐API响应JSON: {music_data}")
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON解析错误: {e}")
                                music_data = {}
                            
                            # 处理API响应
                            if music_data.get('code') == 200 and music_data.get('data'):
                                # 解析音乐数据
                                music_info = music_data['data']
                                # 确保音乐信息包含有效的URL字段
                                # 检查并标准化URL字段，适配不同的API响应格式
                                if 'url' not in music_info:
                                    # 尝试从其他可能的字段获取音频URL
                                    if 'mp3' in music_info:
                                        music_info['url'] = music_info['mp3']
                                    elif 'audio_url' in music_info:
                                        music_info['url'] = music_info['audio_url']
                                    elif 'file_url' in music_info:
                                        music_info['url'] = music_info['file_url']
                                    logger.info(f"标准化音乐URL字段后的数据: {music_info}")
                                
                                # 检查是否为VIP音乐
                                if 'vip' in music_info and music_info['vip']:
                                    is_vip_music = True
                                elif 'url' in music_info and music_info['url']:
                                    url_lower = music_info['url'].lower()
                                    for keyword in vip_keywords:
                                        if keyword in url_lower:
                                            is_vip_music = True
                                            break
                            else:
                                # API调用失败或返回异常
                                logger.warning(f"音乐API返回异常，code={music_data.get('code')}，msg={music_data.get('msg')}")
                                
                                # 发送错误消息给用户
                                self.write_message(json.dumps({
                                    'type': 'special_command',
                                    'command': 'music',
                                    'content': message_content,
                                    'message': f'音乐获取失败: {music_data.get('msg', '未知错误')}'
                                }))
                                return
                        
                        # 标记VIP音乐
                        if is_vip_music:
                            music_info['is_vip'] = True
                            music_info['url'] = ''  # 清空URL以防止播放
                            logger.info(f"检测到VIP音乐: {music_info.get('name', '用户指定音乐')}")
                        
                        # 构建音乐卡片数据
                        music_card_data = {
                            'type': 'music_message',
                            'username': self.username,
                            'content': message_content,
                            'music_info': music_info,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        
                        # 广播音乐卡片给所有用户
                        self.broadcast_message(music_card_data)
                        
                        # 保存音乐消息到数据库
                        db = get_db()
                        additional_data = {
                            'music_info': music_info
                        }
                        db.save_message(self.username, 'music_message', message_content, additional_data)
                        
                        # 同时发送确认消息给命令发送者
                        if is_vip_music:
                            self.write_message(json.dumps({
                                'type': 'special_command',
                                'command': 'music',
                                'content': message_content,
                                'message': '该音乐为vip歌曲无法播放'
                            }))
                        else:
                            self.write_message(json.dumps({
                                'type': 'special_command',
                                'command': 'music',
                                'content': message_content,
                                'message': '音乐卡片已生成'
                            }))

                    except Exception as e:
                        logger.error(f"音乐获取错误: {e}")
                        # 发送错误消息给用户
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'music',
                            'content': message_content,
                            'message': f'音乐获取失败: {str(e)}'
                        }))

                elif message_content.startswith('@天气'):
                    # 实现天气查询功能（使用多个免费天气API作为备选）
                    try:
                        # 解析城市名称
                        parts = message_content.split(' ', 1)
                        if len(parts) > 1 and parts[1].strip():
                            city = parts[1].strip()
                            logger.info(f"查询天气：城市={city}")
                            
                            # 多个天气API作为备选，逐一尝试直到成功获取数据
                            weather_reply = None
                            
                            # API 1: 和风天气免费API
                            try:
                                api_url = f"https://devapi.qweather.com/v7/weather/now?location={city}&key=25434092d12f46c2a3a1d860b8bd2c9d"
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                }
                                
                                weather_response = requests.get(api_url, headers=headers, timeout=10)
                                logger.info(f"和风天气API响应状态码: {weather_response.status_code}")
                                logger.info(f"和风天气API响应内容: {weather_response.text}")
                                
                                weather_data = weather_response.json()
                                
                                if weather_data.get('code') == '200':
                                    now = weather_data.get('now', {})
                                    if now:
                                        weather_reply = f"{city}当前天气：\n"
                                        weather_reply += f"实时温度：{now.get('temp', '未知')}°C\n"
                                        weather_reply += f"天气状况：{now.get('text', '未知')}\n"
                                        weather_reply += f"湿度：{now.get('humidity', '未知')}%\n"
                                        weather_reply += f"风力情况：{now.get('windDir', '未知')} {now.get('windScale', '未知')}级\n"
                                        weather_reply += f"体感温度：{now.get('feelsLike', '未知')}°C\n"
                                        weather_reply += f"更新时间：{now.get('obsTime', '未知')}\n"
                                        weather_reply = weather_reply.rstrip('\n')
                                        logger.info(f"和风天气查询成功: {weather_reply}")
                            except Exception as e1:
                                logger.warning(f"和风天气API调用失败: {str(e1)}")
                            
                            # API 2: 免费天气API（备选）
                            if not weather_reply:
                                try:
                                    # 使用免费天气API，不需要API密钥
                                    api_url = f"https://wttr.in/{city}?format=j1"
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                    }
                                    
                                    weather_response = requests.get(api_url, headers=headers, timeout=10)
                                    logger.info(f"WTTR API响应状态码: {weather_response.status_code}")
                                    
                                    if weather_response.status_code == 200:
                                        weather_data = weather_response.json()
                                        current_condition = weather_data.get('current_condition', [{}])[0]
                                        if current_condition:
                                            weather_reply = f"{city}当前天气：\n"
                                            weather_reply += f"实时温度：{current_condition.get('temp_C', '未知')}°C\n"
                                            weather_reply += f"天气状况：{current_condition.get('weatherDesc', [{}])[0].get('value', '未知')}\n"
                                            weather_reply += f"湿度：{current_condition.get('humidity', '未知')}%\n"
                                            weather_reply += f"风力情况：{current_condition.get('windspeedKmph', '未知')} km/h {current_condition.get('winddirDegree', '未知')}°\n"
                                            weather_reply += f"体感温度：{current_condition.get('FeelsLikeC', '未知')}°C\n"
                                            weather_reply += f"更新时间：{current_condition.get('observation_time', '未知')}\n"
                                            weather_reply = weather_reply.rstrip('\n')
                                            logger.info(f"WTTR天气查询成功: {weather_reply}")
                                except Exception as e2:
                                    logger.warning(f"WTTR API调用失败: {str(e2)}")
                            
                            # API 3: OpenWeatherMap 免费API（备选，使用测试密钥）
                            if not weather_reply:
                                try:
                                    api_key = "e10a4e6b3e04c60312f99066cfc45b6c"  # 这是一个示例密钥，请替换为有效的密钥
                                    api_url = "https://api.openweathermap.org/data/2.5/weather"
                                    params = {
                                        'q': city,
                                        'appid': api_key,
                                        'units': 'metric',  # 使用摄氏度
                                        'lang': 'zh_cn'  # 使用中文
                                    }
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                    }
                                    
                                    weather_response = requests.get(api_url, params=params, headers=headers, timeout=10)
                                    logger.info(f"OpenWeatherMap API响应状态码: {weather_response.status_code}")
                                    
                                    if weather_response.status_code == 200:
                                        weather_data = weather_response.json()
                                        weather_reply = f"{city}当前天气：\n"
                                        
                                        # 添加温度信息
                                        if 'main' in weather_data:
                                            weather_reply += f"实时温度：{weather_data['main'].get('temp', '未知')}°C\n"
                                            weather_reply += f"体感温度：{weather_data['main'].get('feels_like', '未知')}°C\n"
                                            weather_reply += f"湿度：{weather_data['main'].get('humidity', '未知')}%\n"
                                        
                                        # 添加天气状况
                                        if 'weather' in weather_data and len(weather_data['weather']) > 0:
                                            weather_reply += f"天气状况：{weather_data['weather'][0].get('description', '未知')}\n"
                                        
                                        # 添加风力信息
                                        if 'wind' in weather_data:
                                            wind_speed = weather_data['wind'].get('speed', '未知')
                                            wind_deg = weather_data['wind'].get('deg', 0)
                                            # 将风向转换为中文方向
                                            directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
                                            direction = directions[round(wind_deg / 45) % 8] if isinstance(wind_deg, int) else '未知'
                                            weather_reply += f"风力情况：{direction}风 {wind_speed} m/s\n"
                                        
                                        # 添加更新时间
                                        if 'dt' in weather_data:
                                            update_time = datetime.datetime.fromtimestamp(weather_data['dt'])
                                            weather_reply += f"更新时间：{update_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                        
                                        weather_reply = weather_reply.rstrip('\n')
                                        logger.info(f"OpenWeatherMap天气查询成功: {weather_reply}")
                                except Exception as e3:
                                    logger.warning(f"OpenWeatherMap API调用失败: {str(e3)}")
                            
                            # API 4: 免费详细天气API（备选）
                            if not weather_reply:
                                try:
                                    api_url = "https://v2.xxapi.cn/api/weatherDetails"
                                    params = {
                                        'city': city,
                                        'key': '4cf665b5f52395a0'
                                    }
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                    }
                                    
                                    weather_response = requests.get(api_url, params=params, headers=headers, timeout=10)
                                    logger.info(f"详细天气API响应状态码: {weather_response.status_code}")
                                    logger.info(f"详细天气API响应内容: {weather_response.text}")
                                    
                                    if weather_response.status_code == 200:
                                        weather_data = weather_response.json()
                                        if weather_data.get('code') == 200:
                                            data = weather_data.get('data', {})
                                            city_info = data.get('city', city)
                                            weather_list = data.get('data', [])
                                            if weather_list:
                                                today_weather = weather_list[0]
                                                real_time_data = today_weather.get('real_time_weather', [])
                                                if real_time_data:
                                                    # 获取最新的实时天气数据
                                                    latest_weather = real_time_data[0]
                                                    weather_reply = f"{city_info}当前天气：\n"
                                                    weather_reply += f"实时温度：{latest_weather.get('temperature', '未知')}°C\n"
                                                    weather_reply += f"天气状况：{latest_weather.get('weather', '未知')}\n"
                                                    weather_reply += f"湿度：{latest_weather.get('humidity', '未知')}\n"
                                                    weather_reply += f"风力情况：{latest_weather.get('wind_dir', '未知')} {latest_weather.get('wind_speed', '未知')}\n"
                                                    weather_reply += f"云量：{latest_weather.get('cloud_cover', '未知')}\n"
                                                    weather_reply += f"气压：{latest_weather.get('pressure', '未知')}\n"
                                                    weather_reply += f"降水量：{latest_weather.get('precipitation', '未知')}\n"
                                                    weather_reply += f"更新时间：{latest_weather.get('time', '未知')}\n"
                                                    weather_reply = weather_reply.rstrip('\n')
                                                    logger.info(f"详细天气API查询成功: {weather_reply}")
                                except Exception as e4:
                                    logger.warning(f"详细天气API调用失败: {str(e4)}")
                            
                            # 如果所有API都调用失败，使用最终的备用方案（基于IP的天气服务）
                            if not weather_reply:
                                try:
                                    # 使用ipinfo.io获取用户IP对应的地理位置天气信息
                                    api_url = "https://ipinfo.io/json"
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                    }
                                    
                                    ip_response = requests.get(api_url, headers=headers, timeout=10)
                                    logger.info(f"IPInfo API响应状态码: {ip_response.status_code}")
                                    
                                    if ip_response.status_code == 200:
                                        ip_data = ip_response.json()
                                        location = ip_data.get('city', '')
                                        
                                        # 使用获取到的城市信息再次尝试天气查询
                                        if location:
                                            wttr_url = f"https://wttr.in/{location}?format=j1"
                                            wttr_response = requests.get(wttr_url, headers=headers, timeout=10)
                                            
                                            if wttr_response.status_code == 200:
                                                weather_data = wttr_response.json()
                                                current_condition = weather_data.get('current_condition', [{}])[0]
                                                if current_condition:
                                                    weather_reply = f"{location}当前天气（基于IP定位）：\n"
                                                    weather_reply += f"实时温度：{current_condition.get('temp_C', '未知')}°C\n"
                                                    weather_reply += f"天气状况：{current_condition.get('weatherDesc', [{}])[0].get('value', '未知')}\n"
                                                    weather_reply += f"湿度：{current_condition.get('humidity', '未知')}%\n"
                                                    weather_reply = weather_reply.rstrip('\n')
                                                else:
                                                    weather_reply = f"无法获取{location}的天气信息"
                                    
                                except Exception as e4:
                                    logger.warning(f"IPInfo备用方案调用失败: {str(e4)}")
                            
                            # 如果所有尝试都失败，设置默认错误消息
                            if not weather_reply:
                                weather_reply = f"{city}的天气数据暂时不可用，请稍后再试"
                        
                        else:
                            weather_reply = "请指定要查询的城市，例如: @天气 北京"
                    except Exception as e:
                        logger.error(f"天气查询API调用失败: {str(e)}")
                        weather_reply = "天气查询服务暂时不可用，请稍后再试"
                    
                    # 首先广播用户输入的@天气消息
                    self.broadcast_message({
                        'type': 'message',
                        'username': self.username,
                        'content': message_content,
                        'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                    })
                    
                    try:
                        # 广播天气回复消息给所有用户
                        weather_message_data = {
                            'type': 'ai_message',
                            'username': '系统',
                            'content': weather_reply,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        self.broadcast_message(weather_message_data)
                        
                        # 保存天气回复到数据库
                        db = get_db()
                        db.save_message('系统', 'ai_message', weather_reply)
                        
                        # 同时发送确认消息给命令发送者
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'weather',
                            'content': message_content,
                            'message': '天气查询完成'
                        }))
                    except Exception as e:
                        logger.error(f"天气查询处理失败: {str(e)}")
                        try:
                            self.write_message(json.dumps({
                                'type': 'error',
                                'data': {
                                    'message': '天气查询服务暂时不可用，请稍后再试'
                                }
                            }))
                        except:
                            pass
                elif message_content.startswith('@新闻'):
                    # 实现新闻查询功能，获取百度热搜前十条并生成PDF
                    try:
                        logger.info(f"查询新闻请求: {message_content}")
                        
                        # 解析命令参数（可选的关键词）
                        parts = message_content.split(' ', 1)
                        keyword = parts[1].strip() if len(parts) > 1 and parts[1].strip() else '新闻'
                        logger.info(f"开始获取新闻内容，关键词: {keyword}")
                        
                        # 创建新闻爬虫实例并获取新闻
                        crawler = NewsCrawler()
                        news_list = crawler.fetch_news()
                        
                        # 格式化新闻内容
                        news_content = crawler.format_news_response(news_list)
                        logger.info(f"成功获取 {len(news_list)} 条新闻")
                        
                        # 生成PDF文件
                        pdf_path = crawler.generate_news_pdf(news_list)
                        
                        # 首先广播用户输入的@新闻消息
                        self.broadcast_message({
                            'type': 'message',
                            'username': self.username,
                            'content': message_content,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        })
                        
                        # 广播新闻消息给所有用户
                        news_message_data = {
                            'type': 'news_pdf_message',  # 新增消息类型
                            'username': '系统',
                            'content': news_content,
                            'news_list': news_list,
                            'pdf_path': pdf_path if pdf_path else '',
                            'pdf_filename': os.path.basename(pdf_path) if pdf_path else '',
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        self.broadcast_message(news_message_data)
                        
                        # 保存新闻消息到数据库
                        db = get_db()
                        additional_data = {
                            'news_list': news_list,
                            'pdf_path': pdf_path
                        }
                        db.save_message('系统', 'news_pdf_message', news_content, additional_data)
                        
                        # 同时发送确认消息给命令发送者
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'news',
                            'content': message_content,
                            'message': '新闻查询完成并生成PDF',
                            'pdf_path': pdf_path,
                            'pdf_filename': os.path.basename(pdf_path) if pdf_path else ''
                        }))
                    except Exception as e:
                        logger.error(f"新闻查询失败: {str(e)}")
                        try:
                            # 广播用户输入的@新闻消息
                            self.broadcast_message({
                                'type': 'message',
                                'username': self.username,
                                'content': message_content,
                                'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                            })
                            
                            # 广播错误消息给所有用户
                            error_message_data = {
                                'type': 'system_message',
                                'username': '系统',
                                'content': '抱歉，暂时无法获取新闻内容，请稍后再试',
                                'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                            }
                            self.broadcast_message(error_message_data)
                            
                            # 发送错误消息给命令发送者
                            self.write_message(json.dumps({
                                'type': 'special_command',
                                'command': 'news',
                                'content': message_content,
                                'message': f'新闻获取失败: {str(e)}'
                            }))
                        except:
                            pass
                elif message_content.startswith('@张兵'):
                    # 实现AI对话功能，调用AI大模型API
                    try:
                        # 确保AI配置已加载
                        if not ChatHandler.ai_config:
                            ChatHandler.load_ai_config()
                        
                        # 配置OpenAI客户端（使用SiliconFlow API）
                        client = openai.OpenAI(
                            api_key=ChatHandler.ai_config.get("api_key", ""),
                            base_url=ChatHandler.ai_config.get("base_url", "https://api.siliconflow.cn/v1")
                        )
                        
                        # 提取用户的问题（去掉@张兵前缀）
                        user_question = message_content[3:].strip()
                        
                        # 如果用户没有输入具体问题，使用默认问题
                        if not user_question:
                            user_question = "你好，请和我聊天"
                        
                        # 检查特殊规则
                        if user_question.strip() == "那艺娜":
                            ai_reply = "砰砰砰"
                        elif "恋情" in user_question or "爱" in user_question or "喜欢" in user_question or "感情" in user_question:
                            ai_reply = "我从来没说过我爱娜娜"
                        elif "天气" in user_question or "气温" in user_question or "温度" in user_question:
                            # 模拟获取天气信息
                            # 在实际应用中，这里可以调用天气API或者读取本地天气文件
                            weather_options = [
                                "晴天，阳光明媚，气温25度，非常适合外出活动！",
                                "晴天，万里无云，气温30度，注意防晒！",
                                "雨天，正在下小雨，气温18度，出门记得带伞！",
                                "雨天，大雨倾盆，气温15度，建议待在室内！",
                                "阴天，天空灰蒙蒙的，气温22度，适合穿着薄外套！",
                                "多云，时有阳光透过云层，气温23度，天气不错！",
                                "小雪，雪花纷飞，气温-2度，注意保暖！",
                                "雾霾，空气质量较差，气温20度，外出建议戴口罩！"
                            ]
                            # 随机选择一个天气，但增加晴天和雨天的概率以测试背景切换功能
                            weights = [0.3, 0.2, 0.2, 0.1, 0.1, 0.05, 0.03, 0.02]  # 权重
                            ai_reply = random.choices(weather_options, weights=weights, k=1)[0]
                        else:
                            # 调用AI模型（使用SSE流式响应）
                            # 构建符合SiliconFlow API规范的请求
                            response = client.chat.completions.create(
                                model=ChatHandler.ai_config.get("model_name", "Qwen/Qwen2.5-7B-Instruct"),
                                messages=[
                                    {"role": "system", "content": ChatHandler.ai_config.get("system_prompt", "")},
                                    {"role": "user", "content": user_question}
                                ],
                                stream=True,  # 启用SSE流式响应
                                temperature=ChatHandler.ai_config.get("temperature", 0.7),
                                max_tokens=ChatHandler.ai_config.get("max_tokens", 1024)
                            )
                            
                            # 收集AI回复内容（SSE流式处理）
                            ai_reply = ""
                            for chunk in response:
                                try:
                                    if chunk.choices and len(chunk.choices) > 0:
                                        if chunk.choices[0].delta.content is not None:
                                            ai_reply += chunk.choices[0].delta.content
                                except Exception as chunk_error:
                                    print(f"处理SSE响应块时出错: {chunk_error}")
                                    continue
                        
                        # 首先广播用户输入的@张兵消息
                        self.broadcast_message({
                            'type': 'message',
                            'username': self.username,
                            'content': message_content,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        })
                        
                        # 如果AI没有返回回复，使用默认回复
                        if not ai_reply:
                            import random
                            ai_responses = ['砰砰砰', '娜艺那', '嗨娜娜，你卡了']
                            ai_reply = random.choice(ai_responses)
                        
                        # 广播AI回复消息给所有用户
                        ai_message_data = {
                            'type': 'ai_message',
                            'username': '张兵',
                            'content': ai_reply,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        self.broadcast_message(ai_message_data)
                        
                        # 保存AI回复到数据库
                        db = get_db()
                        db.save_message('张兵', 'ai_message', ai_reply)
                        
                        # 同时发送确认消息给命令发送者
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'ai',
                            'content': message_content,
                            'message': '张兵AI已回复'
                        }))
                    except Exception as e:
                        print(f"AI调用错误: {e}")
                        # 详细记录错误信息，便于调试
                        import traceback
                        traceback.print_exc()
                        # 发生错误时使用备用回复
                        import random
                        fallback_responses = ChatHandler.ai_config.get("fallback_responses", ['砰砰砰', '娜艺娜', '嗨娜娜，你卡了'])
                        ai_reply = random.choice(fallback_responses)
                        
                        # 广播备用AI回复
                        ai_message_data = {
                            'type': 'ai_message',
                            'username': '张兵',
                            'content': ai_reply,
                            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                        }
                        self.broadcast_message(ai_message_data)
                        
                        # 保存备用AI回复到数据库
                        db = get_db()
                        db.save_message('张兵', 'ai_message', ai_reply, {'is_fallback': True})
                        
                        # 通知用户发生了错误
                        self.write_message(json.dumps({
                            'type': 'special_command',
                            'command': 'ai',
                            'content': message_content,
                            'message': 'AI服务暂时不可用，使用备用回复'
                        }))
                else:
                    # 普通消息广播给所有用户
                    message_data = {
                        'type': 'message',
                        'username': self.username,
                        'content': message_content,
                        'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
                    }
                    self.broadcast_message(message_data)
                    
                    # 保存普通消息到数据库
                    try:
                        db = get_db()
                        db.save_message(self.username, 'message', message_content)
                    except Exception as e:
                        logger.error(f"保存消息到数据库失败: {e}")
                    
            # 处理文件上传请求
            elif data['type'] == 'file_request':
                # 简单实现，实际应用中需要处理文件存储和验证
                self.write_message(json.dumps({
                    'type': 'file_response',
                    'status': 'success',
                    'message': '文件上传功能将在后续版本实现'
                }))
        except Exception as e:
            logger.error(f"消息处理错误: {e}")
            import traceback
            traceback.print_exc()
    
    def on_close(self):
        """处理WebSocket连接关闭"""
        if self.id in ChatHandler.clients:
            del ChatHandler.clients[self.id]
            
        if self.username and self.id in ChatHandler.online_users:
            del ChatHandler.online_users[self.id]
            if self.id in ChatHandler.authenticated_users:
                del ChatHandler.authenticated_users[self.id]
            
            # 通知其他用户有用户离开
            leave_message = {
                'type': 'user_left',
                'username': self.username,
                'online_users': list(ChatHandler.online_users.values()),
                'message': f"{self.username} 离开了聊天室",
                'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
            }
            self.broadcast_message(leave_message)
            
            # 保存系统消息到数据库
            db = get_db()
            db.save_message('系统', 'system_message', f"{self.username} 离开了聊天室")
            
            # 更新用户状态为离线
            db.update_user_status(self.username, False)
            
            # 更新会话结束时间
            db.end_session(self.id)
        
        logger.info(f"连接关闭: {self.id}")
    
    @classmethod
    def broadcast_message(cls, message, exclude=None):
        for client_id, client in cls.clients.items():
            if client_id != exclude:
                try:
                    client.write_message(json.dumps(message))
                except Exception as e:
                    logger.error(f"广播消息给客户端 {client_id} 失败: {e}")

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class LoginHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("login.html")

class RegisterHandler(tornado.web.RequestHandler):
    def post(self):
        """处理用户注册请求"""
        try:
            data = json.loads(self.request.body)
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            # 验证输入
            if not username or not password:
                self.write({'success': False, 'message': '用户名和密码不能为空'})
                return
            
            if len(username) < 3 or len(username) > 20:
                self.write({'success': False, 'message': '用户名长度应在3-20个字符之间'})
                return
            
            if len(password) < 6:
                self.write({'success': False, 'message': '密码长度至少为6个字符'})
                return
            
            # 检查用户名是否包含禁止内容
            if '张兵' in username or 'zhangbing' in username.lower():
                self.write({'success': False, 'message': '用户名包含禁止内容'})
                return
            
            # 调用数据库注册用户
            db = get_db()
            if db.register_user(username, password):
                self.write({'success': True, 'message': '注册成功'})
            else:
                self.write({'success': False, 'message': '用户名已存在'})
        except Exception as e:
            logger.error(f"注册失败: {e}")
            self.write({'success': False, 'message': '注册失败，请稍后重试'})

class LoginHandler(tornado.web.RequestHandler):
    def post(self):
        """处理用户登录请求"""
        try:
            data = json.loads(self.request.body)
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            # 验证输入
            if not username or not password:
                self.write({'success': False, 'message': '用户名和密码不能为空'})
                return
            
            # 调用数据库验证用户
            db = get_db()
            login_success, message = db.login_user(username, password)
            if login_success:
                # 检查用户是否已在线
                if username in ChatHandler.online_users.values():
                    self.write({'success': False, 'message': '该用户已在线，请稍后再试'})
                    return
                
                self.write({'success': True, 'message': '登录成功'})
            else:
                self.write({'success': False, 'message': message})
        except Exception as e:
            logger.error(f"登录失败: {e}")
            self.write({'success': False, 'message': '登录失败，请稍后重试'})

class ConfigHandler(tornado.web.RequestHandler):
    def get(self):
        """返回服务器配置信息"""
        try:
            self.set_header('Content-Type', 'application/json')
            # 使用默认配置确保始终返回有效的JSON
            default_config = {
                "servers": [
                    {
                        "name": "默认服务器",
                        "host": "localhost",
                        "port": 8888
                    }
                ]
            }
            
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.write(json.dumps(config))
            except Exception as inner_e:
                # 记录错误但仍返回默认配置
                print(f"加载配置文件失败: {str(inner_e)}")
                self.write(json.dumps(default_config))
        except Exception as e:
            # 确保在任何情况下都返回有效的JSON
            self.set_status(500)
            self.write(json.dumps({
                "servers": [
                    {
                        "name": "默认服务器",
                        "host": "localhost",
                        "port": 8888
                    }
                ]
            }))

class HistoryHandler(tornado.web.RequestHandler):
    def get(self):
        """获取聊天历史记录"""
        try:
            # 获取查询参数
            limit = int(self.get_argument('limit', 50))
            page = int(self.get_argument('page', 0))
            search = self.get_argument('search', None)
            username = self.get_argument('username', None)
            
            # 计算offset
            offset = page * limit
            
            db = get_db()
            
            # 获取历史消息（支持搜索和用户过滤）
            messages = db.get_history_messages(limit, offset, search, username)
            
            # 格式化响应数据
            formatted_messages = []
            for msg in messages:
                formatted_msg = {
                    'username': msg.get('username', '未知'),
                    'type': msg['type'],
                    'content': msg['content'],
                    'timestamp': msg['timestamp']
                }
                
                # 添加额外数据
                if 'additional_data' in msg and msg['additional_data']:
                    try:
                        additional_data = json.loads(msg['additional_data']) if isinstance(msg['additional_data'], str) else msg['additional_data']
                        formatted_msg.update(additional_data)
                    except:
                        pass
                
                # 确保timestamp是字符串格式
                if isinstance(formatted_msg['timestamp'], str):
                    # 如果是完整的ISO格式，只提取时间部分
                    try:
                        if 'T' in formatted_msg['timestamp']:
                            dt = datetime.datetime.fromisoformat(formatted_msg['timestamp'].replace('Z', '+00:00'))
                            formatted_msg['timestamp'] = dt.strftime('%H:%M:%S')
                        elif len(formatted_msg['timestamp']) > 8:
                            # 假设是其他格式的完整时间戳，尝试转换
                            dt = datetime.datetime.fromisoformat(str(formatted_msg['timestamp']))
                            formatted_msg['timestamp'] = dt.strftime('%H:%M:%S')
                    except:
                        # 保持原样
                        pass
                else:
                    # 转换为时间字符串
                    try:
                        formatted_msg['timestamp'] = datetime.datetime.fromisoformat(str(formatted_msg['timestamp'])).strftime('%H:%M:%S')
                    except:
                        formatted_msg['timestamp'] = datetime.datetime.now().strftime('%H:%M:%S')
                
                formatted_messages.append(formatted_msg)
            
            self.set_header('Content-Type', 'application/json')
            # 返回格式与前端期望一致
            self.write(json.dumps({
                'messages': formatted_messages
            }))
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            self.set_status(500)
            self.write(json.dumps({'messages': []}))  # 出错时返回空列表

class StaticFileHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')

def make_app():
    # 加载AI配置
    ChatHandler.load_ai_config()
    
    # 初始化数据库
    db = get_db()
    logger.info("数据库初始化完成")
    
    # 创建PDF目录（如果不存在）
    pdf_dir = 'pdf_news'
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)
    
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "template_path": os.path.dirname(__file__),
        "debug": True
    }
    return tornado.web.Application([
        (r"/api/register", RegisterHandler),
        (r"/api/login", LoginHandler),
        (r"/config", ConfigHandler),
        (r"/api/history", HistoryHandler),
        (r"/chat", MainHandler),
        (r"/ws", ChatHandler),
        (r"/pdf_news/(.*)", tornado.web.StaticFileHandler, {'path': pdf_dir}),  # 添加PDF静态文件服务
        (r"/static/(.*)", tornado.web.StaticFileHandler, {'path': settings['static_path']}),
        (r"/(.*)", StaticFileHandler, {'path': '.', 'default_filename': 'login.html'}),
    ], **settings)

if __name__ == "__main__":
    try:
        # 确保静态文件目录存在
        if not os.path.exists('static'):
            os.makedirs('static')
        
        app = make_app()
        app.listen(8888)
        logger.info("服务器启动在 http://localhost:8888")
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        logger.info("服务器正在关闭...")
    finally:
        # 关闭数据库连接
        close_db()
        logger.info("服务器已关闭")