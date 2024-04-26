"""
运筹算子+求解器模型
包含了12种算子
所有算子优化的优先级：成品油>炼厂原油>转运原油>运费
v1.1 温俊锐 10.15 算子数添加到12，添加多目标优化，调整炼厂原油比重
v1.0 温俊锐 10.11 在强化学习+求解器框架的基础上建立类
based 史俊研 基本求解模型
"""

import sys
import gurobipy as gp
import numpy as np
import pandas as pd
from collections import defaultdict
from gurobipy import GRB, abs_

from common.tools import Ub_value
from common.tools import Ub_safe
from common.tools import Nan_zero


class Behavioral_solver():
    def __init__(self, vertices, edges):
        self.reset(vertices, edges)
    
    def reset(self, vertices, edges):
        self.satisfy_N_day = 5
        self.demand_one = {}
        self.demand_N = {}   
        
        #读取供应节点
        self.node_mat_supply = {}
        for k,v in vertices['supply'].items():
            road_num = len(v.nbr_road)
            for idx,p in enumerate(v.period):
                # 取最大供应
                for m_code in v.material:
                    if (k,m_code) in self.node_mat_supply.keys():
                        self.node_mat_supply[(k,m_code)] = max(v.quantity[idx]*road_num, self.node_mat_supply[(k,m_code)])  
                    else:
                        self.node_mat_supply[(k,m_code)] = v.quantity[idx]*road_num
        self.supplyk = self.node_mat_supply.keys()

        #读取转运节点
        self.origin_distri = []#原油分输
        self.origin_transfer = []#原油中转库
        self.demand = {}
        self.origin_transfer_min = {}
        self.origin_transfer_max = {}
        self.origin_transfer_safetyLb = {}
        self.origin_transfer_safetyUb = {}
        self.origin_transfer_open = {}
        self.origin_transfer_supply = {}
        for k,v in vertices['transfer'].items():
            for m_code,m_info in v.materials.items():
                if 'FSD' in k:
                    self.origin_distri.append((k,m_code))

                self.origin_transfer.append((k,m_code))
                self.origin_transfer_min[(k,m_code)] = 0
                self.origin_transfer_max[(k,m_code)] = Ub_value(m_info['inventory_cap'][0])
                self.origin_transfer_safetyLb[(k,m_code)] = 0
                self.origin_transfer_safetyUb[(k,m_code)] = Ub_value(m_info['inventory_cap'][1])
                self.origin_transfer_safetyUb[(k,m_code)] = Ub_safe(self.origin_transfer_safetyUb[(k,m_code)], self.origin_transfer_max[(k,m_code)])
                if m_code not in v.storage.keys():
                    self.origin_transfer_open[(k,m_code)] = 0
                else:
                    self.origin_transfer_open[(k,m_code)] = v.storage[m_code]
    #                 if self.origin_transfer_open[(k,m_code)] > self.origin_transfer_max[(k,m_code)]:
    #                     self.origin_transfer_open[(k,m_code)] = self.origin_transfer_max[(k,m_code)]
                self.origin_transfer_supply[(k,m_code)] = 0
                self.demand[(k,m_code)] = 0                                 
        #读取炼厂节点
        self.refinerys = []#炼厂
        self.ori_ref_lb = []
        self.ori_ref_ub = []
        self.ori_ref = []
        self.pro_ref = []
        self.ref_sto_min = {}
        self.ref_sto_max = {}
        self.ref_sto_saftylb = {}
        self.ref_sto_saftyub = {}
        self.ref_open = {} 
        self.ratio = {}   
        self.process_ub = {}
        self.process_lb = {}
        for k,v in vertices['refinery'].items():                
            self.refinerys.append(k)        
            self.ori_ref_lb.append(v.JG_capacity['D'][0])
            self.ori_ref_ub.append(v.JG_capacity['D'][1])
            self.process_lb[k] = v.JG_capacity['D'][0]
            self.process_ub[k] = v.JG_capacity['D'][1]
            self.demand[k,'CY'] = Nan_zero((v.demand['PLDO'][0]+v.demand['PLDO'][1])/2*1.25)
            self.demand[k,'QY'] = Nan_zero((v.demand['PGLE'][0]+v.demand['PGLE'][1])/2*1.25)
            self.demand[k,'PKER'] = Nan_zero((v.demand['PKER'][0]+v.demand['PKER'][1])/2*1.25)
            self.pro_ref.append((k,'CY'))
            self.pro_ref.append((k,'QY'))
            self.pro_ref.append((k,'PKER'))

            self.ref_sto_min[(k,'JGHY')] = 0
            self.ref_sto_min[(k,'CY')] = 0
            self.ref_sto_min[(k,'QY')] = 0
            self.ref_sto_min[(k,'PKER')] = 0               
            self.ref_sto_max[(k,'JGHY')] = Ub_value(v.inventory_cap['JGHY'][0])
            self.ref_sto_max[(k,'CY')] = Ub_value(v.inventory_cap['CY'][0])
            self.ref_sto_max[(k,'QY')] = Ub_value(v.inventory_cap['QY'][0])
            self.ref_sto_max[(k,'PKER')] = 999

            self.ref_sto_saftylb[(k,'JGHY')] = 0
            self.ref_sto_saftylb[(k,'CY')] = 0
            self.ref_sto_saftylb[(k,'QY')] = 0
            self.ref_sto_saftylb[(k,'PKER')] = 0
            self.ref_sto_saftyub[(k,'JGHY')] = Ub_value(v.inventory_cap['JGHY'][1])
            self.ref_sto_saftyub[(k,'CY')] = Ub_value(v.inventory_cap['CY'][1])
            self.ref_sto_saftyub[(k,'QY')] = Ub_value(v.inventory_cap['QY'][1])
            self.ref_sto_saftyub[(k,'PKER')] = 999

            self.ref_sto_saftyub[(k,'JGHY')] = Ub_safe(self.ref_sto_saftyub[(k,'JGHY')], self.ref_sto_max[(k,'JGHY')])
            self.ref_sto_saftyub[(k,'CY')] = Ub_safe(self.ref_sto_saftyub[(k,'CY')], self.ref_sto_max[(k,'CY')])
            self.ref_sto_saftyub[(k,'QY')] = Ub_safe(self.ref_sto_saftyub[(k,'QY')], self.ref_sto_max[(k,'QY')])
            self.ref_sto_saftyub[(k,'PKER')] = Ub_safe(self.ref_sto_saftyub[(k,'PKER')], self.ref_sto_max[(k,'PKER')])

            for i,j in v.ratio.items():
                if i == 'PLDO0':
                    self.ratio[(k,'CY')] = j
                elif i == 'PGLE0':
                    self.ratio[(k,'QY')] = j
                elif i == 'PKER':
                    self.ratio[(k,'PKER')] = j

            for i,j in v.storage.items():   
                if i == 'PLDO':
                    self.ref_open[(k,'CY')] = j
                elif i == 'PGLE':
                    self.ref_open[(k,'QY')] = j
                elif i == 'JGHY':
                    self.ref_open[(k,'JGHY')] = j
                    self.ori_ref.append((k,'JGHY'))
                else:
                    self.ref_open[(k,i)] = j
            self.ref_open[(k,'PKER')] = 0

        #读取道路
        self.cost = {}
        self.product_route_lb = {}
        self.product_route_ub = {}
        id_road = {}
        roads = edges
        for k in roads.values():
            trans_upperbound = 999
            for i in range(len(k.cap_transports)):
                trans_upperbound = min(trans_upperbound, k.cap_transports[i].capacity['D'][1])
            trans_upperbound = trans_upperbound if trans_upperbound > 0 else 999
            if (k.start,k.material) in self.node_mat_supply.keys() and self.node_mat_supply[(k.start,k.material)] > trans_upperbound:
                trans_upperbound = self.node_mat_supply[(k.start,k.material)]

            if (k.material,k.start,k.end,k.mode) in id_road.keys():
                id_road[k.material,k.start,k.end,k.mode] += 1 
            else:
                id_road[k.material,k.start,k.end,k.mode] = 0     

            self.cost[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = k.cost
            self.product_route_lb[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = 0
            self.product_route_ub[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = trans_upperbound

        self.productRoute,self.p_r_lb = gp.multidict(self.product_route_lb)    
        self.productRoute,self.p_r_ub = gp.multidict(self.product_route_ub)

    def solve(self, vertices, policy_id, day, save_schedual=False):
        self.demand_N = {}
        #读取供应节点
        self.node_mat_supply = {}
        for k,v in vertices['supply'].items():
            road_num = len(v.nbr_road)
            for idx,p in enumerate(v.period):
                if day % p == 0:
                    for m_code in v.material:
                        if (k,m_code) in self.node_mat_supply.keys():
                            self.node_mat_supply[(k,m_code)] += v.quantity[idx]*road_num
                        else:
                            self.node_mat_supply[(k,m_code)] = v.quantity[idx]*road_num
        self.supplyk = self.node_mat_supply.keys()

        #更新转运节点库存
        for k,v in vertices['transfer'].items():
            for m_code,m_info in v.materials.items():
                if m_code not in v.storage.keys():
                    self.origin_transfer_open[(k,m_code)] = 0
                else:
                    self.origin_transfer_open[(k,m_code)] = v.storage[m_code]
        #更新炼厂节点库存           
        for k,v in vertices['refinery'].items():
            self.demand[k,'CY'] = Nan_zero((v.demand['PLDO'][0]+v.demand['PLDO'][1])/2*1.25)
            self.demand[k,'QY'] = Nan_zero((v.demand['PGLE'][0]+v.demand['PGLE'][1])/2*1.25)
            self.demand[k,'PKER'] = Nan_zero((v.demand['PKER'][0]+v.demand['PKER'][1])/2*1.25)
            
            for i,j in v.storage.items():   
                if i == 'PLDO':
                    self.ref_open[(k,'CY')] = j
                elif i == 'PGLE':
                    self.ref_open[(k,'QY')] = j
                elif i == 'JGHY':
                    self.ref_open[(k,'JGHY')] = j
                else:
                    self.ref_open[(k,i)] = j
            self.ref_open[(k,'PKER')] = 0
            CY_demand = self.demand[k,'CY']/self.ratio[(k,'CY')] if self.ratio[(k,'CY')] > 0 else 0
            QY_demand = self.demand[k,'QY']/self.ratio[(k,'QY')] if self.ratio[(k,'QY')] > 0 else 0
            PKER_demand = self.demand[k,'PKER']/self.ratio[(k,'PKER')] if self.ratio[(k,'PKER')] > 0 else 0
            demand_ = max(CY_demand, QY_demand, PKER_demand)
            demand_one = demand_ * 1
            self.demand_one[k,'JGHY'] = demand_one
            demand_N = demand_ * self.satisfy_N_day
            demand_N = self.ref_sto_saftyub[k,'JGHY'] if demand_N > self.ref_sto_saftyub[k,'JGHY'] else demand_N
            demand_N = self.ref_sto_saftylb[k,'JGHY'] if demand_N < self.ref_sto_saftylb[k,'JGHY'] else demand_N
            self.demand_N[k,'JGHY'] = demand_N
        rl_action = self.policy(policy_id, day, save_schedual)

        return rl_action
            
    def policy(self, policy_id, day, save_schedual):
        # 建模gurobi
        m = gp.Model("single_day_routing")    
        m.setParam('OutputFlag', False)
        
        # 路径的运输量
        flow = m.addVars(self.productRoute,lb = self.p_r_lb,ub = self.p_r_ub,vtype=GRB.CONTINUOUS,name="flow")
        # 炼厂加工量
        volum_refinery = m.addVars(self.refinerys,lb=0,ub = self.ori_ref_ub,vtype=GRB.CONTINUOUS,name = 'refinery volum')
        # 运费
        flow_cost = m.addVar(lb=-1e10,ub = 1e10,vtype=GRB.CONTINUOUS,name = 'flow cost')
        # 总运量
#         flow_total = m.addVar(lb=-1e10,ub = 1e10,vtype=GRB.CONTINUOUS,name = 'flow total')
        
        # 原油中转当天结束存储量
        originTransferNode_currentStorage = m.addVars(self.origin_transfer,lb=0,ub=999,vtype=GRB.CONTINUOUS,name='origin transfer node storage')
        # 炼厂当天结束原油存储量
        refinery_ori_currentStorage = m.addVars(self.ori_ref,lb=0,ub=999,vtype=GRB.CONTINUOUS,name='origin refinery node storage')
        # 炼厂当天结束成品油存储量
        refinery_pro_currentStorage = m.addVars(self.pro_ref,lb=-999,ub=999,vtype=GRB.CONTINUOUS,name='production refinery node storage')

        # Constraints
        #供应点流量平衡约束
        #筛选去除孤立节点
        supplyk_selected = []
        for k in self.supplyk:
            if flow.select(k[1],k[0],'*','*','*') != []:
                supplyk_selected.append(k)
        m.addConstrs(self.node_mat_supply[k] == gp.quicksum(flow.select(k[1],k[0],'*','*','*')) for k in supplyk_selected)

        # 原油分输点流量平衡约束
        m.addConstrs(gp.quicksum(flow.select(k[1],'*',k[0],'*','*'))-gp.quicksum(flow.select(k[1],k[0],'*','*','*')) == 0 for k in self.origin_distri)
        # 原油中转流量平衡约束
        m.addConstrs(originTransferNode_currentStorage[k] == self.origin_transfer_supply[k]+self.origin_transfer_open[k]+gp.quicksum(flow.select(k[1],'*',k[0],'*','*'))-gp.quicksum(flow.select(k[1],k[0],'*','*','*')) for k in self.origin_transfer)
        # 炼厂加工混油流量平衡及加工量约束
        m.addConstrs(refinery_ori_currentStorage[k] == self.ref_open[k]+flow.sum('*','*',k[0],'*','*')-volum_refinery[k[0]] for k in self.ori_ref)
        # 炼厂成品油流量平衡及加工量约束
        m.addConstrs(refinery_pro_currentStorage[k] == self.ref_open[k]+volum_refinery[k[0]]*self.ratio[k]-self.demand[k] for k in self.pro_ref)    
        # 道路运费约束
        m.addConstr(flow_cost == gp.quicksum(flow[k]*self.cost[k] for k in self.productRoute)) 
        # 道路总运量约束
#         m.addConstr(flow_total == gp.quicksum(flow[k] for k in self.productRoute))

# 根据算子设置目标
###############################################################
        P_F = 0.001
        P_T = 1
        P_R_ori = 100
        P_R_pro = 10000
        P_in = 1
        P_safe = 10
        P_out = 100
        P_demand = 1
        
        bool_PWLObj_MultiObj = policy_id % 12 < 6
        bool_Nday_SafeUb = policy_id % 6 < 3
        num_Up_Flat_Down = policy_id % 3
        
        # 分段线性 or 多目标
        if bool_PWLObj_MultiObj:
            # 运费
            m.setObjective(P_F*flow_cost)
            # 分段线性：转运节点宽松库存
            for i in self.origin_transfer:
                PWLObj_x = [self.origin_transfer_min[i],\
                             self.origin_transfer_safetyLb[i],\
                             self.origin_transfer_safetyUb[i],\
                             self.origin_transfer_max[i],\
                             999\
                            ]
                PWLObj_y = [0]*5
                PWLObj_y[0] = P_T*P_safe*(self.origin_transfer_safetyLb[i]-self.origin_transfer_min[i])
                PWLObj_y[1] = 0
                PWLObj_y[2] = 0
                PWLObj_y[3] = P_T*P_safe*(self.origin_transfer_max[i]-self.origin_transfer_safetyUb[i])
                PWLObj_y[4] = P_T*P_out*(999-self.origin_transfer_max[i]) + PWLObj_y[3]
                m.setPWLObj(originTransferNode_currentStorage[i], PWLObj_x, PWLObj_y)
            # 分段线性：炼厂
            for i in self.refinerys:
                JGHY_k = 0.1 * self.ref_open[i,'JGHY'] / (self.demand_one[i,'JGHY'] + 1e-6)
                JGHY_w = 1.0 - JGHY_k
                JGHY_w = 0.1 if JGHY_w < 0.1 else JGHY_w

                if bool_Nday_SafeUb:
                    # 分段线性：炼厂JGHY满足N天需求
                    target_sto = self.demand_N[i,'JGHY']
                else:
                    # 分段线性：炼厂JGHY全体拉高
                    target_sto = self.ref_sto_saftyub[i,'JGHY']
                
                PWLObj_x = [self.ref_sto_min[i,'JGHY'],\
                            self.ref_sto_saftylb[i,'JGHY'],\
                            target_sto,\
                            self.ref_sto_saftyub[i,'JGHY'],\
                            self.ref_sto_max[i,'JGHY'],\
                            999\
                            ]
                PWLObj_y = [0]*6
                PWLObj_y[2] = 0
                PWLObj_y[1] = P_R_ori*P_in*JGHY_w*(target_sto-self.ref_sto_saftylb[i,'JGHY'])
                PWLObj_y[3] = P_R_ori*P_in*JGHY_w*(self.ref_sto_saftyub[i,'JGHY']-target_sto)
                PWLObj_y[0] = P_R_ori*P_safe*JGHY_w*(self.ref_sto_saftylb[i,'JGHY']-self.ref_sto_min[i,'JGHY']) + PWLObj_y[1]   
                PWLObj_y[4] = P_R_ori*P_safe*JGHY_w*(self.ref_sto_max[i,'JGHY']-self.ref_sto_saftyub[i,'JGHY']) + PWLObj_y[3]
                PWLObj_y[5] = P_R_ori*P_out*JGHY_w*(999-self.ref_sto_max[i,'JGHY']) + PWLObj_y[4]
                m.setPWLObj(refinery_ori_currentStorage[i,'JGHY'], PWLObj_x, PWLObj_y)
            
                # 分段线性：炼厂成品油库存调节
                for m_code in ['QY','CY','PKER']:
                    target_sto = 0
                    if num_Up_Flat_Down == 0:
                        target_sto = self.ref_sto_saftyub[i,m_code]
                    elif num_Up_Flat_Down == 1:
                        target_sto = self.ref_open[i,m_code]
                    else:
                        target_sto = self.ref_sto_saftylb[i,m_code]
                    target_sto = self.ref_sto_saftylb[i,m_code] if target_sto < self.ref_sto_saftylb[i,m_code] else target_sto  
                    target_sto = self.ref_sto_saftyub[i,m_code] if target_sto > self.ref_sto_saftyub[i,m_code] else target_sto
                    
                    PWLObj_x = [-999,\
                                self.ref_sto_min[i,m_code],\
                                self.ref_sto_saftylb[i,m_code],\
                                target_sto,\
                                self.ref_sto_saftyub[i,m_code],\
                                self.ref_sto_max[i,m_code],\
                                999\
                                ]
                    PWLObj_y = [0]*7
                    PWLObj_y[3] = 0
                    PWLObj_y[2] = P_R_pro*P_in*(target_sto-self.ref_sto_saftylb[i,m_code])
                    PWLObj_y[4] = P_R_pro*P_in*(self.ref_sto_saftyub[i,m_code]-target_sto)
                    PWLObj_y[1] = P_R_pro*P_safe*(self.ref_sto_saftylb[i,m_code]-self.ref_sto_min[i,m_code]) + PWLObj_y[2]   
                    PWLObj_y[5] = P_R_pro*P_safe*(self.ref_sto_max[i,m_code]-self.ref_sto_saftyub[i,m_code]) + PWLObj_y[4]
                    PWLObj_y[6] = P_R_pro*P_out*(999-self.ref_sto_max[i,m_code]) + PWLObj_y[5]
                    PWLObj_y[0] = P_R_pro*P_out*P_demand*(self.ref_sto_min[i,m_code]-(-999)) + PWLObj_y[1]

                    m.setPWLObj(refinery_pro_currentStorage[i,m_code], PWLObj_x, PWLObj_y)
        else: # 多目标
            objN_cnt = 0
            m.setObjectiveN(flow_cost, index=objN_cnt, priority=0, name='obj cost')      
            # 多目标：转运节点库存
            Transfer_Storage_D_Ub = m.addVars(self.origin_transfer,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin transfer node storage D-value Ub')
            Transfer_Storage_ABS_Ub = m.addVars(self.origin_transfer,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin transfer node storage ABS Ub') 
            Transfer_Storage_D_Lb = m.addVars(self.origin_transfer,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin transfer node storage D-value Lb')
            Transfer_Storage_ABS_Lb = m.addVars(self.origin_transfer,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin transfer node storage ABS Lb') 
            for i in self.origin_transfer:
                m.addConstr(Transfer_Storage_D_Ub[i] == originTransferNode_currentStorage[i] - self.origin_transfer_safetyUb[i]) 
                m.addConstr(Transfer_Storage_ABS_Ub[i] == abs_(Transfer_Storage_D_Ub[i]))
                m.addConstr(Transfer_Storage_D_Lb[i] == self.origin_transfer_safetyLb[i] - originTransferNode_currentStorage[i])   
                m.addConstr(Transfer_Storage_ABS_Lb[i] == abs_(Transfer_Storage_D_Lb[i]))
                m.setObjectiveN(Transfer_Storage_D_Ub[i]+Transfer_Storage_ABS_Ub[i]\
                                +Transfer_Storage_D_Lb[i]+Transfer_Storage_ABS_Lb[i],\
                                index=objN_cnt, priority=1, name='obj transfer '+i[0]+' '+i[1])
                objN_cnt += 1

            # 多目标：炼厂
            Refinery_ori_D = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage D-value')  
            Refinery_ori_ABS = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage ABS')
            Refinery_pro_D = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage D-value')  
            Refinery_pro_ABS = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage ABS') 
            
            Refinery_ori_D_Ub = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage D-value Ub')  
            Refinery_ori_ABS_Ub = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage ABS Ub')
            Refinery_pro_D_Ub = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage D-value Ub')  
            Refinery_pro_ABS_Ub = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage ABS Ub') 
            
            Refinery_ori_D_Lb = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage D-value Lb')  
            Refinery_ori_ABS_Lb = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage ABS Lb')
            Refinery_pro_D_Lb = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage D-value Lb')  
            Refinery_pro_ABS_Lb = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage ABS Lb') 
            
            Refinery_ori_D_MAX = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage D-value MAX')  
            Refinery_ori_ABS_MAX = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage ABS MAX')
            Refinery_pro_D_MAX = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage D-value MAX')  
            Refinery_pro_ABS_MAX = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage ABS MAX') 
            
            Refinery_ori_D_MIN = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage D-value MIN')  
            Refinery_ori_ABS_MIN = m.addVars(self.ori_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='origin refinery node storage ABS MIN')
            Refinery_pro_D_MIN = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage D-value MIN')  
            Refinery_pro_ABS_MIN = m.addVars(self.pro_ref,lb=-9999,ub=9999,vtype=GRB.CONTINUOUS,name='pro refinery node storage ABS MAIN')
            for i in self.refinerys:
                target_sto = 0
                if bool_Nday_SafeUb:
                    # 多目标：炼厂满足N天需求
                    target_sto = self.demand_N[i,'JGHY']
                else:
                    # 多目标：炼厂库存拉高
                    target_sto = self.ref_sto_saftyub[i,'JGHY']
                
                JGHY_k = 0.1 * self.ref_open[i,'JGHY'] / (self.demand_one[i,'JGHY'] + 1e-6)
                JGHY_w = 1.0 - JGHY_k
                JGHY_w = 1.0 if JGHY_w > 1.0 else JGHY_w
                JGHY_w = 0.1 if JGHY_w < 0.1 else JGHY_w

                m.addConstr(Refinery_ori_D[i,'JGHY'] == refinery_ori_currentStorage[i,'JGHY'] - target_sto) 
                m.addConstr(Refinery_ori_ABS[i,'JGHY'] == abs_(Refinery_ori_D[i,'JGHY']))
                
                m.addConstr(Refinery_ori_D_Ub[i,'JGHY'] == refinery_ori_currentStorage[i,'JGHY'] - self.ref_sto_saftyub[i,'JGHY']) 
                m.addConstr(Refinery_ori_ABS_Ub[i,'JGHY'] == abs_(Refinery_ori_D_Ub[i,'JGHY']))
                m.addConstr(Refinery_ori_D_Lb[i,'JGHY'] == self.ref_sto_saftylb[i,'JGHY'] - refinery_ori_currentStorage[i,'JGHY']) 
                m.addConstr(Refinery_ori_ABS_Lb[i,'JGHY'] == abs_(Refinery_ori_D_Lb[i,'JGHY']))
                
                m.addConstr(Refinery_ori_D_MAX[i,'JGHY'] == refinery_ori_currentStorage[i,'JGHY'] - self.ref_sto_max[i,'JGHY']) 
                m.addConstr(Refinery_ori_ABS_MAX[i,'JGHY'] == abs_(Refinery_ori_D_MAX[i,'JGHY']))
                m.addConstr(Refinery_ori_D_MIN[i,'JGHY'] == self.ref_sto_min[i,'JGHY'] - refinery_ori_currentStorage[i,'JGHY']) 
                m.addConstr(Refinery_ori_ABS_MIN[i,'JGHY'] == abs_(Refinery_ori_D_MIN[i,'JGHY']))
                
                m.setObjectiveN(P_in * Refinery_ori_ABS[i,'JGHY']\
                                +P_safe * (Refinery_ori_D_Ub[i,'JGHY'] + Refinery_ori_ABS_Ub[i,'JGHY'])\
                                +P_safe * (Refinery_ori_D_Lb[i,'JGHY'] + Refinery_ori_ABS_Lb[i,'JGHY'])\
                                +P_out * (Refinery_ori_D_MAX[i,'JGHY'] + Refinery_ori_ABS_MAX[i,'JGHY'])\
                                +P_out * (Refinery_ori_D_MIN[i,'JGHY'] + Refinery_ori_ABS_MIN[i,'JGHY']),\
                                index=objN_cnt, weight=JGHY_w, priority=2, name='obj refinery '+i[0]+' '+i[1])  
                objN_cnt += 1
                
                # 多目标：炼厂成品油库存调节
                for m_code in ['QY','CY','PKER']:
                    target_sto = 0
                    if num_Up_Flat_Down == 0:
                        target_sto = self.ref_sto_saftyub[i,m_code]
                    elif num_Up_Flat_Down == 1:
                        target_sto = self.ref_sto_saftylb[i,m_code]
                    else:
                        target_sto = self.ref_open[i,m_code]
#                     print(i,m_code,target_sto)
                    target_sto = self.ref_sto_saftylb[i,m_code] if target_sto < self.ref_sto_saftylb[i,m_code] else target_sto    
                    target_sto = self.ref_sto_saftyub[i,m_code] if target_sto > self.ref_sto_saftyub[i,m_code] else target_sto
                    m.addConstr(Refinery_pro_D[i,m_code] == refinery_pro_currentStorage[i,m_code] - target_sto) 
                    m.addConstr(Refinery_pro_ABS[i,m_code] == abs_(Refinery_pro_D[i,m_code]))

                    m.addConstr(Refinery_pro_D_Ub[i,m_code] == refinery_pro_currentStorage[i,m_code] - self.ref_sto_saftyub[i,m_code]) 
                    m.addConstr(Refinery_pro_ABS_Ub[i,m_code] == abs_(Refinery_pro_D_Ub[i,m_code]))
                    m.addConstr(Refinery_pro_D_Lb[i,m_code] == self.ref_sto_saftylb[i,m_code] - refinery_pro_currentStorage[i,m_code]) 
                    m.addConstr(Refinery_pro_ABS_Lb[i,m_code] == abs_(Refinery_pro_D_Lb[i,m_code]))

                    m.addConstr(Refinery_pro_D_MAX[i,m_code] == refinery_pro_currentStorage[i,m_code] - self.ref_sto_max[i,m_code]) 
                    m.addConstr(Refinery_pro_ABS_MAX[i,m_code] == abs_(Refinery_pro_D_MAX[i,m_code]))
                    m.addConstr(Refinery_pro_D_MIN[i,m_code] == self.ref_sto_min[i,m_code] - refinery_pro_currentStorage[i,m_code]) 
                    m.addConstr(Refinery_pro_ABS_MIN[i,m_code] == abs_(Refinery_pro_D_MIN[i,m_code]))
                    
                    m.setObjectiveN(P_in * Refinery_pro_ABS[i,m_code]\
                                    +P_safe * (Refinery_pro_D_Ub[i,m_code] + Refinery_pro_ABS_Ub[i,m_code])\
                                    +P_safe * (Refinery_pro_D_Lb[i,m_code] + Refinery_pro_ABS_Lb[i,m_code])\
                                    +P_out * (Refinery_pro_D_MAX[i,m_code] + Refinery_pro_ABS_MAX[i,m_code])\
                                    +P_out * P_demand * (Refinery_pro_D_MIN[i,m_code] + Refinery_pro_ABS_MIN[i,m_code]),\
                                    index=objN_cnt, priority=3, name='obj refinery '+i[0]+' '+i[1])  
                    objN_cnt += 1

#######################################################

        # Set global sense for ALL objectives.
        m.modelSense=GRB.MINIMIZE
        # Optimize
        m.optimize()

        # current optimization status of the model object
        if m.status != GRB.OPTIMAL:
            print("Optimization terminated with status {}".format(m.status))
            if  m.status == GRB.INFEASIBLE:       
                m.computeIIS()
                m.write('abc.ilp')
            sys.exit(0)

        # 记录结果
        for_rl = {}
        for arc in self.productRoute:
            for_rl[arc[1]+'_'+arc[2]+'_'+arc[0]] = flow[arc].x
        
        for refinery in self.refinerys:
            for_rl[refinery] = volum_refinery[refinery].x
        
        #Analysis
        if save_schedual:
            path = './schedule/'+str(day)+'.xlsx'
            output = pd.ExcelWriter(path, mode='w')

            df = []
            for arc in self.productRoute:
                #if flow[arc].x > 1e-6:
                singleline = pd.DataFrame([[arc[0],arc[1],arc[2],arc[3],flow[arc].x]],columns=['Material',"From", "To", 'Mode',"Flow"+str(day)])
                df.append(singleline)
                
            product_flow = pd.concat(df, ignore_index=True)
            product_flow.to_excel(output,sheet_name='flow of arc')

            df = []
            for refinery in self.refinerys:
                #if volum_refinery[refinery].x > 1e-6:
                singleline = pd.DataFrame([[refinery,volum_refinery[refinery].x]],columns=['Refinary',"volum"+str(day)])
                df.append(singleline)
                    #refinaryVolum = refinaryVolum.append({'Refinary':refinery,"volum":volum_refinery[refinery].x}, ignore_index=True)
            #refinaryVolum.index=[''] * len(refinaryVolum) 
            
            refinaryVolum = pd.concat(df, ignore_index=True)
            refinaryVolum.to_excel(output,sheet_name='Processing of refinery')

            storage = {}
            storage.update(originTransferNode_currentStorage)
            storage.update(refinery_ori_currentStorage)
            storage.update(refinery_pro_currentStorage)
            ind = self.origin_transfer + self.ori_ref + self.pro_ref
            df = []
            for i in self.origin_transfer:         
                if storage[i].x < self.origin_transfer_safetyLb[i]:
                    safty_warn = storage[i].x - self.origin_transfer_safetyLb[i]
                elif storage[i].x > self.origin_transfer_safetyUb[i]:
                    safty_warn = storage[i].x - self.origin_transfer_safetyUb[i]
                else:
                    safty_warn = 0
                limit_warn = 0
                singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
                df.append(singleline) 
            for i in self.ori_ref:         
                if storage[i].x < self.ref_sto_saftylb[i]:
                    safty_warn = storage[i].x - self.ref_sto_saftylb[i]
                elif storage[i].x > self.ref_sto_saftyub[i]:
                    safty_warn = storage[i].x - self.ref_sto_saftyub[i]
                else:
                    safty_warn = 0
                limit_warn = 0
                singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
                df.append(singleline)    
            for i in self.pro_ref:         
                if storage[i].x < self.ref_sto_saftylb[i]:
                    safty_warn = storage[i].x - self.ref_sto_saftylb[i]
                elif storage[i].x > self.ref_sto_saftyub[i]:
                    safty_warn = storage[i].x - self.ref_sto_saftyub[i]
                else:
                    safty_warn = 0

                if storage[i].x < self.ref_sto_min[i]:
                    limit_warn = storage[i].x - self.ref_sto_min[i]
                elif storage[i].x > self.ref_sto_max[i]:
                    limit_warn = storage[i].x - self.ref_sto_max[i]
                else:
                    limit_warn = 0

                singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
                df.append(singleline)
            #node_storage.index=[''] * len(node_storage)
            node_storage = pd.concat(df, ignore_index=True)
            node_storage.to_excel(output,sheet_name='storage of the day')

            output.save()
            output.close()

#         obj_pro = m.ObjVal
    #     print(obj_pro,flow_cost.x,flow_total.x)
        m.dispose()
        return for_rl

# 算子详情
# 算子编号	对炼厂成品油的目标	对炼厂原油库存的目标	对转运节点的目标	优化方法	是否考虑运费
# 1	提高库存到安全线	满足5天需求	保持在安全库存内	分段线性优化	是
# 2	降低库存到安全线	满足5天需求	保持在安全库存内	分段线性优化	是
# 3	维持库存	满足5天需求	保持在安全库存内	分段线性优化	是
# 4	提高库存到安全线	提高库存到安全线	保持在安全库存内	分段线性优化	是
# 5	降低库存到安全线	提高库存到安全线	保持在安全库存内	分段线性优化	是
# 6	维持库存	提高库存到安全线	保持在安全库存内	分段线性优化	是
# 7	提高库存到安全线	满足5天需求	保持在安全库存内	多目标序列优化	是
# 8	降低库存到安全线	满足5天需求	保持在安全库存内	多目标序列优化	是
# 9	维持库存	满足5天需求	保持在安全库存内	多目标序列优化	是
# 10	提高库存到安全线	提高库存到安全线	保持在安全库存内	多目标序列优化	是
# 11	降低库存到安全线	提高库存到安全线	保持在安全库存内	多目标序列优化	是
# 12	维持库存	提高库存到安全线	保持在安全库存内	多目标序列优化	是
