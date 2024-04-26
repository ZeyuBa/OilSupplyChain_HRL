from distutils.command.config import config
import json
from platform import node
from numpy import NaN
import pandas as pd
import pickle

def Ub_value(v):
    v = 999 if v>=999 else v
    v = 999 if v<0 else v
    v = 999 if not(v<0) and not(v>0) and not(v==0) else v
    return v

def Ub_safe(safe,ub):
    return ub if safe>ub else safe

def Nan_zero(v):
    v = 0 if not(v<0) and not(v>0) and not(v==0) else v
    return v

def save_render(data, path="./render_data.pkl"):
    with open(path, 'wb') as f:
        pickle.dump(data, f)


def load_json_config(file_path):
    with open(file_path, 'r') as f:
        config = json.load(f)
    return config

import os
def load_sys_config(file_path, model_id):
    configs = {}
    n_vertices = []
    # 所有节点名称
    nodes = pd.read_excel(file_path + 's_info_nodes.xlsx')
    nodes = nodes[nodes.model_id == model_id]
    configs['nodes'] = load_nodes(nodes)

    # 油田节点
    supply = pd.read_excel(file_path + 's_run_supply.xlsx')
    supply = supply[supply.model_id == model_id]
    configs['supply'] = load_supply(supply, configs)

    inventory = pd.read_excel(file_path + 's_run_inventory.xlsx')
    inventory = inventory[inventory.model_id == model_id]
    capInventory = pd.read_excel(file_path + 's_run_capInventory.xlsx')
    capInventory = capInventory[capInventory.model_id == model_id]
    capacityrows = pd.read_excel(file_path + 's_run_capacityrows.xlsx')
    capacityrows = capacityrows[capacityrows.model_id == model_id]

    # 中转节点
    configs['transfer'] = load_transfer(inventory, capInventory, capacityrows, configs)

    # 加工方案
    recipe = pd.read_excel(file_path + 's_run_recipe.xlsx')
    recipe = recipe[recipe.model_id == model_id]

    # 炼厂
    configs['refinery'] = load_refinery(inventory, capInventory, capacityrows, recipe, configs)

    # 需求
    demand = pd.read_excel(file_path + 's_run_demand.xlsx')
    demand = demand[demand.model_id == model_id]
    configs['demand'] = load_demand(demand, configs)

    # 商储节点
    configs['warehouse'] = load_warehouse(inventory, capacityrows, configs)
    
    transport = pd.read_excel(file_path + 's_run_transport.xlsx')
    transport = transport[transport.model_id == model_id]
    capTrans = pd.read_excel(file_path + 's_run_capTransport.xlsx')
    capTrans = capTrans[capTrans.model_id == model_id]

    # 运输网络
    configs['transport'] = load_transport(transport, capTrans, configs)
    configs['cap_transport'] = load_capTransport(capacityrows)

    # 油种
    material_member = pd.read_excel(file_path + 's_info_materialMember.xlsx')
    material_member = material_member[material_member.model_id == model_id]
    configs['material_member'] = load_material_member(material_member)

    n_vertices.append(len(configs['transfer']))

    configs['n_vertices'] = n_vertices
    configs['nodes'] = {}

    return configs


def load_nodes(df):
    config = {'supply': [], 'transfer': [], 'refinery': [], 'warehouse': [], 'others': []}
    for i in range(df.shape[0]):
        if df.iloc[i, 4] == '油气田企业' or df.iloc[i, 4] == '口岸':
            config['supply'].append(df.iloc[i, 2])
        elif df.iloc[i, 4] == '管道原油库' or df.iloc[i, 4] == '原油分输点':
            config['transfer'].append(df.iloc[i, 2])
        elif df.iloc[i, 4] == '炼化企业' and df.iloc[i, 2] != 'GDSH':
            config['refinery'].append(df.iloc[i, 2])
        elif df.iloc[i, 4] == '原油商储库':
            config['warehouse'].append(df.iloc[i, 2])
        else:
            config['others'].append(df.iloc[i, 2])
    return config


