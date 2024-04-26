from telnetlib import SE
from utils.box import Box
import numpy as np
from common.tools import Ub_value
from common.tools import Ub_safe
from common.tools import Nan_zero

class Refinery(object):
    def __init__(self, config, mm):
        self.key = config['node_code']
        self.JY_recipe = config['JY_recipe']
        self.JG_capacity ={
            'D': config['JG_capacity']['D'],  # min, max
            'M': config['JG_capacity']['M']
        } 
        self.ratio = config['JG_recipe']
        self.immediate = {
            'PGLE0': 0,
            'PLDO0': 0,
            'PKER': 0,
            'XWZ': 0,
        }
        self.storage = {
            'JGHY': 0,
            'PGLE': 0,
            'PLDO': 0
        }
        for mat in config['open'].keys():
            if mat in mm.keys():
                self.storage[mm[mat]] += config['open'][mat]
            elif mat == 'JGHY':
                self.storage[mat] += config['open'][mat]
            else:
                self.immediate[mat] += config['open'][mat]
                
        self.storage['PGLE'] += self.immediate['PGLE0']
        self.storage['PLDO'] += self.immediate['PLDO0']
        self.immediate['PGLE0'] = 0
        self.immediate['PLDO0'] = 0
            

        self.inventory_cap = config['inventory_cap']  # max, safemax
        
        for material1, material2 in {'JGHY':'JGHY', 'PLDO':'CY', 'PGLE':'QY'}.items():
            self.inventory_cap[material2][0] = Ub_value(self.inventory_cap[material2][0])
            self.inventory_cap[material2][1] = Ub_value(self.inventory_cap[material2][1])
            if self.inventory_cap[material2][1] > self.inventory_cap[material2][0]:
                self.inventory_cap[material2][1] = self.inventory_cap[material2][0]
            
            if self.storage[material1] > self.inventory_cap[material2][0]:
                self.storage[material1] = self.inventory_cap[material2][0]
            elif self.storage[material1] < 0:
                self.storage[material1] = 0
        
        self.demand = {
            'PGLE': [0, 0],  # min, max
            'PLDO': [0, 0],
            'PKER': [0, 0],
        }

        self.JGHY_signal = 0
        self.CY_signal = 0
        self.QY_signal = 0
        self.PKER_signal = 0
        self.nbr_road = []

        self.receive_list = {'JGHY': 0}
        self.JG_quantity = 0
        self.total_JG_quantity = 0
        self.signal_list = []
        # 记录当月剩余可加工量（每日更新）
        self.left_JG_budget = 1

    @staticmethod
    def set_action_space():
        action_space = {
            'process': [Box(0, 1, shape=(1,), dtype=np.float64)],
        }
        return action_space

    def update(self):
        # 更新库存量
        for material in self.receive_list.keys():
            if material in self.storage.keys():
                self.storage[material] += self.receive_list[material]
            else:
                self.storage[material] = self.receive_list[material]
        self.receive_list = {'JGHY': 0}
        if self.demand is not None:
            for material in self.demand.keys():
                if material == 'PKER':
                    self.immediate[material] -= (self.demand[material][0] + self.demand[material][1]) / 2 * 1.25
                else:
                    self.storage[material] -= (self.demand[material][0] + self.demand[material][1]) / 2 * 1.25
        
        # 更新加工
        for material in self.ratio.keys():
            quantity = self.storage['JGHY'] if self.JG_quantity > self.storage['JGHY'] else self.JG_quantity
            self.immediate[material] += quantity * self.ratio[material]
        self.storage['PLDO'] += self.immediate['PLDO0']
        self.storage['PGLE'] += self.immediate['PGLE0']
        self.immediate['PLDO0'] = 0
        self.immediate['PGLE0'] = 0
        self.storage['JGHY'] -= quantity
        self.total_JG_quantity += quantity
        # 更新当月剩余可加工量
        self.left_JG_budget -= quantity / self.JG_capacity['M'][0]
        
        # signal
        self.signal_list = []
        self.JGHY_signal = 0
        if self.storage['JGHY'] > self.inventory_cap['JGHY'][0]:
            self.JGHY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'JGHY',
                                     'signal': 'over upper', 'storage': self.storage['JGHY'],
                                     'upper': self.inventory_cap['JGHY'][0]})
        if self.storage['JGHY'] > self.inventory_cap['JGHY'][1]:
            self.JGHY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'JGHY',
                                     'signal': 'over safeup', 'storage': self.storage['JGHY'],
                                     'upper': self.inventory_cap['JGHY'][1]})
        if self.storage['JGHY'] < 0:
            self.JGHY_signal = 1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'JGHY',
                                     'signal': 'short', 'storage': self.storage['JGHY'],
                                     'down': 0})
        
        self.CY_signal = 0
        if self.storage['PLDO'] > self.inventory_cap['CY'][0]:
            self.CY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'CY',
                                     'signal': 'over upper', 'storage': self.storage['PLDO'] ,
                                     'upper': self.inventory_cap['CY'][0]})
        if self.storage['PLDO'] > self.inventory_cap['CY'][1]:
            self.CY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'CY',
                                     'signal': 'over safeup', 'storage': self.storage['PLDO'] ,
                                     'upper': self.inventory_cap['CY'][1]})
        if self.storage['PLDO'] < 0:
            self.CY_signal = 1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'CY',
                                     'signal': 'short', 'storage': self.storage['PLDO'] ,
                                     'down': 0})

        self.QY_signal = 0
        if self.storage['PGLE'] > self.inventory_cap['QY'][0]:
            self.QY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'QY',
                                     'signal': 'over upper', 'storage': self.storage['PGLE'],
                                     'upper': self.inventory_cap['QY'][0]})
        if self.storage['PGLE'] > self.inventory_cap['QY'][1]:
            self.QY_signal = +1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'QY',
                                     'signal': 'over safeup', 'storage': self.storage['PGLE'],
                                     'upper': self.inventory_cap['QY'][1]})
        if self.storage['PGLE'] < 0:
            self.QY_signal = 1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'QY',
                                     'signal': 'short', 'storage': self.storage['PGLE'],
                                     'down': 0})

        self.PKER_signal = 0
        if self.immediate['PKER'] < 0:
            self.PKER_signal = 1
            self.signal_list.append({'node_type': 'refinery', 'node_code': self.key, 'material_code': 'PKER',
                                     'signal': 'short', 'storage': self.immediate['PKER'],
                                     'down': 0})
    
    def get_state(self):
        state = {
            'key': self.key,
            'storage': self.storage,
            'JG_lower': self.JG_capacity['D'][0],
            'JG_upper': self.JG_capacity['D'][1],
            'JGHY_upper_storage': [self.inventory_cap['JGHY'][0], self.inventory_cap['JGHY'][1]],
            'PLDO_upper_storage': [self.inventory_cap['CY'][0], self.inventory_cap['CY'][1]],
            'PGLE_upper_storage': [self.inventory_cap['QY'][0], self.inventory_cap['QY'][1]],
            'demand': self.demand,
            'left_JG_budget': self.left_JG_budget
        }
        return state

    def get_signal(self):
        return [self.JGHY_signal, self.CY_signal, self.QY_signal, self.PKER_signal], self.signal_list

    def get_reward(self):
        # if self.left_JG_budget < 0:
        #     return [0, -10000, -10000, 0, 0, 0]
        # 油品运输费用
        t_reward = 0
        refinery_reward_gain = 5

        sa_reward, sl_reward = 0, 0
        # 加工混油警告惩罚、库存舍弃损失
        JGHY_loss_storage = self.storage['JGHY'] - self.inventory_cap['JGHY'][0]
        alert_JGHY_loss_storage = self.storage['JGHY'] - self.inventory_cap['JGHY'][1]

        sa_reward += max(0, alert_JGHY_loss_storage) * 10 * refinery_reward_gain
        sl_reward += max(0, JGHY_loss_storage) * 20 * refinery_reward_gain

        # 柴油库存警告惩罚、库存舍弃损失
        CY_loss_storage = self.storage['PLDO'] - self.inventory_cap['CY'][0]
        alert_CY_loss_storage = self.storage['PLDO'] - self.inventory_cap['CY'][1]

        sa_reward += max(0, alert_CY_loss_storage) * 10 * refinery_reward_gain
        sl_reward += max(0, CY_loss_storage) * 20 * refinery_reward_gain

        # 汽油库存警告惩罚、库存舍弃损失
        QY_loss_storage = self.storage['PGLE'] - self.inventory_cap['QY'][0]
        alert_QY_loss_storage = self.storage['PGLE'] - self.inventory_cap['QY'][1]

        sa_reward += max(0, alert_QY_loss_storage) * 10 * refinery_reward_gain
        sl_reward += max(0, QY_loss_storage) * 20 * refinery_reward_gain
        
        demand_reward = 0
        demand_reward -= self.storage['PLDO'] if self.storage['PLDO'] < 0 else 0
        demand_reward -= self.storage['PGLE'] if self.storage['PGLE'] < 0 else 0
        demand_reward -= self.immediate['PKER'] if self.immediate['PKER'] < 0 else 0
        demand_reward *= 20 * refinery_reward_gain
        
        for material1, material2 in {'JGHY':'JGHY', 'PLDO':'CY', 'PGLE':'QY'}.items():
            if self.storage[material1] > self.inventory_cap[material2][0]:
                self.storage[material1] = self.inventory_cap[material2][0]
            elif self.storage[material1] < 0:
                self.storage[material1] = 0
        self.immediate['PKER'] = 0

        return [-t_reward, -sa_reward, -sl_reward, 0, 0, -demand_reward]

    def add_demand(self, demand, mm):
        for mat in demand.keys():
            if mat in mm.keys():
                self.demand[mm[mat]][0] += demand[mat][0]
                self.demand[mm[mat]][1] += demand[mat][1]
            else:
                self.demand[mat] = [demand[mat][0], demand[mat][1]]
#         for mat in self.demand.keys():
#             if self.demand[mat][1] == 0:
#                 self.demand[mat][1] = 999

    def add_next_neighbor(self, nbr, road):
        self.nbr_road.append(road)

    def update_receive_list(self, material, quantity):
        self.receive_list['JGHY'] += quantity

    def update_JG_list(self, quantity):
        self.JG_quantity = quantity
        
