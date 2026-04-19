import pyautogui
import Window_readering
import time
import keyboard
import threading

# 在现有全局变量后添加
sunflower_planted_count = 0
current_plant_mode = "建立经济"  # 可选："建立经济"、"防御"、"扩展"
danger_alert = False  # 危险警告
danger_rows = set()  # 记录有危险僵尸的行


reader = Window_readering.PvZReader()
sun_plant_ok = False  # 向日葵是否已种植完毕

# 植物卡槽位置 (根据实际卡槽顺序调整)
PLANT_SLOTS = {
    '向日葵': 1,
    '豌豆射手': 2,
    '樱桃炸弹': 3,
    '坚果墙': 4,
    '双发射手': 5,
    '火爆辣椒': 6,
    '窝瓜': 7,
    '火炬树桩': 8,
    '南瓜头': 9,
    '高坚果': 10
}

plant_place_col = {    # 每行植物的距离，第一个植物在 70 距离处
    1 :70 , 2 :150, 3 :230, 4 :310,
    5 :390, 6 :470, 7 :550, 8 :630, 9 :7101
}

SLOT_COORDS = {
    1: (925, 410), 2: (974, 410), 3: (1031, 410), 4: (1084, 410), 5: (1129, 410),
    6: (1178, 410), 7: (1228, 410), 8: (1282, 410), 9: (1333, 410), 10: (1389, 410)
}
GRID_COORDS = {
    (row, col): {
        1: (890, 533), 2: (962, 529), 3: (1043, 527), 4: (1132, 531), 5: (1213, 532),
        6: (1290, 538), 7: (1368, 537), 8: (1447, 535), 9: (1526, 534),
        10: (880, 624), 11: (962, 622), 12: (1055, 621), 13: (1125, 624), 14: (1207, 627),
        15: (1286, 623), 16: (1364, 630), 17: (1446, 627), 18: (1531, 627),
        19: (888, 731), 20: (961, 726), 21: (1048, 724), 22: (1132, 724), 23: (1211, 728),
        24: (1284, 734), 25: (1372, 729), 26: (1446, 726), 27: (1535, 731),
        28: (885, 826), 29: (962, 822), 30: (1045, 822), 31: (1125, 822), 32: (1207, 822),
        33: (1285, 822), 34: (1363, 828), 35: (1445, 822), 36: (1532, 828),
        37: (880, 929), 38: (962, 925), 39: (1045, 925), 40: (1125, 925), 41: (1207, 925),
        42: (1285, 925), 43: (1361, 916), 44: (1445, 925), 45: (1532, 925)
    }[(row - 1) * 9 + col]
    for row in range(1, 6) for col in range(1, 10)
}

# 记录已种植的格子和植物名字（全局变量）
planted_grids = {}

def select_plant(plant_name):  # 选择植物卡片

    slot_num = PLANT_SLOTS.get(plant_name)
    if slot_num in SLOT_COORDS:
        pyautogui.click(SLOT_COORDS[slot_num])
        time.sleep(0.1)
        return True
    return False


def plant_at(row, col, plant_name):  # 在指定位置种植物

    if not check_plant_CD(plant_name):  # 先检查植物CD
        return False

    if (row, col) not in GRID_COORDS:
        return False

    if select_plant(plant_name):
        x, y = GRID_COORDS[(row, col)]
        pyautogui.moveTo(x, y)
        pyautogui.click()
        time.sleep(0.2)
        planted_grids[(row, col)] = plant_name
        print(f'{plant_name} 已在 ({row},{col}) 种植 ')
        return True
    return False


def check_plant_CD(plant_name):  # 检查植物CD, 返回True表示可以种植
    cd = reader.read_plant_CD()
    plant_numb = PLANT_SLOTS.get(plant_name)
    if plant_numb is None:
        return False
    if reader.read_dword(cd + ((plant_numb - 1) * 0x50)) == 0:
        return True
    return False


