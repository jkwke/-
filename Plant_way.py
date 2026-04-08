import pyautogui
import Window_readering
import time


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
        return

    sun = reader.get_sunlight()
    if sun >= 50 and check_plant_CD('向日葵'):
        # 从第1列开始种植向日葵
        for row in range(1, 6):
            if (row, 1) not in planted_grids:
                if plant_at(row, 1, '向日葵'):
                    sunflower_planted_count += 1
                    if sunflower_planted_count >= 5:
                        sun_plant_ok = True
                    return


def assess_zombie_threat(zombie_list):
    """评估僵尸威胁级别和受影响的行"""
    global danger_alert, danger_rows  # danger_alert 危险警报 , danger_rows 危险行

    danger_rows.clear()
    danger_alert = False

    for zombie in zombie_list:
        # 僵尸距离阈值判断
        if zombie['x'] < 800:  # 中等距离，开始预警
            danger_rows.add(zombie['row'])

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
    """防御决策逻辑"""
    sun = reader.get_sunlight()

    # 有危险僵尸时的优先级
    if danger_alert:
        for row in danger_rows:
            # 如果有向日葵CD，先尝试种植豌豆射手
            if sun >= 100 and check_plant_CD('豌豆射手'):
                # 只在第二列种植豌豆射手
                if (row, 2) not in planted_grids:
                    if plant_at(row, 2, '豌豆射手'):
                        return True

            # 如果该行已经有射手，检查是否需要补充
            if has_shooter_in_row(row):
                # 统计该行僵尸数量
                row_zombies = [z for z in get_zombie_data() if z['row'] == row]
                if (len(row_zombies) > 2
                        and sun >= 100
                        and check_plant_CD('豌豆射手')
                        and not check_plant_CD("双发射手")):
                    # 在射手前种植豌豆射手
                    if (row, 3) not in planted_grids:
                        if plant_at(row, 3, '豌豆射手'):
                            return True

    return False


def expansion_logic():
    """向日葵种完后的扩展建设逻辑"""
    sun = reader.get_sunlight()

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

    # 阶段2：双发射手种完一列后，在前面种坚果
    # 这里需要您添加检查双发射手列是否完成的逻辑

    return False


def game_brain():
    global current_plant_mode, danger_alert

    # 获取游戏状态
    zombie_list = get_zombie_data()
    danger_rows, danger_alert = assess_zombie_threat(zombie_list)
    sun = reader.get_sunlight()

    # 决策优先级
    if danger_alert:
        # 优先级1：处理紧急威胁
        if defense_logic(danger_rows, danger_alert):
            return

    if not sun_plant_ok:
        # 优先级2：种植向日葵（如果没有危险或危险已处理）
        plant_sunflowers_logic()
    else:
        # 优先级3：扩展建设
        expansion_logic()

    # 基础防御：即使没有危险警报，也保持一定防御
    if not danger_alert and sun >= 100 and check_plant_CD('豌豆射手'):
        # 检查哪些行有僵尸但还不算危险
        for zombie in zombie_list:
            if 600 <= zombie['x'] < 800:  # 中等距离
                row = zombie['row']
                if not has_shooter_in_row(row):
                    # 在该行中间位置种植豌豆射手
                    for col in range(4, 6):
                        if (row, col) not in planted_grids:
                            plant_at(row, col, '豌豆射手')
                            break


if __name__ == "__main__":
    try:
        while True:
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
