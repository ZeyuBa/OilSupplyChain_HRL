from env.objects.depot import PetrolDepot


class Province(object):
    def __init__(self, config):
        self.key = config['key']
        self.gas_lack_coef = config['gas_lack_coef']
        self.diesel_lack_coef = config['diesel_lack_coef']

        self.gas = PetrolDepot(belongsTo=self.key, config=config['gas_depot'])
        self.diesel = PetrolDepot(belongsTo=self.key, config=config['diesel_depot'])

    def update(self, action):
        # 更新汽油库
        gas_in = self.gas.get_today_receive()
        self.gas.update_storage(action['gas_need'], gas_in)

        # 更新柴油库
        diesel_in = self.diesel.get_today_receive()
        self.diesel.update_storage(action['diesel_need'], diesel_in)

    def get_state(self):
        state = {
            'gas_storage': self.gas.storage,
            'diesel_storage': self.diesel.storage,
            'lower_gas': self.gas.lower_storage,
            'upper_gas': self.gas.upper_storage,
            'lower_diesel': self.diesel.lower_storage,
            'upper_diesel': self.diesel.upper_storage
        }
        return state

    def get_signal(self):
        return [self.gas.signal, self.diesel.signal]

    def get_reward(self, action=None):
        # 汽油库存警告惩罚、库存舍弃损失
        g_o_reward, g_l_reward = self.gas.get_part_reward()
        # 柴油库存警告惩罚、库存舍弃损失
        d_o_reward, d_l_reward = self.diesel.get_part_reward()
        o_reward = g_o_reward + d_o_reward
        l_reward = g_l_reward + d_l_reward

        # 库存缺口惩罚
        g_g_reward = self.gas_lack_coef * max(0, -self.gas.storage)
        d_g_reward = self.diesel_lack_coef * max(0, -self.diesel.storage)
        g_reward = g_g_reward + d_g_reward

        return [0, -o_reward, -l_reward, -g_reward]

    # 汽油库相关操作
    def add_gas2receive(self, gas, day):
        self.gas.add_future_receive(gas, day)

    # 柴油库相关操作
    def add_diesel2receive(self, diesel, day):
        self.diesel.add_future_receive(diesel, day)