def get_zombie_data():  # 获取僵尸数据并存储到列表中

    zombie_list = []

    zombie_data = reader.get_zombie_data()

    current_zombie_numbers = zombie_data[0]['count'] if zombie_data else 0
    max_print = min(len(zombie_data), current_zombie_numbers) if current_zombie_numbers > 0 else 0

    if max_print > 0:
        entries_to_print = zombie_data[-max_print:]
        for unit in entries_to_print:
            if unit['x'] > 800:
                continue
            row = int(unit['y'] // 100) + 1
            zombie_info = {
                'sun': unit['sun'],
                'hp': unit['hp'] + unit['head_hat'],
                'count': unit['count'],
                'x': round(unit['x']),
                'y': row,
                'row': row
            }
            zombie_list.append(zombie_info)

    return zombie_list


def get_dangerous_zombies(zombie_list):
    """获取危险僵尸（接近房子的）"""
    dangerous = []
    for zombie in zombie_list:
        if zombie['x'] < 600:
            dangerous.append(zombie)
    return sorted(dangerous, key=lambda z: z['x'])

def get_weakest_row(zombie_list):
    """获取最危险的行（僵尸最多或最近的行）"""
    row_threat = defaultdict(lambda: {'count': 0, 'max_x': 0})

    for zombie in zombie_list:
        row = zombie['row']
        row_threat[row]['count'] += 1
        row_threat[row]['max_x'] = max(row_threat[row]['max_x'], zombie['x'])

    if not row_threat:
        return None

    # 优先选择有僵尸的行，按僵尸数量和进度排序
    threat_rows = [(row, data['count'], data['max_x'])
                   for row, data in row_threat.items()]
    if threat_rows:
        best_row = max(threat_rows, key=lambda x: (x[2], x[1]))[0]
        return best_row
    return None


def plant_sunflowers_logic():
    """种植向日葵的专用逻辑"""
    global sunflower_planted_count, sun_plant_ok

    if sunflower_planted_count >= 5:
        sun_plant_ok = True
        return False

    sun = reader.get_sunlight()
    if sun >= 50 and check_plant_CD('向日葵'):
        # 从第1列开始种植向日葵
        for row in range(1, 6):
            if (row, 1) not in planted_grids:
                if plant_at(row, 1, '向日葵'):
                    sunflower_planted_count += 1
                    if sunflower_planted_count >= 5:
                        sun_plant_ok = True
                    return  True
    return False


def assess_zombie_threat(zombie_list):
    """评估僵尸威胁级别和受影响的行"""
    global danger_alert, danger_rows  # danger_alert 危险警报 , danger_rows 危险行

    danger_rows.clear()
    danger_alert = False

    for zombie in zombie_list:
        if zombie['x'] < 700:  # 危险距离
            danger_alert = True
            danger_rows.add(zombie['row'])

    return danger_rows, danger_alert


def has_shooter_in_row(row):
    """检查指定行是否有射手类植物"""
    shooter_plants = ['豌豆射手', '双发射手']
    for col in range(1, 10):
        if (row, col) in planted_grids and planted_grids.get((row, col)) in shooter_plants:
            return True
    return False


def defense_logic(danger_rows, danger_alert):
    """防御决策逻辑 """
    if danger_alert:
        sun = reader.get_sunlight()
        zombie_list = get_zombie_data()

        for row in danger_rows:
            if (row, 2) not in planted_grids:
                if sun >= 100 and check_plant_CD('豌豆射手'):
                    if plant_at(row, 2, '豌豆射手'):
                        return True
            else:
                if has_shooter_in_row(row):

                    row_zombies = [z for z in zombie_list if z['row'] == row]

                    if (len(row_zombies) > 2
                            and sun >= 100
                            and check_plant_CD('豌豆射手')):

                        if (row, 3) not in planted_grids:
                            if plant_at(row, 3, '豌豆射手'):
                                return True

        return False
    return False


def expansion_logic(sun):
    """向日葵种完后的扩展建设逻辑"""

    # 阶段1：种植双发射手在豌豆射手前
    if sun >= 200 and check_plant_CD('双发射手'):
        # 寻找已种植豌豆射手的位置
        for row in range(1, 6):
            for col in range(2, 8):  # 检查第2-7列
                if (row, col) in planted_grids and planted_grids.get((row, col)) == '豌豆射手':  # 假设这是豌豆射手
                    # 在前方一格种植双发射手
                    target_col = col + 1
                    if (target_col >= 1
                            and (row, target_col) not in planted_grids
                            and check_plant_CD('双发射手')):
                        if plant_at(row, target_col, '双发射手'):
                            return True
    return False


class Selector:
    def __init__(self, children):
        self.children = children

    def run(self):
        for child in self.children:
            if child.run():
                return True
        return False

class Sequence:
    def __init__(self, children):
        self.children = children

    def run(self):
        for child in self.children:
            if not child.run():
                return False
        return True


class CheckZombies:
    def __init__(self, danger_rows, danger_alert):

        self.danger_rows = danger_rows
        self.danger_alert = danger_alert

    def run(self):
        if self.danger_alert:
            if defense_logic(self.danger_rows, self.danger_alert):
                return True
        return False

class plant_sunflowers:
    def __init__(self):
        self.sunflower_planted_count = 0
        self.sun_plant_ok = False

    def run(self):
        if plant_sunflowers_logic():
            return True
        return False


class extra_plant:
    def __init__(self, sun):
        self.sun = sun

    def run(self):
        if expansion_logic(self.sun):
            return True
        return False


def game_brain():
    global current_plant_mode, danger_alert
    zombie_list = get_zombie_data()
    danger_rows, danger_alert = assess_zombie_threat(zombie_list)
    sun = reader.get_sunlight()

    tree = Selector([
        Sequence([
            CheckZombies(danger_rows, danger_alert)
        ]),
        Sequence([
            plant_sunflowers()
        ]),
        Sequence([
            extra_plant(sun)
        ])
    ])
    tree.run()


is_running = False


def game_loop():
    """游戏主循环"""
    global is_running
    try:
        while is_running:
            game_brain()
            zombie_list = get_zombie_data()
            for zombie in zombie_list:
                print(f"阳光：{zombie['sun']}，僵尸：总 HP={zombie['hp']}，"
                      f"数量={zombie['count']}，"
                      f"x 位置={zombie['x']}，y 位置={zombie['row']}")
            print("-" * 25)
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("已退出")
    finally:
        reader.close()


def toggle_script():
    """切换脚本运行状态"""
    global is_running
    is_running = not is_running
    if is_running:
        print("\n[启动] 自动脚本已启动 - 按 F9 暂停")
        thread = threading.Thread(target=game_loop, daemon=True)
        thread.start()
    else:
        print("\n[暂停] 自动脚本已暂停 - 按 F9 继续")


if __name__ == "__main__":
    print("  F9  - 启动/暂停脚本")
    print("=" * 50)
    print("等待按键...")

    keyboard.add_hotkey('f9', toggle_script)
    keyboard.wait('f10')
    print("\n[退出] 程序已停止")
    reader.close()
