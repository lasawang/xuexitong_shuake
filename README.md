# 学习通视频完成工具

这是一个用于自动完成学习通视频任务的工具。

## 功能特点

- 自动完成视频观看任务
- 支持视频复习功能
- 图形界面操作
- 自动登录获取Cookies

## 打包说明

### 方法一：使用build.py脚本（推荐）

```bash
python build.py
```

### 方法二：使用PyInstaller直接打包

首先安装PyInstaller：
```bash
pip install PyInstaller
```

然后执行打包命令：
```bash
pyinstaller --onefile --windowed --name "学习通视频完成工具" --icon icon.ico main.py
```

### 方法三：使用setup.py（用于pip安装）

```bash
python setup.py sdist bdist_wheel
```

## 运行要求

- Python 3.8+
- 相关依赖包（已包含在requirements.txt中）

## 依赖安装

```bash
pip install -r requirements.txt
```

对于DrissionPage，需要额外安装：
```bash
pip install DrissionPage
```

## 使用说明

1. 运行程序
2. 点击"登录获取Cookies"按钮进行登录
3. 配置相关信息会自动保存
4. 点击"开始执行"完成视频任务或"开始复习"进行复习

## 注意事项

- 请合理使用此工具，避免频繁操作导致账号异常
- 使用前请确保网络连接正常
- 如遇到问题，请查看日志文件获取详细信息
