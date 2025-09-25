import json
import re
import time
import random
from hashlib import md5
import requests
from lxml import etree
import sys
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar, 
                             QMessageBox, QGroupBox, QFormLayout, QStatusBar, QGridLayout,
                             QFileDialog, QDialog, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler('video_completion.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# 添加登录工作线程类
class LoginWorker(QThread):
    # 定义信号用于与主线程通信
    login_success = pyqtSignal(dict, dict, str, str, str, str)  # cookies, config, clazzid, userid, courseid, cpi
    login_failed = pyqtSignal(str)  # 错误信息
    log_message = pyqtSignal(str, str)  # 日志消息和颜色

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            from DrissionPage import ChromiumPage
            from urllib.parse import urlparse, parse_qs
            import json
            import time

            # 发送日志消息到主线程
            self.log_message.emit("[系统] 开始登录流程...", "#00ffff")

            # 创建浏览器实例
            cp = ChromiumPage(addr_or_opts='127.0.0.1:9222')

            # 访问登录页面
            cp.get('https://passport2.chaoxing.com/login')

            # 等待用户完成登录
            while True:
                if "用户登录" not in cp.title:
                    break
                time.sleep(1)

            # 访问课程页面
            cp.get('https://i.mooc.chaoxing.com/space/index')

            # 等待用户选择课程
            while True:
                current_url = cp.latest_tab.url
                if "https://i.mooc.chaoxing.com/space/index" not in current_url:
                    break
                if "courseid" in current_url and "clazzid" in current_url:
                    break
            print("当前 URL:", current_url)
            # 解析 URL 参数
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            params = {key: value[0] if len(value) == 1 else value
                      for key, value in query_params.items()}

            course_id = params.get("courseid", "")
            clazzid = params.get("clazzid", "")
            cpi = params.get("cpi", "")

            # 获取 cookies
            current_cookies = cp.cookies()

            def cookies_to_dict(cookies_list):
                return {cookie['name']: cookie['value'] for cookie in cookies_list}

            cookies_dict = cookies_to_dict(current_cookies)
            userid = cookies_dict.get("UID", "")

            # 准备数据
            cookies_data = {
                "cookies": cookies_dict,
                "config": {
                    "clazzid": clazzid,
                    "userid": userid,
                    "courseid": course_id,
                    "cpi": cpi
                }
            }

            config_data = {
                "clazzid": clazzid,
                "userid": userid,
                "courseid": course_id,
                "cpi": cpi
            }

            # 发送成功信号
            self.login_success.emit(cookies_dict, config_data, clazzid, userid, course_id, cpi)

        except Exception as e:
            # 发送失败信号
            self.login_failed.emit(str(e))


class VideoCompletionWorker(QThread):
    # 定义信号用于与主线程通信
    progress_updated = pyqtSignal(int)  # 进度更新信号
    log_message = pyqtSignal(str)       # 日志消息信号
    task_completed = pyqtSignal(bool)   # 任务完成信号

    def __init__(self, config_data, cookies):
        super().__init__()
        self.config_data = config_data
        self.is_review = False  # 标记是否为复习模式
        self.cookies = cookies
        # 构建 Referer URL
        courseid = config_data.get("courseid", "254542668")
        clazzid = config_data.get("clazzid", "127167075")
        cpi = config_data.get("cpi", "365638859")
        referer_url = f'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=1035900866&courseId={courseid}&clazzid={clazzid}&cpi={cpi}&enc=47c4a615eb350ed8af278d112e720bdc&mooc2=1&openc=9979b589d5dae5a253f3a74a58abd317'
        
        self.headers = {
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Referer': referer_url,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }

    def run(self):
        try:
            if self.is_review:
                self.log_message.emit("开始执行视频复习任务...")
                self.execute_video_review()
            else:
                self.log_message.emit("开始执行视频完成任务...")
                self.execute_video_completion()
            self.task_completed.emit(True)
        except Exception as e:
            self.log_message.emit(f"执行失败: {str(e)}")
            self.task_completed.emit(False)

    def execute_video_completion(self):
        # 从配置中获取参数
        clazzid = self.config_data.get('clazzid', '127167075')
        userid = self.config_data.get('userid', '312574292')
        courseid = self.config_data.get('courseid', '254542668')
        cpi = self.config_data.get('cpi', '365638859')
        
        self.log_message.emit(f"使用配置: 班级ID={clazzid}, 用户ID={userid}")

        params = {
            'courseId': courseid,
            'chapterId': '1035900866',
            'clazzid': clazzid,
            'cpi': cpi,
            'mooc2': '1',
            'isMicroCourse': 'false',
        }

        try:
            response = requests.get(
                'https://mooc1.chaoxing.com/mooc-ans/mycourse/studentstudycourselist',
                params=params,
                cookies=self.cookies,
                headers=self.headers,
            )
            response.raise_for_status()
            self.log_message.emit("✓ 成功获取课程列表")
        except requests.exceptions.RequestException as e:
            self.log_message.emit(f"✗ 获取课程列表失败")
            return

        try:
            tree = etree.HTML(response.text)
            self.log_message.emit("✓ 成功解析课程数据")
        except Exception as e:
            self.log_message.emit(f"✗ 解析课程数据失败")
            return

        # course_list 放所有未完成的任务
        course_list = []
        # video_course_list 未完成的视频课程
        video_course_list = []

        def process_course_item(item):
            """
            递归处理每个课程项目及其子项目
            """
            try:
                # 提取课程ID和标题
                items = item.xpath('.//span[contains(@class, "catalog_points_yi prevTips")]')

                for item_ in items:
                    course_id_list = item_.xpath('../@id')
                    if not course_id_list:
                        return

                    course_id = course_id_list[0].replace('cur', '')
                    title = ''.join(item_.xpath('../span//text()')).strip()
                    course_info = (course_id, title)
                    course_list.append(course_info)
                # if item.xpath('.//span[contains(@class, "icon_Completed")]'):
                #     print(f"跳过已完成的课程: {course_id} {title}")
                #     return
                # 将未完成的课程添加到 course_list



                # 递归处理子课程
                # for sub_item in item.xpath('./ul/li'):
                #     process_course_item(sub_item)
            except Exception as e:
                pass

        # 从根节点开始处理
        try:
            root_items = tree.xpath('//*[@style="padding-bottom:30px"]/li/div[2]/ul/li')
            self.log_message.emit(f"找到 {len(root_items)} 个章节项目")
            for i, item in enumerate(root_items):
                process_course_item(item)
                # 发送进度更新信号
                progress = int((i + 1) / len(root_items) * 20)
                self.progress_updated.emit(progress)
            self.log_message.emit(f"识别到 {len(course_list)} 个未完成任务")
        except Exception as e:
            self.log_message.emit(f"✗ 处理课程数据时出错")
            return

        # 处理未完成的课程
        total_courses = len(course_list)
        if total_courses == 0:
            self.log_message.emit("没有未完成的任务")
            return
            
        self.log_message.emit(f"开始处理 {total_courses} 个任务...")
        
        for idx, (course_id, title) in enumerate(course_list):
            self.log_message.emit(f"正在处理 ({idx+1}/{total_courses}): {title}")
            
            try:
                params = {
                    'clazzid': clazzid,
                    'courseid': courseid,
                    'knowledgeid': f'{course_id}',
                    'num': '0',
                    'ut': 's',
                    'cpi': cpi,
                    'v': '2025-0424-1038-3',
                    'mooc2': '1',
                    'isMicroCourse': 'false',
                    'editorPreview': '0',
                }

                response = requests.get('https://mooc1.chaoxing.com/mooc-ans/knowledge/cards', params=params, cookies=self.cookies,
                                        headers=self.headers)
                response.raise_for_status()

                if not response.text:
                    continue

                value_matches = re.findall(r'mArg = (.*);', response.text)
                if len(value_matches) < 2:
                    continue
                    
                value = value_matches[1]
                
                try:
                    video_info = json.loads(value)

                    if not video_info.get("attachments") or len(video_info["attachments"]) == 0:
                        continue

                    object_id = video_info["attachments"][0]["objectId"]
                    otherinfo = video_info["attachments"][0]["otherInfo"].split('&')[0]
                    course_name = video_info["attachments"][0]["otherInfo"].split('&')[1]
                    zongchang = video_info["attachments"][0]["attDuration"]
                    job_id = video_info["attachments"][0]["jobid"]
                    attDurationEnc = video_info["attachments"][0]["attDurationEnc"]
                    video_face = video_info["attachments"][0]["videoFaceCaptureEnc"]
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    continue
                    
                if video_info["attachments"][0]["property"]["type"]:
                    rand_time = random.uniform(27, 30)
                    self.log_message.emit(f"等待 {rand_time}s")
                    time.sleep(rand_time)

                    try:
                        params = {
                            'k': '886',
                            'flag': 'normal',
                            '_dc': str(int(time.time() * 1000)),
                        }

                        response = requests.get(
                            f'https://mooc1.chaoxing.com/ananas/status/{object_id}',
                            params=params,
                            cookies=self.cookies,
                            headers=self.headers,
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        video_url = data["http"]
                        video_response = requests.get(video_url, cookies=self.cookies, headers=self.headers)
                        video_response.raise_for_status()
                        
                        dtoken = data["dtoken"]
                        
                        # 生成加密字符串
                        jiami = md5(
                            f'[{clazzid}][{userid}][{job_id}][{object_id}][{zongchang}000][d_yHJ!$pdA~5][{zongchang}000][0_{zongchang}]'.encode()).hexdigest()

                        params = {
                            'clazzId': clazzid,
                            'playingTime': f"{zongchang}",
                            'duration': f"{zongchang}",
                            'clipTime': f'0_{zongchang}',
                            'objectId': object_id,
                            'otherInfo': otherinfo,
                            'courseId': course_name,
                            'jobid': job_id,
                            'userid': userid,
                            'isdrag': '0',
                            'view': 'pc',
                            'enc': jiami,
                            'rt': '0.9',
                            'videoFaceCaptureEnc': video_face,
                            'dtype': 'Video',
                            '_t': str(int(time.time() * 1000)),
                            'attDuration': f"{zongchang}",
                            'attDurationEnc': attDurationEnc,
                        }

                        response = requests.get(
                            f'https://mooc1.chaoxing.com/mooc-ans/multimedia/log/a/{cpi}/{dtoken}',
                            params=params,
                            cookies=self.cookies,
                            headers=self.headers,
                        )
                        response.raise_for_status()
                        if response.json ()['isPassed']:
                            self.log_message.emit(f"✓ 任务已通过: {title} {response.json ()['isPassed']}")
                        else :
                            self.log_message.emit(f"✗ 任务失败: {title} {response.json ()['isPassed']}")
                        
                        # 更新进度
                        progress = 20 + int((idx + 1) / total_courses * 80)
                        self.progress_updated.emit(progress)
                        
                        # 如果不是最后一个课程，等待30秒
                        if idx < total_courses - 1:
                            rand_time = random.randint(27, 30)
                            self.log_message.emit(f"等待 {rand_time}s")
                            for i in range(rand_time):
                                time.sleep(1)
                                # 每秒更新一次进度
                                self.progress_updated.emit(20 + int((idx + 1) / total_courses * 80) + int(i / 60 * 10))
                    except requests.exceptions.RequestException as e:
                        self.log_message.emit(f"✗ 处理失败: {title}")
                    except KeyError as e:
                        self.log_message.emit(f"✗ 处理失败: {title}")
                    except Exception as e:
                        self.log_message.emit(f"✗ 处理失败: {title}")
                else:
                    self.log_message.emit(f"✓ 跳过非视频任务: {title}")
            except Exception as e:
                self.log_message.emit(f"✗ 处理失败: {title}")
                
            # 更新进度
            progress = 20 + int((idx + 1) / total_courses * 80)
            self.progress_updated.emit(progress)

        if self.is_review:
            self.log_message.emit(f"复习任务完成! 成功复习 {total_courses} 个任务")
        else:
            self.log_message.emit(f"任务完成! 成功处理 {total_courses} 个任务")

    def execute_video_review(self):
        # 从配置中获取参数
        clazzid = self.config_data.get('clazzid', '127167075')
        userid = self.config_data.get('userid', '312574292')
        courseid = self.config_data.get('courseid', '254542668')
        cpi = self.config_data.get('cpi', '365638859')

        self.log_message.emit(f"使用配置进行复习: 班级ID={clazzid}, 用户ID={userid}")

        params = {
            'courseId': courseid,
            'chapterId': '1035900866',
            'clazzid': clazzid,
            'cpi': cpi,
            'mooc2': '1',
            'isMicroCourse': 'false',
        }

        try:
            response = requests.get(
                'https://mooc1.chaoxing.com/mooc-ans/mycourse/studentstudycourselist',
                params=params,
                cookies=self.cookies,
                headers=self.headers,
            )
            response.raise_for_status()
            self.log_message.emit("✓ 成功获取课程列表")
        except requests.exceptions.RequestException as e:
            self.log_message.emit(f"✗ 获取课程列表失败: {str(e)}")
            return

        try:
            tree = etree.HTML(response.text)
            self.log_message.emit("✓ 成功解析课程数据")
        except Exception as e:
            self.log_message.emit(f"✗ 解析课程数据失败")
            return

        # course_list 放所有任务（包括已完成的，用于复习）
        course_list = []

        def process_course_item(item):
            """
            递归处理每个课程项目及其子项目
            """
            try:
                # 提取课程ID和标题
                items = item.xpath('.//span[contains(@class, "catalog_points_yi prevTips")]')

                for item_ in items:
                    course_id_list = item_.xpath('../@id')
                    if not course_id_list:
                        return

                    course_id = course_id_list[0].replace('cur', '')
                    title = ''.join(item_.xpath('../span//text()')).strip()
                    course_info = (course_id, title)
                    course_list.append(course_info)

                # 递归处理子课程
                for sub_item in item.xpath('./ul/li'):
                    process_course_item(sub_item)
            except Exception as e:
                pass

        # 从根节点开始处理
        try:
            root_items = tree.xpath('//*[@style="padding-bottom:30px"]/li/div[2]/ul/li')
            self.log_message.emit(f"找到 {len(root_items)} 个章节项目")
            for i, item in enumerate(root_items):
                process_course_item(item)
                # 发送进度更新信号
                progress = int((i + 1) / len(root_items) * 20)
                self.progress_updated.emit(progress)
            self.log_message.emit(f"识别到 {len(course_list)} 个任务（用于复习）")
        except Exception as e:
            self.log_message.emit(f"✗ 处理课程数据时出错")
            return

        # 处理所有课程（包括已完成的）
        total_courses = len(course_list)
        if total_courses == 0:
            self.log_message.emit("没有可复习的任务")
            return

        self.log_message.emit(f"开始复习 {total_courses} 个任务...")
        # 对于复习模式，我们重新观看视频
        for idx, (course_id, title) in enumerate(course_list):
            self.log_message.emit(f"正在复习 ({idx+1}/{total_courses}): {title}")

            try:
                params = {
                    'clazzid': clazzid,
                    'courseid': courseid,
                    'knowledgeid': f'{course_id}',
                    'num': '0',
                    'ut': 's',
                    'cpi': cpi,
                    'v': '2025-0424-1038-3',
                    'mooc2': '1',
                    'isMicroCourse': 'false',
                    'editorPreview': '0',
                }

                response = requests.get('https://mooc1.chaoxing.com/mooc-ans/knowledge/cards', params=params, cookies=self.cookies,
                                        headers=self.headers)
                response.raise_for_status()

                if not response.text:
                    continue

                value_matches = re.findall(r'mArg = (.*);', response.text)
                if len(value_matches) < 2:
                    continue

                value = value_matches[1]

                try:
                    video_info = json.loads(value)

                    if not video_info.get("attachments") or len(video_info["attachments"]) == 0:
                        continue

                    object_id = video_info["attachments"][0]["objectId"]
                    otherinfo = video_info["attachments"][0]["otherInfo"].split('&')[0]
                    course_name = video_info["attachments"][0]["otherInfo"].split('&')[1]
                    zongchang = video_info["attachments"][0]["attDuration"]
                    job_id = video_info["attachments"][0]["jobid"]
                    attDurationEnc = video_info["attachments"][0]["attDurationEnc"]
                    video_face = video_info["attachments"][0]["videoFaceCaptureEnc"]
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    continue

                if video_info["attachments"][0]["property"]["type"]:
                    try:
                        params = {
                            'k': '886',
                            'flag': 'normal',
                            '_dc': str(int(time.time() * 1000)),
                        }

                        response = requests.get(
                            f'https://mooc1.chaoxing.com/ananas/status/{object_id}',
                            params=params,
                            cookies=self.cookies,
                            headers=self.headers,
                        )
                        response.raise_for_status()
                        data = response.json()

                        video_url = data["http"]
                        video_response = requests.get(video_url, cookies=self.cookies, headers=self.headers)
                        video_response.raise_for_status()

                        dtoken = data["dtoken"]

                        # 生成加密字符串
                        jiami = md5(
                            f'[{clazzid}][{userid}][{job_id}][{object_id}][{zongchang}000][d_yHJ!$pdA~5][{zongchang}000][0_{zongchang}]'.encode()).hexdigest()

                        params = {
                            'clazzId': clazzid,
                            'playingTime': f"{zongchang}",
                            'duration': f"{zongchang}",
                            'clipTime': f'0_{zongchang}',
                            'objectId': object_id,
                            'otherInfo': otherinfo,
                            'courseId': course_name,
                            'jobid': job_id,
                            'userid': userid,
                            'isdrag': '0',
                            'view': 'pc',
                            'enc': jiami,
                            'rt': '0.9',
                            'videoFaceCaptureEnc': video_face,
                            'dtype': 'Video',
                            '_t': str(int(time.time() * 1000)),
                            'attDuration': f"{zongchang}",
                            'attDurationEnc': attDurationEnc,
                        }

                        response = requests.get(
                            f'https://mooc1.chaoxing.com/mooc-ans/multimedia/log/a/{cpi}/{dtoken}',
                            params=params,
                            cookies=self.cookies,
                            headers=self.headers,
                        )
                        response.raise_for_status()
                        if response.json()['isPassed']:
                            self.log_message.emit(f"✓ 复习完成: {title} {response.json()['isPassed']}")
                        else:
                            self.log_message.emit(f"✗ 复习失败: {title} {response.json()['isPassed']}")

                        # 更新进度
                        progress = 20 + int((idx + 1) / total_courses * 80)
                        self.progress_updated.emit(progress)

                        # 如果不是最后一个课程，等待30秒
                        if idx < total_courses - 1:
                            self.log_message.emit(f"等待30秒后继续...")
                            for i in range(30):
                                time.sleep(1)
                                # 每秒更新一次进度
                                self.progress_updated.emit(20 + int((idx + 1) / total_courses * 80) + int(i / 60 * 10))
                    except requests.exceptions.RequestException as e:
                        self.log_message.emit(f"✗ 复习失败: {title}")
                    except KeyError as e:
                        self.log_message.emit(f"✗ 复习失败: {title}")
                    except Exception as e:
                        self.log_message.emit(f"✗ 复习失败: {title}")
                else:
                    self.log_message.emit(f"✓ 跳过非视频任务: {title}")
            except Exception as e:
                self.log_message.emit(f"✗ 复习失败: {title}")

            # 更新进度
            progress = 20 + int((idx + 1) / total_courses * 80)
            self.progress_updated.emit(progress)

        self.log_message.emit(f"复习任务完成! 成功复习 {total_courses} 个任务")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学习通视频完成工具")
        self.setGeometry(100, 100, 900, 700)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a0a0a, stop:1 #1a1a2e);
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #00b4d8;
                border-radius: 10px;
                margin-top: 1ex;
                background-color: rgba(25, 25, 35, 0.8);
                padding: 10px;
                color: #00f5ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #00f5ff;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0077b6, stop:1 #00b4d8);
                border: 1px solid #00b4d8;
                color: white;
                padding: 12px 24px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 8px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0096c7, stop:1 #48cae4);
                border: 1px solid #48cae4;
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #006d96, stop:1 #0086a8);
            }
            QPushButton:disabled {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #555, stop:1 #777);
                border: 1px solid #666;
                color: #aaa;
            }
            QPushButton#stopButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d90429, stop:1 #ff2a6d);
                border: 1px solid #ff2a6d;
            }
            QPushButton#stopButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2a6d, stop:1 #ff6b9d);
                border: 1px solid #ff6b9d;
            }
            QPushButton#reviewButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6a040f, stop:1 #d00000);
                border: 1px solid #d00000;
            }
            QPushButton#reviewButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9d0208, stop:1 #dc2f02);
                border: 1px solid #dc2f02;
            }
            QLineEdit {
                padding: 12px;
                border: 2px solid #00b4d8;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                color: #e0f7ff;
                background-color: rgba(0, 0, 0, 0.3);
            }
            QLineEdit:focus {
                border: 2px solid #48cae4;
                background-color: rgba(0, 0, 0, 0.5);
                selection-background-color: #0077b6;
            }
            QTextEdit {
                border: 2px solid #0077b6;
                border-radius: 8px;
                background-color: rgba(0, 0, 0, 0.7);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                color: #00ff00;
                selection-background-color: #0077b6;
            }
            QProgressBar {
                border: 2px solid #0077b6;
                border-radius: 10px;
                text-align: center;
                height: 25px;
                background-color: rgba(0, 0, 0, 0.5);
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #0077b6);
                border-radius: 8px;
            }
            QLabel {
                color: #caf0f8;
                font-size: 16px;
                font-weight: bold;
            }
            QStatusBar {
                background-color: rgba(0, 0, 0, 0.8);
                color: #caf0f8;
                font-size: 14px;
                border-top: 1px solid #0077b6;
            }
            QMenuBar {
                background-color: rgba(10, 10, 20, 0.9);
                color: #caf0f8;
                font-size: 16px;
            }
            QMenuBar::item {
                background: transparent;
            }
            QMenuBar::item:selected {
                background: rgba(0, 180, 216, 0.3);
            }
            QMenuBar::item:pressed {
                background: rgba(0, 180, 216, 0.5);
            }
        """)
        
        # 创建菜单栏
        menubar = self.menuBar()
        file_menu = menubar.addMenu('文件')
        login_menu = menubar.addMenu('登录')
        help_menu = menubar.addMenu('帮助')
        
        # 添加菜单项
        load_action = file_menu.addAction('加载配置')
        save_action = file_menu.addAction('保存配置')
        exit_action = file_menu.addAction('退出')
        login_action = login_menu.addAction('登录获取 Cookies')
        about_action = help_menu.addAction('关于')
        
        load_action.triggered.connect(self.load_config)
        save_action.triggered.connect(self.save_config)
        exit_action.triggered.connect(self.close)
        login_action.triggered.connect(self.start_login)
        about_action.triggered.connect(lambda: QMessageBox.about(self, "关于", "学习通视频完成工具 v1.1\n支持视频完成、复习和自动登录功能"))
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        central_widget.setLayout(main_layout)
        
        # 创建标题
        title_label = QLabel("学习通视频完成工具")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #00f5ff;
            margin: 15px;
            padding: 10px;
            background-color: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            border: 2px solid #00b4d8;
        """)
        main_layout.addWidget(title_label)
        
        # 创建配置组
        config_group = QGroupBox("配置信息")
        config_layout = QGridLayout()
        config_layout.setSpacing(15)
        config_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标签和输入框
        clazzid_label = QLabel("班级ID:")
        clazzid_label.setStyleSheet("font-weight: bold; font-size: 16px; color:#00f5ff;")
        self.clazzid_input = QLineEdit()
        self.clazzid_input.setPlaceholderText("请输入班级ID")
        
        userid_label = QLabel("用户ID:")
        userid_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #00f5ff;")
        self.userid_input = QLineEdit()
        self.userid_input.setPlaceholderText("请输入用户ID")
        
        courseid_label = QLabel("课程ID:")
        courseid_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #00f5ff;")
        self.courseid_input = QLineEdit()
        self.courseid_input.setPlaceholderText("请输入课程ID")
        
        cpi_label = QLabel("CPI:")
        cpi_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #00f5ff;")
        self.cpi_input = QLineEdit()
        self.cpi_input.setPlaceholderText("请输入CPI")
        
        # 添加到布局
        config_layout.addWidget(clazzid_label, 0, 0)
        config_layout.addWidget(self.clazzid_input, 0, 1)
        config_layout.addWidget(userid_label, 0, 2)
        config_layout.addWidget(self.userid_input, 0, 3)
        config_layout.addWidget(courseid_label, 1, 0)
        config_layout.addWidget(self.courseid_input, 1, 1)
        config_layout.addWidget(cpi_label, 1, 2)
        config_layout.addWidget(self.cpi_input, 1, 3)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.load_config_btn = QPushButton("加载配置")
        self.save_config_btn = QPushButton("保存配置")
        self.login_btn = QPushButton("登录获取 Cookies")
        self.start_btn = QPushButton("开始执行")
        self.review_btn = QPushButton("开始复习")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("stopButton")
        
        # 增大按钮字体
        button_style = "font-size: 16px; padding: 12px 24px;"
        self.load_config_btn.setStyleSheet(button_style)
        self.save_config_btn.setStyleSheet(button_style)
        self.login_btn.setStyleSheet(button_style)
        self.start_btn.setStyleSheet(button_style)
        self.review_btn.setStyleSheet(button_style)
        self.stop_btn.setStyleSheet(button_style)
        
        self.load_config_btn.clicked.connect(self.load_config)
        self.save_config_btn.clicked.connect(self.save_config)
        self.login_btn.clicked.connect(self.start_login)
        self.start_btn.clicked.connect(self.start_execution)
        self.review_btn.clicked.connect(self.start_review)
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setEnabled(False)
        
        button_layout.addWidget(self.load_config_btn)
        button_layout.addWidget(self.save_config_btn)
        button_layout.addWidget(self.login_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.review_btn)
        button_layout.addWidget(self.stop_btn)
        main_layout.addLayout(button_layout)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(35)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 8px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: #333333;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        self.progress_bar.setFormat("准备就绪...")
        main_layout.addWidget(self.progress_bar)
        
        # 创建日志显示区域标题
        log_title = QLabel("运行日志:")
        log_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #00f5ff;
            margin-top: 10px;
        """)
        main_layout.addWidget(log_title)
        
        # 创建日志显示区域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(300)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #00ff00;
                font-family: Consolas, Monaco, 'Courier New', monospace;
                font-size: 14px;
                border: 2px solid #333333;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        # 添加一些初始日志
        self.log_display.append("[系统] 学习通视频完成工具已启动")
        self.log_display.append("[提示] 请加载配置或输入配置信息后点击开始执行")
        main_layout.addWidget(self.log_display)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #eeeeee;
                color: #333333;
                font-size: 14px;
                border-top: 1px solid #cccccc;
            }
        """)
        self.status_bar.showMessage("就绪 - 请加载配置")
        
        # 初始化工作线程
        self.worker = None
        self.login_worker = None  # 登录工作线程
        
        # 检查是否有 cookies.json 文件
        self.cookies_exists = False
        self.check_cookies_file()
        
        # 加载默认配置
        self.load_config()

    def check_cookies_file(self):
        """检查 cookies.json 文件是否存在"""
        import os
        if os.path.exists('cookies.json'):
            self.cookies_exists = True

    def handle_login_success(self, cookies, config_data, clazzid, userid, courseid, cpi):
        """处理登录成功的回调"""
        try:
            import json
            
            # 保存到 cookies.json
            cookies_data = {
                "cookies": cookies,
                "config": config_data
            }
            with open("cookies.json", "w", encoding="utf-8") as f:
                json.dump(cookies_data, f, ensure_ascii=False, indent=4)
            
            # 同时更新 config.json
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            
            # 更新界面中的配置
            self.clazzid_input.setText(clazzid)
            self.userid_input.setText(userid)
            self.courseid_input.setText(courseid)
            self.cpi_input.setText(cpi)
            
            self.log_message("[系统] 登录成功，配置已保存", "#00ff00")
            self.status_bar.showMessage("登录成功，配置已保存")
            self.cookies_exists = True
            
        except Exception as e:
            self.log_message(f"[错误] 保存登录信息失败: {str(e)}", "#ff0000")
            self.status_bar.showMessage("登录信息保存失败")

    def handle_login_failed(self, error_msg):
        """处理登录失败的回调"""
        self.log_message(f"[错误] 登录失败: {error_msg}", "#ff0000")
        self.status_bar.showMessage("登录失败")

    def handle_login_log(self, message, color):
        """处理登录过程中的日志消息"""
        self.log_message(message, color)

    def start_login(self):
        """启动登录流程"""
        # 检查是否安装了 DrissionPage
        try:
            from DrissionPage import ChromiumPage
        except ImportError:
            reply = QMessageBox.question(self, "依赖缺失", 
                                       "需要安装 DrissionPage 库才能使用登录功能。\n是否现在安装？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "DrissionPage"])
                    QMessageBox.information(self, "安装完成", "DrissionPage 安装成功，请重新启动程序。")
                    return
                except subprocess.CalledProcessError:
                    QMessageBox.warning(self, "安装失败", "DrissionPage 安装失败，请手动安装后重试。")
                    return
            else:
                return
        
        # 创建并启动登录工作线程
        self.login_worker = LoginWorker()
        self.login_worker.login_success.connect(self.handle_login_success)
        self.login_worker.login_failed.connect(self.handle_login_failed)
        self.login_worker.log_message.connect(self.handle_login_log)
        self.login_worker.start()

    def start_review(self):
        # 获取配置数据
        config_data = {
            'clazzid': self.clazzid_input.text(),
            'userid': self.userid_input.text(),
            'courseid': self.courseid_input.text(),
            'cpi': self.cpi_input.text()
        }
        
        # 验证配置
        if not all(config_data.values()):
            QMessageBox.warning(self, "警告", "请填写所有配置项")
            return
        
        # 验证 cookies
        cookies = self.load_cookies()
        if not cookies:
            reply = QMessageBox.question(self, "缺少 Cookies", 
                                       "未找到有效的 cookies，请先登录。\n是否现在登录？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.start_login()
                return
            else:
                return
        
        # 测试 cookies 是否有效
        if not self.test_cookies_validity(cookies):
            reply = QMessageBox.question(self, "Cookies 无效", 
                                       "当前 cookies 已失效，请重新登录。\n是否现在登录？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.start_login()
                return
            else:
                return
        
        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.review_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("复习任务执行中...")
        
        # 清空日志
        self.log_display.clear()
        
        self.log_message("[系统] 开始执行复习任务...", "#00ffff")
        self.status_bar.showMessage("正在执行复习任务...")
        
        # 创建并启动工作线程
        self.worker = VideoCompletionWorker(config_data, cookies)
        self.worker.log_message.connect(self.log_message)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.task_completed.connect(self.on_task_completed)
        self.worker.is_review = True  # 标记为复习模式
        self.worker.start()

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.clazzid_input.setText(config_data.get('clazzid', ''))
            self.userid_input.setText(config_data.get('userid', ''))
            self.courseid_input.setText(config_data.get('courseid', ''))
            self.cpi_input.setText(config_data.get('cpi', ''))
            
            # 检查 cookies 是否存在且有效
            cookies = self.load_cookies()
            if cookies and self.test_cookies_validity(cookies):
                self.log_message("[系统] 配置加载成功，cookies 有效", "#00ff00")
                self.status_bar.showMessage("配置已加载，cookies 有效")
                self.progress_bar.setFormat("配置已加载，cookies 有效")
            else:
                self.log_message("[警告] 配置加载成功，但 cookies 无效或不存在", "#ffff00")
                self.status_bar.showMessage("配置已加载，cookies 无效或不存在")
                self.progress_bar.setFormat("配置已加载，cookies 无效或不存在")
        except FileNotFoundError:
            self.log_message("[警告] 未找到配置文件，使用默认值", "#ffff00")
            self.status_bar.showMessage("未找到配置文件")
            self.progress_bar.setFormat("未找到配置文件")
        except Exception as e:
            self.log_message(f"[错误] 加载配置失败: {str(e)}", "#ff0000")
            self.status_bar.showMessage("配置加载失败")
            self.progress_bar.setFormat("配置加载失败")

    def save_config(self):
        try:
            config_data = {
                'clazzid': self.clazzid_input.text(),
                'userid': self.userid_input.text(),
                'courseid': self.courseid_input.text(),
                'cpi': self.cpi_input.text()
            }
            
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            
            self.log_message("[系统] 配置保存成功", "#00ff00")
            self.status_bar.showMessage("配置已保存")
            self.progress_bar.setFormat("配置已保存")
            QMessageBox.information(self, "成功", "配置保存成功")
        except Exception as e:
            self.log_message(f"[错误] 保存配置失败: {str(e)}", "#ff0000")
            self.status_bar.showMessage("配置保存失败")
            self.progress_bar.setFormat("配置保存失败")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")

    def start_execution(self):
        # 获取配置数据
        config_data = {
            'clazzid': self.clazzid_input.text(),
            'userid': self.userid_input.text(),
            'courseid': self.courseid_input.text(),
            'cpi': self.cpi_input.text()
        }
        
        # 验证配置
        if not all(config_data.values()):
            QMessageBox.warning(self, "警告", "请填写所有配置项")
            return
        
        # 验证 cookies
        cookies = self.load_cookies()
        if not cookies:
            reply = QMessageBox.question(self, "缺少 Cookies", 
                                       "未找到有效的 cookies，请先登录。\n是否现在登录？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.start_login()
                return
            else:
                return
        
        # 测试 cookies 是否有效
        if not self.test_cookies_validity(cookies):
            reply = QMessageBox.question(self, "Cookies 无效", 
                                       "当前 cookies 已失效，请重新登录。\n是否现在登录？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.start_login()
                return
            else:
                return
        
        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("任务执行中...")
        
        # 清空日志
        self.log_display.clear()
        
        self.log_message("[系统] 开始执行任务...", "#00ff00")
        self.status_bar.showMessage("正在执行任务...")
        
        # 创建并启动工作线程
        self.worker = VideoCompletionWorker(config_data, cookies)
        self.worker.log_message.connect(self.log_message)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.task_completed.connect(self.on_task_completed)
        self.worker.start()

    def load_cookies(self):
        """从 cookies.json 加载 cookies"""
        import os
        import json
        
        if os.path.exists('cookies.json'):
            try:
                with open('cookies.json', 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                    return cookies_data.get('cookies', {})
            except Exception as e:
                self.log_message(f"[错误] 读取 cookies 失败: {str(e)}", "#ff0000")
                return {}
        else:
            return {}

    def test_cookies_validity(self, cookies):
        """测试 cookies 是否有效"""
        try:
            # 尝试访问一个需要登录的页面来测试 cookies
            response = requests.get(
                'https://mooc1.chaoxing.com/api/work/stuwork-list',
                cookies=cookies,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            # 如果响应中包含登录相关的错误信息，则 cookies 无效
            if '请先登录' in response.text or response.status_code == 403 or response.status_code == 302:
                return False
            return True
        except Exception as e:
            self.log_message(f"[警告] 测试 cookies 时出错: {str(e)}", "#ffff00")
            return False

    def stop_execution(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.log_message("[系统] 任务已停止", "#ffff00")
            self.status_bar.showMessage("任务已停止")
            self.progress_bar.setFormat("任务已停止")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def log_message(self, message, color="#00ff00"):
        # 在主线程中更新UI
        timestamp = time.strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        
        # 创建一个文本字符格式
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        text_format.setFontPointSize(14)  # 增大字体
        
        # 获取当前光标位置并插入带颜色的文本
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(formatted_message + "\n", text_format)
        
        # 滚动到底部
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        
        # 同时记录到文件
        logger.info(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        if value == 0:
            self.progress_bar.setFormat("准备就绪...")
        elif value == 100:
            self.progress_bar.setFormat("任务完成!")
        else:
            self.progress_bar.setFormat(f"执行中... {value}%")

    def on_task_completed(self, success):
        self.start_btn.setEnabled(True)
        self.review_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if success:
            if hasattr(self.worker, 'is_review') and self.worker.is_review:
                self.log_message("[系统] 复习任务执行完成!", "#00ffff")
                self.status_bar.showMessage("复习任务已完成")
                self.progress_bar.setFormat("复习任务已完成")
                QMessageBox.information(self, "完成", "复习任务执行完成!")
            else:
                self.log_message("[系统] 任务执行完成!", "#00ff00")
                self.status_bar.showMessage("任务已完成")
                self.progress_bar.setFormat("任务已完成")
                QMessageBox.information(self, "完成", "任务执行完成!")
        else:
            self.log_message("[错误] 任务执行失败!", "#ff0000")
            self.status_bar.showMessage("任务执行失败")
            self.progress_bar.setFormat("任务执行失败")
            QMessageBox.warning(self, "错误", "任务执行失败!")


def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序字体
    font = QFont("Microsoft YaHei", 12)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()