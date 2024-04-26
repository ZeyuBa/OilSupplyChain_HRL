from utils.box import Box
import numpy as np
from collections import defaultdict


class Warehouse(object):
    def __init__(self, config, mm):
        self.key = config['node_code']
        self.materials = config['material']
        self.storage = {}
        self.inventory_cap = config['inventory_cap']  # max, safemax
        if self.inventory_cap[1] > self.inventory_cap[0]:
            self.inventory_cap[1] = self.inventory_cap[0]
        for mat in config['material']:
            self.storage[mat] = config['material'][mat]['open']
            
        for mat in config['material']:
            self.storage[mat] = config['material'][mat]['open']
            
        for material in self.materials.keys():
            if self.storage[material] > self.materials[material]['inventory_cap'][0]:
                self.storage[material] = self.materials[material]['inventory_cap'][0]
            elif self.storage[material] < 0:
                self.storage[material] = 0
            if self.materials[material]['inventory_cap'][1] > self.materials[material]['inventory_cap'][0]:
                self.materials[material]['inventory_cap'][1] = self.materials[material]['inventory_cap'][0]

        self.nbr_road = []
        self.receive_list = defaultdict(float)

        self.signal = 0
        self.signal_list = []

    def set_action_space(self):  # 可以运，不是首选
        action_space = []
        for _ in self.nbr_road:
            space = Box(0, 999, shape=(1,), dtype=np.float64)  # 没有能力限制
            action_space.append(space)
        action_space = {'road_action_space': action_space}
        return action_space

    def update(self):
        for material in self.receive_list.keys():
            if material in self.storage.keys():
                self.storage[material] += self.receive_list[material]
#             else:
#                 self.storage[material] = self.receive_list[material]
        self.receive_list.clear()
        
        # signal
        self.signal_list = []
        self.signal = 0
        for idx, material in enumerate(self.materials):
            if material in self.storage.keys():
                if self.storage[material] > self.materials[material]['inventory_cap'][0]:
                    self.signal = 1
                    self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': material,
                                             'signal': 'over upper', 'storage': self.storage[material],
                                             'upper': self.materials[material]['inventory_cap'][0]})
        if sum(self.storage.values()) > self.inventory_cap[0]:
            self.signal = 1
            self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': 'total',
                                     'signal': 'over upper', 'storage': sum(self.storage.values()),
                                     'upper': self.inventory_cap[0]})

    def get_state(self):
        state = {
            'key': self.key,
            'materials': ['total'] + [i for i in self.storage.keys()],
            'storage': [sum(self.storage.values())] + [i for i in self.storage.values()],
            'upper_storage': [self.inventory_cap[0]] + [v['inventory_cap'][0] for v in self.materials.values()],
        }
        return state

    def get_signal(self):
        return [self.signal], self.signal_list

    def get_reward(self, action):
        # 油品运输费用
        t_reward = 0
        for idx, road in enumerate(self.nbr_road):
            nbr = road.end
            if self.key+'_'+nbr+'_'+road.material in action.keys():
                quantity = action[self.key+'_'+nbr+'_'+road.material]
            else:
                # print(self.key+'_'+nbr+'_'+road.material)
                quantity = 0
            t_reward += road.cost * 10000 * quantity

        # 分油种库存警告惩罚、分油种库存舍弃损失
        sa_reward, sl_reward = 0, 0
        for idx, material in enumerate(self.materials):
            loss_storage = self.storage[material] - self.materials[material]['inventory_cap'][0]
            alert_loss_storage = self.storage[material] - self.materials[material]['inventory_cap'][1]

            sa_reward += max(0, alert_loss_storage) * 10
            sl_reward += max(0, loss_storage) * 20
            
            if self.storage[material] > self.materials[material]['inventory_cap'][0]:
                self.storage[material] = self.materials[material]['inventory_cap'][0]
            elif self.storage[material] < 0:
                self.storage[material] = 0

        # 总库存警告、总库存舍弃
        total_loss_storage = sum(self.storage.values()) - self.inventory_cap[0]
        total_alert_loss_storage = sum(self.storage.values()) - self.inventory_cap[1]

        ta_reward = max(0, total_alert_loss_storage) * 10
        tl_reward = max(0, total_loss_storage) * 20

        return [-t_reward, -sa_reward, -sl_reward, -ta_reward, -tl_reward, 0]

    def add_next_neighbor(self, nbr, road):
        self.nbr_road.append(road)

    def update_storage(self, material, quantity):
        if material in self.storage.keys():
            self.storage[material] += quantity
        else:
            self.storage[material] = quantity

    def update_receive_list(self, material, quantity):
        self.receive_list[material] += quantity