def load_supply(df, conf):
    configs = []
    for node_code in conf['nodes']['supply']:
        supply = df[df.node_code == node_code]
        config = {
            'node_code': node_code,
            'material_code': [supply.iloc[0, 2]],
            'period': [],
            'quantity': [],  # 每个周期的supply（min=max）
        }
        for i in range(supply.shape[0]):
            if supply.iloc[i, 6] == 'any':
                config['period'].append(1)
            else:
                config['period'].append(int(supply.iloc[i, 6][1:]))
            config['quantity'].append(supply.iloc[i, 8])
        configs.append(config)

    '''# 特殊处理
    ndf =  df[df.node_code == 'SINOPEC']
    config = {
            'node_code' : 'SINOPEC',
            'material_code' : [],
            'period' : [],
            'min' : [],
            'max' : [],
            'cost' : []
        }
    for i in range(ndf.shape[0]):
        config['material_code'].append(ndf.iloc[i, 2])
        if ndf.iloc[i, 6] == 'any':
            config['period'].append(1)
        else:
            config['period'].append(int(ndf.iloc[i,6][1:]))
        config['min'].append(ndf.iloc[i,8])
        config['max'].append(ndf.iloc[i,9])
        config['cost'].append(ndf.iloc[i,10])'''

    return configs


def load_transfer(df_inv, df_capInv, df_caprows, conf):
    configs = []
    for node_code in conf['nodes']['transfer']:
        config = {
            'node_code': node_code,
            'material': {},
            'inventory_cap': [999, 999], # max, safe_max
        }
        ndf_capInv = df_capInv[df_capInv.node_code == node_code]
        for i in range(ndf_capInv.shape[0]):
            capacity_code = ndf_capInv.iloc[i, 2]
            ndf_caprows = df_caprows[df_caprows.capacity_code == capacity_code]
            config['inventory_cap'][0] = 999 if pd.isnull(ndf_caprows.iloc[0, 9]) else float(ndf_caprows.iloc[0, 9])
            config['inventory_cap'][1] = 999 if pd.isnull(ndf_caprows.iloc[0, 12]) else float(ndf_caprows.iloc[0, 12])

        ndf_inv = df_inv[df_inv.node_code == node_code]
        for i in range(ndf_inv.shape[0]):
            mat_config = {
                'open': float(ndf_inv.iloc[i, 8]),
                'inventory_cap': [999 if pd.isnull(float(ndf_inv.iloc[i, 11])) else float(ndf_inv.iloc[i, 11]), 
                999 if pd.isnull(float(ndf_inv.iloc[i, 16])) else float(ndf_inv.iloc[i, 16])]
            }
            config['material'][ndf_inv.iloc[i, 2]] = mat_config
        configs.append(config)
    return configs


def load_refinery(df_inv, df_capInv, df_caprows, df_recipe, conf):
    configs = []
    for node_code in conf['nodes']['refinery']:
        config = {
            'node_code': node_code,
            'JY_recipe': [],
            'JG_capacity': {},
            'JG_recipe': {},
            'inventory_cap': {
                'JGHY': [999, 999]  # max, safe_max
            },
            'open': {}
        }
        # recipe
        ndf_recipe = df_recipe[df_recipe.node_code == node_code]
        for i in range(ndf_recipe.shape[0]):
            if ndf_recipe.iloc[i, 2][6] == 'Y' and int(ndf_recipe.iloc[i, 10]) != -1:
                config['JY_recipe'].append(ndf_recipe.iloc[i, 8])
            if ndf_recipe.iloc[i, 2][6] == 'G' and float(ndf_recipe.iloc[i, 10]) != 1:
                config['JG_recipe'][ndf_recipe.iloc[i, 8]] = -float(ndf_recipe.iloc[i, 10])
        ndf_inv = df_inv[df_inv.node_code == node_code]
        # max
        config['inventory_cap']['JGHY'][0] = ndf_inv[ndf_inv.material_code == 'JGHY'].iloc[0, 11]
        config['inventory_cap']['JGHY'][1] = ndf_inv[ndf_inv.material_code == 'JGHY'].iloc[0, 16]
        # capacity and max
        ndf_caprows = df_caprows[df_caprows.node_code == node_code]
        for i in range(ndf_caprows.shape[0]):
            if ndf_caprows.iloc[i, 2][:6] == 'CASE_D':
                config['JG_capacity']['D'] = [float(ndf_caprows.iloc[i, 8]), float(ndf_caprows.iloc[i, 9])]
            elif ndf_caprows.iloc[i, 2][:6] == 'CASE_M':
                config['JG_capacity']['M'] = [ndf_caprows.iloc[i, 8], ndf_caprows.iloc[i, 9]]
            elif ndf_caprows.iloc[i, 2][:2] == 'KC' and (
                    ndf_caprows.iloc[i, 2][-2:] == 'QY' or ndf_caprows.iloc[i, 2][-2:] == 'CY'):
                config['inventory_cap'][ndf_caprows.iloc[i, 2][-2:]] = [float(ndf_caprows.iloc[i, 9])]
                config['inventory_cap'][ndf_caprows.iloc[i, 2][-2:]].append(float(ndf_caprows.iloc[i, 12]))
        # open
        for i in range(ndf_inv.shape[0]):
            config['open'][ndf_inv.iloc[i, 2]] = float(ndf_inv.iloc[i, 8])
        configs.append(config)
    return configs


