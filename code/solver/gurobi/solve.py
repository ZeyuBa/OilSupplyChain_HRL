# -*- coding: utf-8 -*-
"""
用于双层算法
"""
import sys
import gurobipy as gp
import numpy as np
import pandas as pd
from collections import defaultdict
from gurobipy import GRB

#Model Deployment
from common.tools import Ub_value
from common.tools import Ub_safe
from common.tools import Nan_zero


def solve(vertices, edges, storagePro, day, save_schedual=False):
    #build data structures 
    P1 = 0.1
    P2 = 1
    prosal = {'transfer':{},'refinery':{}}
    transfer_pro = []
    refinery_pro_ori = []
    refinery_pro_cpy = []
    for k in storagePro.keys():
        for n in storagePro[k]:
                if k == 'transfer':
                    for material,value in n['storage'].items():
                        prosal[k][(n['key'],material)] = value 
                        transfer_pro.append((n['key'],material))
                elif k == 'refinery': 
                    for material,value in n['storage'].items():
                        if material == 'PGLE':
                            prosal[k][(n['key'],material)] = value
                            refinery_pro_cpy.append((n['key'],material))
                        elif material == 'PLDO':
                            prosal[k][(n['key'],'CY')] = value
                            refinery_pro_cpy.append((n['key'],material))
                        elif material == 'JGHY':
                            prosal[k][(n['key'],material)] = value
                            refinery_pro_ori.append((n['key'],material))    
      

    d = vertices
    node_mat_supply = {}
    for k,v in d['supply'].items():
        road_num = len(v.nbr_road)
        for idx,p in enumerate(v.period):
            if day % p == 0:
                for i in v.material:
                    if (k,i) in node_mat_supply.keys():
                        node_mat_supply[(k,i)] += v.quantity[idx]*road_num
                    else:
                        node_mat_supply[(k,i)] = v.quantity[idx]*road_num
    supplyk = node_mat_supply.keys()         
#     node_mat_supply[('JZG','HSJK')] = 3.6
#     node_mat_supply[('JZG','HSJK')] = 7.5
    
    
    origin_distri = []#原油分输
    origin_transfer = []#原油中转库
    demand = {}
    origin_transfer_min = {}
    origin_transfer_max = {}
    origin_transfer_safetyLb = {}
    origin_transfer_safetyUb = {}
    origin_transfer_open = {}
    origin_transfer_supply = {}
#     for k,v in d['warehouse'].items():
#         if v.materials is None:
#             origin_distri.append(k)
#         else:
#             for m_code,m_info in v.materials.items():
#                 origin_transfer.append((k,m_code))
#                 origin_transfer_min[(k,m_code)] = 0
#                 origin_transfer_max[(k,m_code)] = Ub_value(m_info['inventory_cap'][0])
#                 origin_transfer_safetyLb[(k,m_code)] = 0
#                 origin_transfer_safetyUb[(k,m_code)] = Ub_value(m_info['inventory_cap'][1])
#                 origin_transfer_safetyUb[(k,m_code)] = Ub_safe(origin_transfer_safetyUb[(k,m_code)], origin_transfer_max[(k,m_code)])
#                 if m_code not in v.storage.keys():
#                     origin_transfer_open[(k,m_code)] = 0
#                 else:
#                     origin_transfer_open[(k,m_code)] = v.storage[m_code]   
                
# #                 if origin_transfer_open[(k,m_code)] > origin_transfer_max[(k,m_code)]:
# #                     origin_transfer_open[(k,m_code)] = origin_transfer_max[(k,m_code)]

#                 origin_transfer_supply[(k,m_code)] = 0
        
    
    for k,v in d['transfer'].items():
        for m_code,m_info in v.materials.items():
            if 'FSD' in k:
                origin_distri.append((k,m_code))
