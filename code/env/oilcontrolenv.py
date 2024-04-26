from env.simulators.game import Game
from env.objects import (Supply, Transfer, Refinery, Demand, Warehouse, Purchase, capTransport, Road)
import numpy as np

vertex_kinds = {
    'supply': Supply, 'purchase': Purchase, 'transfer': Transfer,
    'refinery': Refinery, 'local_demand': Demand, 'warehouse': Warehouse,
} # 油田、直采、中转、炼厂、地方需求、商储

transport_limitations = {}
P = 1000  # 出现预警第一天的惩罚项
gamma = 1.1  # 倍数因子，用于放大预警时长惩罚
# 运输费用/分库存警告/分库存舍弃/总库存警告/总库存舍弃/需求未满足/每日运输/周期运输/周期加工/预警个数
rho = np.array([0, 2e-3, 0, 0, 0, 4e-3, 0, 0, 0, 1e-4])  # 各类回报在总回报中的系数
# rho = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1e-2])  # 各类回报在总回报中的系数（统计预警用）


class OilControlEnv(Game):
    def __init__(self, conf, sys_conf):
        super().__init__(sum(sys_conf['n_vertices']), conf['is_obs_continuous'], conf['is_act_continuous'],
                         conf['game_name'], sum(sys_conf['n_vertices']), conf['obs_type'])
        self.sys_conf = sys_conf
        self.vertices = {
            'supply': {}, 'purchase': {}, 'transfer': {}, 'refinery': {},
            'local_demand': {}, 'warehouse': {},
        }
        self.edges = {}
        self.cap_transports = {}

        self.max_step = int(conf['max_step'])
        self.step_cnt = 0
        self.warning_cnt = 0  # 记录连续预警的天数
        self.n_rewards = np.zeros(10)  # 记录累计的各类回报
        self.signal_list = []

        self.current_state = None
        self.all_observes = None
        self.joint_action_space = None
        self.info = {}

    def init_system(self):
        # 初始化各节点信息
        for k in self.sys_conf.keys():
            v_configs = self.sys_conf[k]
            if k == 'supply' or k == 'transfer' or k == 'warehouse' or k == 'refinery':
                for conf in v_configs:
                    vertex = vertex_kinds[k](conf, self.sys_conf['material_member'])
                    self.vertices[k][conf['node_code']] = vertex
                    self.sys_conf['nodes'][conf['node_code']] = k
            elif k == "demand":
                for keys in v_configs.keys():
                    if keys in self.sys_conf['nodes']:
                        vertex = self.vertices[self.sys_conf['nodes'][keys]][keys]
                        vertex.add_demand(v_configs[keys], self.sys_conf['material_member'])
                    else:
                        vertex = vertex_kinds['local_demand'](keys, v_configs[keys])
                        self.vertices['local_demand'][keys] = vertex
                        self.sys_conf['nodes'][keys] = 'local_demand'
            elif k == "cap_transport":
                for conf in v_configs:
                    cap_vertex = capTransport(conf)
                    self.cap_transports[conf['cap_code']] = cap_vertex
                    
        for v in self.vertices['transfer'].values():
            if 'FSD' in v.key:
                v.inventory_cap = [0,0]
                for material in v.materials.values():
                    material['inventory_cap'] = [0,0]

        # 初始化道路信息
        r_configs = self.sys_conf['transport']
        node_map = self.sys_conf['nodes']
        for r in r_configs:
            cap_transports = [self.cap_transports[cap_code] for cap_code in r['cap_transport']]
            road = Road(r, cap_transports)
            start_vertex = self.vertices[node_map[r['from_code']]][r['from_code']]
            end_vertex = self.vertices[node_map[r['to_code']]][r['to_code']]
