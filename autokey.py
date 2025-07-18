import random
import time
import threading
from flask import Flask, render_template, request, jsonify
from serial import Serial, SerialException
from ch9329 import keyboard

app = Flask(__name__, static_folder=".", template_folder=".")

# 全局变量
is_running = False
ser = None  # 串口对象
lock = threading.Lock()  # 用于串口访问的线程锁


@app.route('/')
def index():
    return render_template('index.html')  # 加载根目录下的 index.html 文件


def close_serial():
    """关闭串口"""
    global ser
    with lock:
        if ser and ser.is_open:
            ser.close()
            print("串口已关闭")


def press_keys(min_press_count, max_press_count, min_pause, max_pause, keys_and_delays):
    """循环按下前端传递的多个按键，并且在每次按键时根据传递的延迟进行等待"""
    global is_running, ser
    is_running = True

    try:
        while is_running:
            press_count = random.randint(min_press_count, max_press_count)
            print(f"本次将按键 {press_count} 次后暂停")

            for _ in range(press_count):
                if not is_running:
                    break
                #for item in keys_and_delays:
                #    if not is_running:
                #        break
                item = random.choice(keys_and_delays)  # 每次随机选一个按键及其延迟配置
                key = item['key']
                max_delay = item['delay']  # 获取每个按键的自定义延迟
                actual_delay = random.uniform(0, max_delay)  # 0到最大延迟随机
                keyboard.press_and_release(ser, key)
                print(f"按下 '{key}'，延迟: {actual_delay:.2f} 秒")
                time.sleep(actual_delay)
                
            if not is_running:
                break

            pause_duration = random.uniform(min_pause * 60, max_pause * 60)  # 转为秒
            print(f"暂停 {pause_duration / 60:.2f} 分钟")
            time.sleep(pause_duration)

            print("暂停结束，继续按键...")

    finally:
        # 停止时关闭串口，清理运行状态
        close_serial()
        is_running = False


@app.route('/send-key', methods=['POST'])
def send_key():
    data = request.get_json()
    key = data.get('key')

    try:
        with lock:
            ser.write(key.encode())
        return jsonify({"message": f"按键 '{key}' 已发送！"})
    except Exception as e:
        return jsonify({"message": f"发送失败: {str(e)}"}), 500


@app.route('/start-pressing', methods=['POST'])
def start_pressing():
    global is_running, ser
    if is_running:
        return jsonify({"message": "任务已在运行中，无法重复启动。"}), 400

    data = request.json
    com_port = data.get('comPort')
    baud_rate = data.get('baudRate')
    min_press_count = data.get('minPressCount')
    max_press_count = data.get('maxPressCount')
    min_pause = data.get('minPause')
    max_pause = data.get('maxPause')
    keys = data.get('keys')

    if not com_port or not baud_rate or not keys:
        return jsonify({"message": "串口配置和按键不能为空。"}), 400

    try:
        with lock:
            ser = Serial(com_port, baud_rate, timeout=0.05)
    except SerialException as e:
        return jsonify({"message": f"打开串口失败: {e}"}), 500

    # 开启线程执行按键任务
    thread = threading.Thread(target=press_keys, args=(min_press_count, max_press_count, min_pause, max_pause, keys))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "按键操作已启动。"})


@app.route('/stop-pressing', methods=['POST'])
def stop_pressing():
    global is_running
    if not is_running:
        return jsonify({"message": "任务未在运行中。"}), 400

    is_running = False
    close_serial()  # 关闭串口
    return jsonify({"message": "按键操作已停止。"})


@app.route('/status', methods=['GET'])
def get_status():
    global is_running
    return jsonify({"running": is_running})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
