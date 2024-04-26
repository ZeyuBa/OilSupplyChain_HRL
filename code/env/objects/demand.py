from collections import defaultdict


class Demand(object):
    def __init__(self, key, config):
        self.key = key
        self.demands = config
        self.signal = 0
        self.storage = {}
        self.receive_list = defaultdict(float)

    def update(self):
        # 更新库存量
        for material in self.receive_list.keys():
            if material in self.storage.keys():
                self.storage[material] += self.receive_list[material]
            else:
                self.storage[material] = self.receive_list[material]
        self.receive_list.clear()
        # 更新信号
        self.signal = 0
        for material in self.demands.keys():
            if material not in self.storage.keys():
                self.signal = 1
            elif self.storage[material] < self.demands[material][0] or \
                    self.storage[material] > self.demands[material][1]:
                self.signal = 1

    def get_state(self):
        state = {
            'key': self.key,
            'demand': self.demands,
        }
        return state

    def get_signal(self):
        return [self.signal]

    def get_reward(self):
        # 需求未满足惩罚
        g_reward = 0
        for material in self.demands.keys():
            short_demand = self.demands[material][0] - self.storage[material]
            loss_demand = self.storage[material] - self.demands[material][1]

            g_reward += (max(0, short_demand), max(0, loss_demand)) * 30

        return [0, 0, 0, 0, 0, -g_reward]

    def update_receive_list(self, material, quantity):
        self.receive_list[material] += quantity