def load_demand(df, conf):
    configs = {}
    for i in range(df.shape[0]):
        node_code = df.iloc[i, 4]
        if node_code in conf['nodes']['others']:
            continue
        if node_code not in configs.keys():
            configs[node_code] = {}
        configs[node_code][df.iloc[i, 2]] = [0 if pd.isnull(df.iloc[i, 8]) else float(df.iloc[i, 8]),
                                             999 if pd.isnull(df.iloc[i, 9]) else float(df.iloc[i, 9]),
                                             float(df.iloc[i, 10])]
    return configs


def load_warehouse(df_inv, df_caprows, conf):
    configs = []
    for node_code in conf['nodes']['warehouse']:
        ndf_caprows = df_caprows[df_caprows.node_code == node_code]
        config = {
            'node_code' : node_code,
            'material' : {},
            'inventory_cap' : [999 if (ndf_caprows.shape[0] == 0 or pd.isnull(ndf_caprows.iloc[0, 9])) else pd.isnull(ndf_caprows.iloc[0, 9]), 999 if (ndf_caprows.shape[0] == 0 or pd.isnull(ndf_caprows.iloc[0, 12])) else pd.isnull(ndf_caprows.iloc[0, 12])]
        }
        ndf_inv = df_inv[df_inv.node_code == node_code]
        for i in range(ndf_inv.shape[0]):
            mat_config = {
                'open' : float(ndf_inv.iloc[i, 8]),
                'cost' : float(ndf_inv.iloc[i, 9]),
                'inventory_cap' : [999 if pd.isnull(ndf_inv.iloc[i, 11]) else float(ndf_inv.iloc[i, 11]), 999 if pd.isnull(ndf_inv.iloc[i, 16]) else float(ndf_inv.iloc[i, 16])],
            }
            config['material'][ndf_inv.iloc[i, 2]] = mat_config
        
        configs.append(config)
    return configs


def load_transport(df_trans, df_capTrans, conf):
    configs = []
    for i in range(df_trans.shape[0]):
        if df_trans.iloc[i, 4] in conf['nodes']['others'] or df_trans.iloc[i, 6] in conf['nodes']['others']:
            continue
        config = {
            'from_code': df_trans.iloc[i, 4],
            'to_code': df_trans.iloc[i, 6],
            'material_code': df_trans.iloc[i, 2],
            'mode_code': df_trans.iloc[i, 8],
            'cost': df_trans.iloc[i, 14],
            'cap_transport': []
        }
        ndf_capTrans = df_capTrans[
            (df_capTrans.from_code == df_trans.iloc[i, 4]) & (df_capTrans.to_code == df_trans.iloc[i, 6]) & (df_capTrans.material_code == df_trans.iloc[i, 2])]
        for j in range(ndf_capTrans.shape[0]):
            if ndf_capTrans.iloc[j, 2][-2:] != '_D':
                config['cap_transport'].append(ndf_capTrans.iloc[j, 2])
        configs.append(config)
    return configs

def load_capTransport(df_caprows):
    configs = []
    for i in range(df_caprows.shape[0]):
        if df_caprows.iloc[i, 2][:2] == 'PZ' or  df_caprows.iloc[i, 2][:2] == 'YS':
            if df_caprows.iloc[i, 2][-2:] != '_D':
                config = {
                    'cap_code': df_caprows.iloc[i, 2],
                    'transport_capacity': {
                        'D': [0 if pd.isnull(df_caprows.iloc[i, 8]) else float(df_caprows.iloc[i, 8]), 999 if pd.isnull(df_caprows.iloc[i, 9]) else float(df_caprows.iloc[i, 9])],  # min, max
                        'M': [0, 999],  # min, max
                    }
                }
            else:
                config['transport_capacity']['M'] = [0 if pd.isnull(df_caprows.iloc[i, 8]) else float(df_caprows.iloc[i, 8]), 999 if pd.isnull(df_caprows.iloc[i, 9]) else float(df_caprows.iloc[i, 9])],
            configs.append(config)
    return configs


def load_material_member(df):
    config = {}
    for i in range(df.shape[0]):
        config[df.iloc[i, 4]] = df.iloc[i, 2]
    return config

