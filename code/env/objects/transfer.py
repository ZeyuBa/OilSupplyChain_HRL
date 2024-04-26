from utils.box import Box
import numpy as np
from collections import defaultdict
from common.tools import Ub_value
from common.tools import Ub_safe
from common.tools import Nan_zero

class Transfer(object):
    def __init__(self, config, mm):
        self.key = config['node_code']
        self.materials = config['material']
        self.storage = {}
        self.inventory_cap = config['inventory_cap']  # max, safemax
        self.inventory_cap[0] = Ub_value(self.inventory_cap[0])
        self.inventory_cap[1] = Ub_value(self.inventory_cap[1])
        if self.inventory_cap[1] > self.inventory_cap[0]:
            self.inventory_cap[1] = self.inventory_cap[0]
        for mat in config['material']:
            self.storage[mat] = config['material'][mat]['open']
            
        for material in self.materials.keys():
            self.materials[material]['inventory_cap'][0] = Ub_value(self.materials[material]['inventory_cap'][0])
            self.materials[material]['inventory_cap'][1] = Ub_value(self.materials[material]['inventory_cap'][1])
            if self.materials[material]['inventory_cap'][1] > self.materials[material]['inventory_cap'][0]:
                self.materials[material]['inventory_cap'][1] = self.materials[material]['inventory_cap'][0]
            if self.storage[material] > self.materials[material]['inventory_cap'][0]:
                self.storage[material] = self.materials[material]['inventory_cap'][0]
            elif self.storage[material] < 0:
                self.storage[material] = 0
            if self.materials[material]['inventory_cap'][1] > self.materials[material]['inventory_cap'][0]:
                self.materials[material]['inventory_cap'][1] = self.materials[material]['inventory_cap'][0]

        self.demand = None
        self.signal = 0
        self.nbr_road = []

        self.receive_list = defaultdict(float)
        self.signal_list = []

    def set_action_space(self):
        action_space = []
        for _ in self.nbr_road:
            space = Box(0, 1, shape=(1,), dtype=np.float64)
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
        if self.demand is not None:
            for material in self.demand.keys():
                self.storage[material] -= (self.demand[material][0] + self.demand[material][1]) / 2
        # signal
        self.signal_list = []
        self.signal = 0
        for idx, material in enumerate(self.materials):
            if material in self.storage.keys():
                if self.storage[material] > self.materials[material]['inventory_cap'][0]:
                    self.signal = +1
                    self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': material,
                                             'signal': 'over upper', 'storage': self.storage[material],
                                             'upper': self.materials[material]['inventory_cap'][0]})
                if self.storage[material] > self.materials[material]['inventory_cap'][1]:
                    self.signal = +1
                    self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': material,
                                             'signal': 'over safeup', 'storage': self.storage[material],
                                             'upper': self.materials[material]['inventory_cap'][1]})
                if self.storage[material] < 0:
                    self.signal = 1
                    self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': material,
                                             'signal': 'over under', 'storage': self.storage[material],
                                             'down': 0})
#         if sum(self.storage.values()) > self.inventory_cap[0]:
#             self.signal = 1
#             self.signal_list.append({'node_type': 'transfer', 'node_code': self.key, 'material_code': 'total',
#                                      'signal': 'over upper', 'storage': sum(self.storage.values()),
#                                      'upper': self.inventory_cap[0]})

    def get_state(self):
        state = {
            'key': self.key,
            'materials': ['total'] + [i for i in self.storage.keys()],
            'storage': [sum(self.storage.values())] + [i for i in self.storage.values()],
            'upper_storage': [self.inventory_cap[0]] + [v['inventory_cap'][0] for v in self.materials.values()],
            'demand': self.demand
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

        # 总库存警告、总库存舍弃
        total_loss_storage = sum(self.storage.values()) - self.inventory_cap[0]
        total_alert_loss_storage = sum(self.storage.values()) - self.inventory_cap[1]

        ta_reward = max(0, total_alert_loss_storage) * 10
        tl_reward = max(0, total_loss_storage) * 20
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

        return [-t_reward, -sa_reward, -sl_reward, -ta_reward, -tl_reward, 0]

    def add_demand(self, demand, mm):
        self.demand = demand

    def add_next_neighbor(self, nbr, road):
        self.nbr_road.append(road)

    def update_receive_list(self, material, quantity):
        self.receive_list[material] += quantity
