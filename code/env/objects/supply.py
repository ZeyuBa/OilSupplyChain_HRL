from collections import defaultdict


class Supply(object):
    def __init__(self, config, mm):
        self.key = config['node_code']
        self.material = config['material_code']

        self.period = config['period']
        self.quantity= config['quantity']
        self.storage = [0 for i in self.material]

        self.demand = None
        self.demand_signal = 0
        self.nbr_road = []  # roads

        self.receive_list = defaultdict(float)
        self.signal_list = []

    def update(self):
        self.demand_signal = 0
        # 更新库存量
        for idx, material in enumerate(self.material):
            if material in self.receive_list.keys():
                self.storage[idx] += self.receive_list[material]
        self.receive_list.clear()
        # signal
        self.signal_list = []
        if self.demand is not None:
            for idx, material in enumerate(self.demand):
                self.storage[idx] -= (self.demand[material][0] + self.demand[material][1]) / 2
                # signal
                if self.storage[idx] < 0:
                    self.demand_signal = 1
                    self.signal_list.append({'node_type': 'supply', 'node_code': self.key, 'material_code': material,
                                             'signal': 'demand', 'storage': self.storage[idx], 'lower': 0,
                                             'upper': 'N'})

    def get_state(self):
        state = {
            'key': self.key,
            'lower_storage': self.quantity,
            'upper_storage': self.quantity,
            'demand': self.demand
        }
        return state

    def get_signal(self):
        return [self.demand_signal], self.signal_list

    def get_reward(self, step_cnt):
        # 油品运输费用
        t_reward = 0
        material_idx = 0
        for idx, p in enumerate(self.period):
            if step_cnt % p == 0:
                quantity = self.quantity[idx]
                if self.key == 'SINOPEC':
                    material_idx = idx
        for road in self.nbr_road:
            if self.material[material_idx] == road.material and quantity != 0:
                t_reward += road.cost * 10000 * quantity

        # 分油种库存警告惩罚、分油种库存舍弃损失
        sa_reward, sl_reward = 0, 0
        for idx, material in enumerate(self.material):
            short_storage = self.quantity[idx] - self.storage[idx]
            loss_storage = self.storage[idx] - self.quantity[idx]

            sa_reward += max(0, short_storage) * 10
            sl_reward += max(0, loss_storage) * 20

        return [-t_reward, 0, 0, 0, 0, 0]#[-t_reward, -sa_reward, -sl_reward, 0, 0, 0]

    def add_next_neighbor(self, nbr, road):
        self.nbr_road.append(road)

    def add_demand(self, demand, mm):
        self.demand = demand

    def update_receive_list(self, material, quantity):
        self.receive_list[material] += quantity