#             if k == 'TLYD' and m_code == 'PJLY':
#                 origin_distri.append((k,m_code))
#             else:
            origin_transfer.append((k,m_code))
            origin_transfer_min[(k,m_code)] = 0
            origin_transfer_max[(k,m_code)] = Ub_value(m_info['inventory_cap'][0])
            origin_transfer_safetyLb[(k,m_code)] = 0
            origin_transfer_safetyUb[(k,m_code)] = Ub_value(m_info['inventory_cap'][1])
            origin_transfer_safetyUb[(k,m_code)] = Ub_safe(origin_transfer_safetyUb[(k,m_code)], origin_transfer_max[(k,m_code)])
            if m_code not in v.storage.keys():
                origin_transfer_open[(k,m_code)] = 0
            else:
                origin_transfer_open[(k,m_code)] = v.storage[m_code]

#                 if origin_transfer_open[(k,m_code)] > origin_transfer_max[(k,m_code)]:
#                     origin_transfer_open[(k,m_code)] = origin_transfer_max[(k,m_code)]

            origin_transfer_supply[(k,m_code)] = 0
            demand[(k,m_code)] = 0                    
   
    transfer_pro_ex = []
    for i in origin_transfer:
        if i in transfer_pro:
            transfer_pro_ex.append(i)                 


    refinerys = []#炼厂
    ori_ref_lb = []
    ori_ref_ub = []
    ori_ref = []
    pro_ref = []
    ref_sto_min = {}
    ref_sto_max = {}
    ref_sto_saftylb = {}
    ref_sto_saftyub = {}
    ref_open = {} 
    ratio = {}        
    for k,v in d['refinery'].items():                
        refinerys.append(k)        
        ori_ref_lb.append(v.JG_capacity['D'][0])
        ori_ref_ub.append(v.JG_capacity['D'][1])
        demand[k,'CY'] = Nan_zero((v.demand['PLDO'][0]+v.demand['PLDO'][1])/2*1.25)
        demand[k,'QY'] = Nan_zero((v.demand['PGLE'][0]+v.demand['PGLE'][1])/2*1.25)
        demand[k,'PKER'] = Nan_zero((v.demand['PKER'][0]+v.demand['PKER'][1])/2*1.25)
        pro_ref.append((k,'CY'))
        pro_ref.append((k,'QY'))
        pro_ref.append((k,'PKER'))

        ref_sto_min[(k,'JGHY')] = 0
        ref_sto_min[(k,'CY')] = 0
        ref_sto_min[(k,'QY')] = 0
        ref_sto_min[(k,'PKER')] = 0               
        ref_sto_max[(k,'JGHY')] = Ub_value(v.inventory_cap['JGHY'][0])
        ref_sto_max[(k,'CY')] = Ub_value(v.inventory_cap['CY'][0])
        ref_sto_max[(k,'QY')] = Ub_value(v.inventory_cap['QY'][0])
        ref_sto_max[(k,'PKER')] = 999

        ref_sto_saftylb[(k,'JGHY')] = 0
        ref_sto_saftylb[(k,'CY')] = 0
        ref_sto_saftylb[(k,'QY')] = 0
        ref_sto_saftylb[(k,'PKER')] = 0
        ref_sto_saftyub[(k,'JGHY')] = Ub_value(v.inventory_cap['JGHY'][1])
        ref_sto_saftyub[(k,'CY')] = Ub_value(v.inventory_cap['CY'][1])
        ref_sto_saftyub[(k,'QY')] = Ub_value(v.inventory_cap['QY'][1])
        ref_sto_saftyub[(k,'PKER')] = 999
        
        ref_sto_saftyub[(k,'JGHY')] = Ub_safe(ref_sto_saftyub[(k,'JGHY')], ref_sto_max[(k,'JGHY')])
        ref_sto_saftyub[(k,'CY')] = Ub_safe(ref_sto_saftyub[(k,'CY')], ref_sto_max[(k,'CY')])
        ref_sto_saftyub[(k,'QY')] = Ub_safe(ref_sto_saftyub[(k,'QY')], ref_sto_max[(k,'QY')])
        ref_sto_saftyub[(k,'PKER')] = Ub_safe(ref_sto_saftyub[(k,'PKER')], ref_sto_max[(k,'PKER')])

        for i,j in v.ratio.items():
            if i == 'PLDO0':
                ratio[(k,'CY')] = j
            elif i == 'PGLE0':
                ratio[(k,'QY')] = j
            elif i == 'PKER':
                ratio[(k,i)] = j

        for i,j in v.storage.items():   
            if i == 'PLDO':
                ref_open[(k,'CY')] = j
            elif i == 'PGLE':
                ref_open[(k,'QY')] = j
            elif i == 'JGHY':
                ref_open[(k,'JGHY')] = j
                ori_ref.append((k,'JGHY'))
            else:
                ref_open[(k,i)] = j
        ref_open[(k,'PKER')] = 0
                      
    ori_ref_sto_min = [ref_sto_min[i] for i in ori_ref]
    ori_ref_sto_max = [ref_sto_max[i] for i in ori_ref]
    pro_ref_sto_min = [-999 for i in pro_ref]
    pro_ref_sto_max = [999 for i in pro_ref]
    #pro_ref_sto_max = [ref_sto_max[i] for i in pro_ref]
    
    
    refinery_pro_ori_ex = []
    for i in ori_ref:
        if i in refinery_pro_ori:
            refinery_pro_ori_ex.append(i)
    
    refinery_pro_cpy_ex = []
    for i in pro_ref:
        if i in refinery_pro_cpy:
            refinery_pro_cpy_ex.append(i)        
    
    cost = {}
    product_route_lb = {}
    product_route_ub = {}
    id_road = {}
    roads = edges
    for k in roads.values():
    #     print(k.key,k.cost,k.material)
        trans_upperbound = 999
        for i in range(len(k.cap_transports)):
            trans_upperbound = min(trans_upperbound, k.cap_transports[i].capacity['D'][1])
        trans_upperbound = trans_upperbound if trans_upperbound > 0 else 999
