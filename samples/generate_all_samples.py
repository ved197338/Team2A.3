import os 
import json 
import pandas as pd 
import numpy as np 

OUTPUT_DIR ="/home/april/Documents/project1/samples"
os .makedirs (OUTPUT_DIR ,exist_ok =True )


customers ={
" customer_id ":["C101","C102","C103","C104","C105","C101","C106","C107","C108","C109"],
"age":[25 ,"28",250 ,None ,"31",25 ,-5 ,42 ,"NA",38 ],
"email":["arun@example.com","priya@domain.org","bad-email","","suresh@corp.com","arun@example.com","user@@mail.com","neha@web.net","kavita@co.in","raj@tech.io"],
"city":["Bangalore","bangalore"," Bangalore ","BENGALURU","Mumbai","Bangalore","mumbai","Delhi","New Delhi","Pune"],
"credit_card":["4532015112830366","5425233430109903","4111111111111111","378282246310005","4532015112830366","4532015112830366","5105105105105100","4012888888881881","4222222222222","5500000000000004"],
"completion_pct":[85.5 ,92.0 ,180.0 ,75.0 ,None ,85.5 ,-10.0 ,100.0 ,64.0 ,88.0 ],
"quantity":[5 ,12 ,-2 ,8 ,14 ,5 ,0 ,9 ,3 ,11 ],
"status":["ACTIVE"]*10 
}
df_cust =pd .DataFrame (customers )
df_cust .to_csv (os .path .join (OUTPUT_DIR ,"messy_customers.csv"),index =False )


products ={
"product_id":["P-01","P-02","P-03","P-04","P-05","P-02"],
"title":["Wireless Mouse"," mechanical keyboard ","USB Cable","Monitor 27 inch","Laptop Stand"," mechanical keyboard "],
"category":["Electronics","electronics","ELECTRONICS","Hardware","Accessories","electronics"],
"price":[29.99 ,"89.50",12.00 ,249.99 ,34.50 ,"89.50"],
"stock":[150 ,45 ,-5 ,20 ,0 ,45 ]
}
df_prod =pd .DataFrame (products )
df_prod .to_csv (os .path .join (OUTPUT_DIR ,"messy_products.tsv"),sep ="\t",index =False )


orders =[
{"order_id":"ORD-101","customer":"John Doe","amount":120.50 ,"status":"completed","items":2 },
{"order_id":"ORD-102","customer":" Jane Smith ","amount":"45.00","status":"COMPLETED","items":1 },
{"order_id":"ORD-103","customer":"Bob Wilson","amount":None ,"status":"pending","items":-1 },
{"order_id":"ORD-101","customer":"John Doe","amount":120.50 ,"status":"completed","items":2 },
{"order_id":"ORD-104","customer":"Alice Brown","amount":350.00 ,"status":"cancelled","items":4 }
]
with open (os .path .join (OUTPUT_DIR ,"messy_orders.json"),"w")as f :
    json .dump (orders ,f ,indent =2 )


with open (os .path .join (OUTPUT_DIR ,"messy_logs.jsonl"),"w")as f :
    f .write ('{"timestamp": "2026-09-27 10:00:00", "level": "INFO", "user_id": "U1", "ip": "192.168.1.1", "resp_ms": 12}\n')
    f .write ('{"timestamp": "2026-09-27 10:00:01", "level": "info", "user_id": "U2", "ip": "192.168.1.2", "resp_ms": "18"}\n')
    f .write ('{"timestamp": "2026-09-27 10:00:02", "level": "ERROR", "user_id": "U3", "ip": "unknown", "resp_ms": 1500}\n')
    f .write ('{"timestamp": "2026-09-27 10:00:00", "level": "INFO", "user_id": "U1", "ip": "192.168.1.1", "resp_ms": 12}\n')


df_cust_parquet =df_cust .copy ()
for col in df_cust_parquet .columns :
    df_cust_parquet [col ]=df_cust_parquet [col ].astype (str )
df_cust_parquet .to_parquet (os .path .join (OUTPUT_DIR ,"messy_metrics.parquet"),index =False )


df_prod_feather =df_prod .copy ()
for col in df_prod_feather .columns :
    df_prod_feather [col ]=df_prod_feather [col ].astype (str )
df_prod_feather .to_feather (os .path .join (OUTPUT_DIR ,"messy_inventory.feather"))


with pd .ExcelWriter (os .path .join (OUTPUT_DIR ,"messy_accounts.xlsx"),engine ='openpyxl')as writer :
    df_cust .to_excel (writer ,sheet_name ="Customers",index =False )
    df_prod .to_excel (writer ,sheet_name ="Products",index =False )

print ("Generated all real-world sample datasets in CSV, TSV, JSON, JSONL, Parquet, Feather, and XLSX.")