#             if node_map[r['from_code']] == 'supply':
#                 print('1',node_map[r['from_code']],r['from_code'],road.material,start_vertex.material)
#             if node_map[r['from_code']] == 'transfer':
#                 print('1',node_map[r['from_code']],r['from_code'],road.material,start_vertex.materials.keys())
#             print('2',node_map[r['to_code']], r['to_code'])
#             if (node_map[r['to_code']] == 'transfer' and road.material in end_vertex.materials.keys()):
#                 print(road.material, end_vertex.materials.keys())
            if (\
            (node_map[r['from_code']] == 'supply' and r['from_code'] in self.vertices['supply'].keys() and road.material in start_vertex.material) or \
            (node_map[r['from_code']] == 'transfer' and r['from_code'] in self.vertices['transfer'].keys() and road.material in start_vertex.materials.keys()) )\
            and\
            (\
            (node_map[r['to_code']] == 'transfer' and r['to_code'] in self.vertices['transfer'].keys() and road.material in end_vertex.materials.keys()) or \
            (node_map[r['to_code']] == 'refinery' and r['to_code'] in self.vertices['refinery'].keys()) ):
                start_vertex.add_next_neighbor(end_vertex, road)
#                 if node_map[r['from_code']] != 'supply':
                self.edges[road.key+'-'+road.material] = road
            
#         self.materials_list = []
#         for k in self.vertices['supply'].values():
#             for material in k.material:
#                 if material not in self.materials_list:
#                     self.materials_list.append(material)
#         for k in self.vertices['transfer'].values():
#             for material in k.materials.keys():
#                 if material not in self.materials_list:
#                     self.materials_list.append(material)
                    
#         for r in self.edges.values():
#             material = r.material
#             end_v = r.end
#             if end_v in self.vertices['transfer']:
#                 if material not in self.vertices['transfer'][end_v].materials and material in self.materials_list:
#                     self.vertices['transfer'][end_v].materials[material] = {'open':0, 'inventory_cap':[0,0]}
#                     self.vertices['transfer'][end_v].storage[material] = 0
        

    def reset(self):
        self.step_cnt = 0
        self.warning_cnt = 0
        self.n_rewards = np.zeros(10)
        self.signal_list = []

        self.vertices = {
            'supply': {}, 'transfer': {}, 'refinery': {},
            'local_demand': {}, 'warehouse': {},
        }
        self.edges = {}
        self.init_system()

        self.current_state = self.get_state()
        self.all_observes = self.get_observations()
        self.joint_action_space, self.action_space = self.set_action_space()

        return self.all_observes

    def step(self, all_action):
        self.step_cnt += 1
        self.current_state = self.get_next_state(all_action)
        self.all_observes = self.get_observations()

        # 更新连续预警天数
        if sum(self.current_state['signal']) == 0:
            self.warning_cnt = 0
        else:
            self.warning_cnt += 1

        reward, split_rewards = self.get_reward(all_action)
        self.n_rewards = split_rewards
        self.info.update({'split_rewards': self.n_rewards})
        done = self.is_terminal()

        return self.all_observes, reward, done, self.info

    def get_state(self):
        self.signal_list = []
        signal = []
        state = {
            'transfer': [], 'refinery': [],
#             'local_demand': [], 'warehouse': []
        }
        for k in state.keys():
            for vertex in self.vertices[k].values():
                if 'FSD' not in vertex.key:
                    state[k].append(vertex.get_state())
                    signal_v, signal_list = vertex.get_signal()
                    signal += signal_v
                    self.signal_list += signal_list
        state['signal'] = signal
        return state

    def get_next_state(self, all_action):
        # 清空前一天的道路运输量
        for trans in transport_limitations.values():
            trans.receive_cap = 0

        # supply节点发出
        supplys = self.vertices['supply']
        for supply in supplys.values():
            material_idx = 0
            for idx, p in enumerate(supply.period):
                if self.step_cnt % p == 0:
#                     quantity = supply.quantity[idx]
#                     if supply.key == 'SINOPEC':
#                         material_idx = idx
                    for road in supply.nbr_road:
                        nbr = road.end
                        if supply.key+'_'+nbr+'_'+road.material in all_action.keys():
                            quantity = all_action[supply.key+'_'+nbr+'_'+road.material]
                        else:
                            quantity = 0
                        if supply.material[material_idx] == road.material and quantity != 0:
                            cap_transports = road.cap_transports  # 抚顺多个管段
                            nbr_vertex = self.vertices[self.sys_conf['nodes'][nbr]][nbr]
                            nbr_vertex.update_receive_list(supply.material[material_idx], quantity)
                    break
