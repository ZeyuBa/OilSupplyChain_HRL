import pandas as pd
day=30
def merge_data(sheet_name,col,output):
    df_merge=pd.read_excel(io='./schedule/1.xlsx',sheet_name=sheet_name).iloc[:,1:]
    for i in range(1,day): 
        df=pd.read_excel(io='./schedule/'+str(i+1)+'.xlsx',sheet_name=sheet_name).iloc[:,1:]
        df_merge=pd.merge(df_merge,df,on=col,how='outer')
    df_merge.to_excel(output,sheet_name=sheet_name)

def merge_schedule():
    output = pd.ExcelWriter('./schedule.xlsx')
    columns=[["Material","From", "To", "Mode"],['Refinary'],['Material',"Node"]]
    sheet_names=['flow of arc','Processing of refinery','storage of the day']
    for sheet_name,col in zip(sheet_names,columns):
        merge_data(sheet_name,col,output)
    output.save()
    output.close()