#         print(k.material,k.start,k.end,k.mode, trans_upperbound)

#         trans_upperbound = trans_upperbound if trans_upperbound<100 else 99
        if (k.material,k.start,k.end,k.mode) in id_road.keys():
            id_road[k.material,k.start,k.end,k.mode] += 1 
        else:
            id_road[k.material,k.start,k.end,k.mode] = 0     
#         print(k.start,k.end,k.material,trans_upperbound)
        cost[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = k.cost
        product_route_lb[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = 0
        product_route_ub[k.material,k.start,k.end,k.mode,id_road[k.material,k.start,k.end,k.mode]] = trans_upperbound
        if (k.start,k.material) in node_mat_supply.keys() and node_mat_supply[(k.start,k.material)] > trans_upperbound:
            node_mat_supply[(k.start,k.material)] = trans_upperbound
            

    productRoute,p_r_lb = gp.multidict(product_route_lb)    
    productRoute,p_r_ub = gp.multidict(product_route_ub)
    

    # creat model
    m = gp.Model("single_day_routing")    
    m.setParam('OutputFlag', False)
    #m.setParam('NonConvex', 2)
    
#     print(origin_transfer_max)
    # Initialize assignment decision variables.
    # 路径的运输量
    flow = m.addVars(productRoute,lb = p_r_lb,ub = p_r_ub,vtype=GRB.CONTINUOUS,name="flow")
    # 炼厂加工量
    volum_refinery = m.addVars(refinerys,lb=ori_ref_lb,ub = ori_ref_ub,vtype=GRB.CONTINUOUS,name = 'refinery volum')
    flow_cost = m.addVar(lb=-1e10,ub = 1e10,vtype=GRB.CONTINUOUS,name = 'flow cost')
    
    flow_total = m.addVar(lb=-1e10,ub = 1e10,vtype=GRB.CONTINUOUS,name = 'flow total')
    #supplyNode_currentStorage = m.addVars(supplypro,lb=supplyNode_bottomCapacity,ub=supplyNode_topCapacity,name='supply node storage' )
    
    # Auxiliary variables
    # 原油中转当天结束存储量
#     originTransferNode_currentStorage = m.addVars(origin_transfer,lb=origin_transfer_min,ub=origin_transfer_max,vtype=GRB.CONTINUOUS,name='origin transfer node storage')
    originTransferNode_currentStorage = m.addVars(origin_transfer,lb=0,ub=999,vtype=GRB.CONTINUOUS,name='origin transfer node storage')
    # 炼厂当天结束原油存储量
#     refinery_ori_currentStorage = m.addVars(ori_ref,lb=ori_ref_sto_min,ub=ori_ref_sto_max,vtype=GRB.CONTINUOUS,name='origin refinery node storage')
    refinery_ori_currentStorage = m.addVars(ori_ref,lb=-999,ub=999,vtype=GRB.CONTINUOUS,name='origin refinery node storage')
    # 炼厂当天结束成品油存储量
#     refinery_pro_currentStorage = m.addVars(pro_ref,lb=pro_ref_sto_min,ub=pro_ref_sto_max,vtype=GRB.CONTINUOUS,name='production refinery node storage')
    refinery_pro_currentStorage = m.addVars(pro_ref,lb=-999,ub=999,vtype=GRB.CONTINUOUS,name='production refinery node storage')
    #manufacNode_diePro_currentStorage = m.addVars(dieProNode_manufac,lb=diemanufNode_bottomCapacity,ub=diemanufNode_topCapacity,name='die manufacture node storage')
#     print(gp.quicksum(originTransferNode_currentStorage.select(k[1],'*')) for k in origin_transfer)
      
    # Constraints
    #供应点流量平衡约束
    supplyk_selected = []
    for k in supplyk:
        if flow.select(k[1],k[0],'*','*','*') != []:
            supplyk_selected.append(k)
    
    m.addConstrs(node_mat_supply[k] == gp.quicksum(flow.select(k[1],k[0],'*','*','*')) for k in supplyk_selected)

    # 原油分输点流量平衡约束
    m.addConstrs(gp.quicksum(flow.select(k[1],'*',k[0],'*','*'))-gp.quicksum(flow.select(k[1],k[0],'*','*','*')) == 0 for k in origin_distri)

    # 原油中转流量平衡约束
    m.addConstrs(originTransferNode_currentStorage[k] == origin_transfer_supply[k]+origin_transfer_open[k]+gp.quicksum(flow.select(k[1],'*',k[0],'*','*'))-gp.quicksum(flow.select(k[1],k[0],'*','*','*')) for k in origin_transfer)
    

    #m.addConstrs(originTransferNode_currentStorage[k] == origin_transfer_open[k]+flow.sum(k[1],'*',k[0],'*','*')-flow.sum(k[1],k[0],'*','*','*') for k in origin_transfer)   
    # 炼厂加工混油流量平衡及加工量约束
    m.addConstrs(refinery_ori_currentStorage[k] == ref_open[k]+flow.sum('*','*',k[0],'*','*')-volum_refinery[k[0]] for k in ori_ref)
    # 炼厂成品油流量平衡及加工量约束
    m.addConstrs(refinery_pro_currentStorage[k] == ref_open[k]+volum_refinery[k[0]]*ratio[k]-demand[k] for k in pro_ref)    
    
    #m.addConstrs(manufacNode_diePro_currentStorage[k] == node_initialStorage[k]+volum_manfac[k[0]]*node_processRate[k]-node_demand[k] for k in dieProNode_manufac)
    
    m.addConstr(flow_cost == gp.quicksum(flow[k]*cost[k] for k in productRoute)) 
    
    m.addConstr(flow_total == gp.quicksum(flow[k] for k in productRoute))
    
    # Set up primary objective.
    # 默认运输量成本
#     m.setObjective(0.01*flow_cost)    
    m.setObjective(P1*flow_total)
    # 超过存储安全线的惩罚成本
    #for i in supplypro:
    #    m.setPWLObj(supplyNode_currentStorage[i],[node_bottomCapacity[i],node_saftyLb[i],node_saftyUb[i],node_topCapacity[i]], [100*(node_saftyLb[i]-node_bottomCapacity[i]),0,0,100*(node_topCapacity[i]-node_saftyUb[i])])
##########
#     for i in origin_transfer:
#         m.setPWLObj(originTransferNode_currentStorage[i],[-1000,0,origin_transfer_min[i],origin_transfer_safetyLb[i],origin_transfer_safetyUb[i],origin_transfer_max[i],1000], 
#                     [3*P1*1000,2*P1*(origin_transfer_min[i]-0),P1*(origin_transfer_safetyLb[i]-origin_transfer_min[i]),0,0,P1*(origin_transfer_max[i]-origin_transfer_safetyUb[i]),2*P1*(1000-origin_transfer_max[i])])
#     for i in ori_ref:
#         m.setPWLObj(refinery_ori_currentStorage[i],[-1000,0,ref_sto_min[i],ref_sto_saftylb[i],ref_sto_saftyub[i],ref_sto_max[i],1000], 
#                     [3*P1*1000,2*P1*(ref_sto_min[i]-0),P1*(ref_sto_saftylb[i]-ref_sto_min[i]),0,0,P1*(ref_sto_max[i]-ref_sto_saftyub[i]),2*P1*(1000-ref_sto_max[i])])
#     for i in pro_ref:
#         m.setPWLObj(refinery_pro_currentStorage[i],[-1000,0,ref_sto_min[i],ref_sto_saftylb[i],ref_sto_saftyub[i],ref_sto_max[i],1000],
#                     [3*P1*1000,2*P1*(ref_sto_min[i]-0),P1*(ref_sto_saftylb[i]-ref_sto_min[i]),0,0,P1*(ref_sto_max[i]-ref_sto_saftyub[i]),2*P1*(1000-ref_sto_max[i])])
#############
    #for i in dieProNode_manufac:
    #    m.setPWLObj(manufacNode_diePro_currentStorage[i],[node_bottomCapacity[i],node_saftyLb[i],node_saftyUb[i],node_topCapacity[i]], [100*(node_saftyLb[i]-node_bottomCapacity[i]),0,0,100*(node_topCapacity[i]-node_saftyUb[i])])
    
    # 与存储建议差值的惩罚

    # 计算实际库存建议
    for i in transfer_pro_ex:
        target_storage = prosal['transfer'][i]*(origin_transfer_max[i] - origin_transfer_min[i]) + origin_transfer_min[i]
#         print(target_storage)
        m.setPWLObj(originTransferNode_currentStorage[i],[-999,origin_transfer_min[i],target_storage,origin_transfer_max[i],999], 
                    [P2*(origin_transfer_min[i]-(-999)),P2*(target_storage-origin_transfer_min[i]),0,P2*(origin_transfer_max[i]-target_storage),P2*(999-origin_transfer_max[i])])
#     print(ref_sto_max)
    for i in refinery_pro_ori_ex:
        target_storage = prosal['refinery'][i]*(ref_sto_max[i] - ref_sto_min[i]) + ref_sto_min[i]
#         print(target_storage)
        m.setPWLObj(refinery_ori_currentStorage[i],[-999,ref_sto_min[i],target_storage,ref_sto_max[i],999], 
                    [P2*(ref_sto_min[i]-(-999)),P2*(target_storage-ref_sto_min[i]),0,P2*(ref_sto_max[i]-target_storage),P2*(999-ref_sto_max[i])])
    for i in refinery_pro_cpy_ex:
        target_storage = prosal['refinery'][i]*(ref_sto_max[i] - ref_sto_min[i]) + ref_sto_min[i]
#         print(target_storage)
        m.setPWLObj(refinery_pro_currentStorage[i],[-999,ref_sto_min[i],target_storage,ref_sto_max[i],999],
                    [P2*(ref_sto_min[i]-(-999)),P2*(target_storage-ref_sto_min[i]),0,P2*(ref_sto_max[i]-target_storage),P2*(999-ref_sto_max[i])])    
    
        
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
    
    for_rl = {}
    #Analysis
    if save_schedual:
        path = './schedule/'+str(day)+'.xlsx'
        output = pd.ExcelWriter(path, mode='w')
    
    df = []
    for arc in productRoute:
        #if flow[arc].x > 1e-6:
        singleline = pd.DataFrame([[arc[0],arc[1],arc[2],arc[3],flow[arc].x]],columns=['Material',"From", "To", 'Mode',"Flow"+str(day)])
        df.append(singleline)
        for_rl[arc[1]+'_'+arc[2]+'_'+arc[0]] = flow[arc].x
    if save_schedual:
        product_flow = pd.concat(df, ignore_index=True)
        product_flow.to_excel(output,sheet_name='flow of arc')
    
    

    df = []
    for refinery in refinerys:
        #if volum_refinery[refinery].x > 1e-6:
        singleline = pd.DataFrame([[refinery,volum_refinery[refinery].x]],columns=['Refinary',"volum"+str(day)])
        df.append(singleline)
        for_rl[refinery] = volum_refinery[refinery].x
            #refinaryVolum = refinaryVolum.append({'Refinary':refinery,"volum":volum_refinery[refinery].x}, ignore_index=True)
    #refinaryVolum.index=[''] * len(refinaryVolum) 
    if save_schedual:     
        refinaryVolum = pd.concat(df, ignore_index=True)
        refinaryVolum.to_excel(output,sheet_name='Processing of refinery')
    
    
    storage = {}
    storage.update(originTransferNode_currentStorage)
    storage.update(refinery_ori_currentStorage)
    storage.update(refinery_pro_currentStorage)
    ind = origin_transfer + ori_ref + pro_ref
    df = []
    for i in origin_transfer:         
        if storage[i].x < origin_transfer_safetyLb[i]:
            safty_warn = storage[i].x - origin_transfer_safetyLb[i]
        elif storage[i].x > origin_transfer_safetyUb[i]:
            safty_warn = storage[i].x - origin_transfer_safetyUb[i]
        else:
            safty_warn = 0
        limit_warn = 0
        singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
        df.append(singleline) 
    for i in ori_ref:         
        if storage[i].x < ref_sto_saftylb[i]:
            safty_warn = storage[i].x - ref_sto_saftylb[i]
        elif storage[i].x > ref_sto_saftyub[i]:
            safty_warn = storage[i].x - ref_sto_saftyub[i]
        else:
            safty_warn = 0
        limit_warn = 0
        singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
        df.append(singleline)    
    for i in pro_ref:         
        if storage[i].x < ref_sto_saftylb[i]:
            safty_warn = storage[i].x - ref_sto_saftylb[i]
        elif storage[i].x > ref_sto_saftyub[i]:
            safty_warn = storage[i].x - ref_sto_saftyub[i]
        else:
            safty_warn = 0
            
        if storage[i].x < ref_sto_min[i]:
            limit_warn = storage[i].x - ref_sto_min[i]
        elif storage[i].x > ref_sto_max[i]:
            limit_warn = storage[i].x - ref_sto_max[i]
        else:
            limit_warn = 0
            
        singleline = pd.DataFrame([[i[1],i[0],storage[i].x,safty_warn,limit_warn]],columns=['Material',"Node", "Storage"+str(day),'safty_warn'+str(day),'limit_warn'+str(day)])                    
        df.append(singleline)
    #node_storage.index=[''] * len(node_storage)
    if save_schedual:
        node_storage = pd.concat(df, ignore_index=True)
        node_storage.to_excel(output,sheet_name='storage of the day')

    if save_schedual:
        output.save()
        output.close()
    
    
    #print solution
#     if m.status == GRB.OPTIMAL:   
    obj_pro = m.ObjVal
#     print(obj_pro,flow_cost.x,flow_total.x)
    m.dispose()
    return for_rl, obj_pro   
        
        
            
def printScen(scenStr):
    sLen = len(scenStr)
    print("\n" + "*"*sLen + "\n" + scenStr + "\n" + "*"*sLen + "\n")
    
    
'''if __name__ == "__main__":
    try:
        roads,supply,nodeStorage,nodes,process_rate,demand = inputData()
        printScen("inputing data successfully.")
        solve_initial(roads,supply,nodeStorage,nodes,process_rate,demand)
        printScen("solving model successfully.")
        #printScen("result display.")
        #printingResult(flow,volumFac,supN_curS,oriTraN_curS,oriFacN_curS,gasFacN_curS,dieFacN_curS)
        
        
    except gp.GurobiError as e:
        print('Error code ' + str(e.errno) + ": " + str(e))
    except AttributeError:
        print('Encountered an attribute error')'''