#                     for cap_transport in cap_transports:
#                         cap_transport.update_receive_cap(quantity)
#                         cap_transport.road_quantities[road.key] = quantity
        
        # refinery节点
        refinerys = self.vertices['refinery']
        for refinery in refinerys.values():
            quantity = all_action[refinery.key]
            refinery.update_JG_list(quantity)
#             print('r:',quantity)

        # transfer节点 和 warehouse节点
        trans_vertices = ['transfer']
        for k in trans_vertices:
            vertices = self.vertices[k]
            # all_actions = all_action[k]

            # # 动作映射
            # for actions in all_actions.values():
            #     if len(actions) <= 0:
            #         continue
            #     idx_ratio = sorted(list(enumerate(actions)), key=lambda x: x[1])
            #     for i in range(1, len(idx_ratio)):
            #         actions[idx_ratio[i][0]] = idx_ratio[i][1] - idx_ratio[i - 1][1]

            for vertice in vertices.values():
                for idx, road in enumerate(vertice.nbr_road):
                    nbr = road.end
                    material = road.material
                    if vertice.key+'_'+nbr+'_'+road.material in all_action.keys():
                        trans_quantity = all_action[vertice.key+'_'+nbr+'_'+road.material]
#                         print('t:',trans_quantity)
                    else:
                        trans_quantity = 0
#                     if material in vertice.storage.keys():  # 有的油没有对应储量，铁岭原油库
#                         storage = vertice.storage[material]
#                     else:
#                         storage = 0
                    quantity = trans_quantity
#                     print(vertice.key+'_'+nbr+'_'+road.material,quantity)
#                     cap_transports = road.cap_transports
#                     for cap_transport in cap_transports:
#                         cap_transport.update_receive_cap(quantity)
#                         cap_transport.road_quantities[road.key] = quantity
                    nbr_vertex = self.vertices[self.sys_conf['nodes'][nbr]][nbr]
                    nbr_vertex.update_receive_list(material, quantity)
                    vertice.update_receive_list(material, -quantity)

        # 更新
        for vertices in self.vertices.values():
            for vertice in vertices.values():
                vertice.update()
        next_state = self.get_state()
        return next_state

    def get_observations(self):
        return self.current_state

    def set_action_space(self):
        joint_action_space = {
            'transfer': {}, 'refinery': {}
        }
        action_dims = 0
        for k in joint_action_space.keys():
            for vertex in self.vertices[k].values():
                action_space = vertex.set_action_space()
                joint_action_space[k][vertex.key] = action_space
