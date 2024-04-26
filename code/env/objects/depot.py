from collections import defaultdict

alpha = 1.1
beta = 0.9


class Depot(object):
    def __init__(self, belongsTo, config):
        self.belongsTo = belongsTo
        self.connectedTo = defaultdict(list)

        self.storage = config['init_storage']
        self.lower_storage = config['lower_storage']
        self.upper_storage = config['upper_storage']
        self.max_storage = config['max_storage']
        self.warn_coef = config['warn_coef']
        self.loss_coef = config['loss_coef']

        self.receive_list = []  # 油品接收列表，每项为二元组(receive, day)
        self.loss_storage = 0
        self.signal = 0

    def add_neighbor(self, nbr, road):
        self.connectedTo[nbr].append(road)

    def get_connections(self):
        return list(self.connectedTo.keys())

    def get_roads(self, nbr):
        return self.connectedTo.get(nbr)

    def add_future_receive(self, goods, day):  # 记录day天后到达该库的货物量
        self.receive_list.append([goods, day])

    def get_today_receive(self):  # 计算今天能到达该库的货物量
        raise NotImplementedError

    def update_storage(self, out_storage, in_storage):
        raise NotImplementedError

    def check_storage(self):
        raise NotImplementedError

    def get_part_reward(self):  # 获取与库存相关的部分回报（库存警告惩罚、库存舍弃损失）
        raise NotImplementedError


# 汽油、柴油库
class PetrolDepot(Depot):
    def __init__(self, belongsTo, config):
        super().__init__(belongsTo, config)

    def get_today_receive(self):
        petrol_receive = 0
        for i in range(len(self.receive_list) - 1, -1, -1):
            self.receive_list[i][1] -= 1
            if self.receive_list[i][1] <= 0:
                petrol_receive += self.receive_list.pop(i)[0]
        return petrol_receive

    def update_storage(self, out_storage, in_storage):
        self.loss_storage = 0
        self.storage += (in_storage - out_storage)
        self.check_storage()

    def check_storage(self):
        # 确定上下界
        if self.signal == 0:
            lb, ub = self.lower_storage, self.upper_storage
        else:
            lb, ub = alpha * self.lower_storage, beta * self.upper_storage
        # 更新监测信号
        if lb <= self.storage <= ub:
            self.signal = 0
        elif ub < self.storage <= self.max_storage:
            self.signal = 1
        elif self.storage > self.max_storage:
            self.loss_storage = self.storage - self.max_storage
            self.storage = self.max_storage
            self.signal = 2
        elif 0 <= self.storage < lb:
            self.signal = 3
        else:
            self.signal = 4

    def get_part_reward(self):
        # 库存警告惩罚
        if self.storage <= 0:
            o_reward = self.warn_coef * self.lower_storage
        elif self.storage < self.lower_storage:
            o_reward = self.warn_coef * (self.lower_storage - self.storage)
        elif self.upper_storage < self.storage < self.max_storage:
            o_reward = self.warn_coef * (self.storage - self.upper_storage)
        elif self.loss_storage > 0:
            o_reward = self.warn_coef * (self.max_storage - self.upper_storage)
        else:
            o_reward = 0
        # 库存舍弃损失
        l_reward = self.loss_coef * self.loss_storage
        return o_reward, l_reward


# 原油库
class CrudeDepot(Depot):
    def __init__(self, belongsTo, config):
        super().__init__(belongsTo, config)
        self.crude_kinds = config['crude_kinds']
        self.storage = {idx: s for idx, s in zip(config['crude_kinds'], config['init_storage'])}

    def get_today_receive(self):
        crude_receive = defaultdict(int)
        for i in range(len(self.receive_list) - 1, -1, -1):
            self.receive_list[i][1] -= 1
            if self.receive_list[i][1] <= 0:
                crude = self.receive_list.pop(i)[0]
                for idx in crude.keys():
                    crude_receive[idx] += crude[idx]
        return crude_receive

    def update_storage(self, out_storage, in_storage):
        self.loss_storage = 0
        for idx in out_storage.keys():
            self.storage[idx] -= out_storage[idx]
        for idx in in_storage.keys():
            self.storage[idx] += in_storage[idx]
        self.check_storage()

    def check_storage(self):
        # 确定上下界
        if self.signal == 0:
            lb, ub = self.lower_storage, self.upper_storage
        else:
            lb, ub = alpha * self.lower_storage, beta * self.upper_storage
        total_storage = sum(self.storage.values())
        # 更新监测信号
        if lb <= total_storage <= ub:
            self.signal = 0
        elif ub < total_storage <= self.max_storage:
            self.signal = 1
        elif total_storage > self.max_storage:
            self.loss_storage = total_storage - self.max_storage
            for idx in self.storage.keys():
                self.storage[idx] = self.storage[idx] * self.max_storage / total_storage
            self.signal = 2
        elif 0 <= total_storage < lb:
            self.signal = 3
        else:
            self.signal = 4

    def get_part_reward(self):
        # 库存警告惩罚
        total_storage = sum(self.storage.values())
        if total_storage <= 0:
            o_reward = self.warn_coef * self.lower_storage
        elif total_storage < self.lower_storage:
            o_reward = self.warn_coef * (self.lower_storage - total_storage)
        elif self.upper_storage < total_storage < self.max_storage:
            o_reward = self.warn_coef * (total_storage - self.upper_storage)
        elif self.loss_storage > 0:
            o_reward = self.warn_coef * (self.max_storage - self.upper_storage)
        else:
            o_reward = 0
        # 库存舍弃损失
        l_reward = self.loss_coef * self.loss_storage
        return o_reward, l_reward