#                 for v in action_space.values():
#                     action_dims += len(v)
                if k == 'transfer' and 'FSD' not in vertex.key:
                    action_dims += len(vertex.materials.keys())
                elif k == 'refinery':
                    action_dims += 3
        return joint_action_space, action_dims

    def get_single_action_space(self, kind, idx):
        vertex_list = self.joint_action_space.get(kind)
        if not vertex_list:
            return None
        return vertex_list[idx]

    def get_reward(self, all_action):
        # 计算每个节点的回报
        # 油品运输费用/分油种库存警告/分油种库存舍弃/总库存警告/总库存舍弃/需求未满足
        # t/sa/sl/ta/tl/g_reward
        split_rewards = np.zeros(6)
        for k in self.vertices.keys():
            for vertex in self.vertices[k].values():
                if k == 'supply':
                    reward = vertex.get_reward(self.step_cnt)
                elif k == 'transfer':
                    reward = vertex.get_reward(all_action)
                elif k == 'refinery':
                    reward = vertex.get_reward()
                split_rewards += np.array(reward)

        # 每天运量惩罚
        trans_reward = 0
        for trans in transport_limitations.values():
            trans_reward += (max(0, trans.receive_cap - trans.upperbound[0]) +
                             max(0, trans.lowerbound[0] - trans.receive_cap))

        # 周期运量总惩罚/周期加工量总惩罚
        total_trans_reward, JG_reward = 0, 0
        if self.step_cnt == self.max_step:
            for trans in transport_limitations.values():
                # 每周期运量惩罚
                loss_trans_cap = trans.total_receive_cap - trans.upperbound[1]
                total_trans_reward += max(0, loss_trans_cap)
            for refinery in self.vertices['refinery'].values():
                # 每周期加工量惩罚
                short_JG_cap = refinery.JG_capacity['M'][0] - refinery.total_JG_quantity
                loss_JG_cap = refinery.total_JG_quantity - refinery.JG_capacity['M'][1]
                JG_reward += (max(0, short_JG_cap) + max(0, loss_JG_cap))

        # 计算系统的预警时长惩罚
        # w_reward = -P * (gamma ** (self.warning_cnt - 1)) if self.warning_cnt > 0 else 0
        # 计算系统总预警个数
        wn_reward = sum(self.current_state['signal']) * 100

        # 按系数计算总回报
        split_rewards = np.append(split_rewards,
                                  [-trans_reward, -total_trans_reward, -JG_reward, -wn_reward], axis=0)
        weighted_rewards = np.multiply(split_rewards, rho)
        total_reward = np.sum(weighted_rewards)

        return total_reward, weighted_rewards

    def is_terminal(self):
        is_done = self.step_cnt >= self.max_step
        return is_done

    def obs2vec(self, state):
        obs_vec = []

        trans_inf = state['transfer']
        for item in trans_inf:
#             storage_len = len(item['upper_storage'])
#             a = np.array(item['storage'], dtype=np.float32)[:storage_len] - \
#                 np.array(item['upper_storage'], dtype=np.float32)
#             b = np.array(item['upper_storage'], dtype=np.float32)
#             b[b == 0] = a[b == 0] + 0.00001
#             obs_vec += list(a / b)
            a = np.array(item['storage'], dtype=np.float32)
            obs_vec += list(a)

        ref_inf = state['refinery']
        for item in ref_inf:
            for k in item['storage'].keys():
#                 if k + '_lower_storage' in item.keys():
#                     a = np.array(item['storage'][k]) - np.array(item[k + '_upper_storage'][0]) / 2
#                     b = np.array(item[k + '_upper_storage'][0] - item[k + '_lower_storage'][0])
#                     b[b == 0] = a[b == 0] + 0.00001
#                     obs_vec += [a / b]
#                 else:
#                     obs_vec += [item['storage'][k] / 100]
                obs_vec += [item['storage'][k]]
            obs_vec.append(item['left_JG_budget'])

#         obs_vec += state['signal']
        return obs_vec

    def vec2action(self, actions):
        all_action = {}
        idn = 0
#         for key in self.joint_action_space.keys():
#             all_action[key] = {}
#             for k, item in self.joint_action_space[key].items():
#                 all_action[key][k] = []
#                 for v in item.values():
#                     for _ in v:
#                         all_action[key][k].append(actions[idx])
#                         idx += 1
        # supply节点发出
        supplys = self.vertices['supply']
        for supply in supplys.values():
            for road in supply.nbr_road:
                nbr = road.end
                all_action[supply.key+'_'+nbr+'_'+road.material] = actions[idn]
                idn += 1
            break
            
        trans_vertices = ['transfer']
        for k in trans_vertices:
            vertices = self.vertices[k]
            for vertice in vertices.values():
                for idx, road in enumerate(vertice.nbr_road):
                    nbr = road.end
                    material = road.material
                    all_action[vertice.key+'_'+nbr+'_'+road.material] = actions[idn]
                    idn += 1
        
        # refinery节点
        refinerys = self.vertices['refinery']
        for refinery in refinerys.values():
            all_action[refinery.key] = actions[idn]
            idn += 1
            
        return all_action
