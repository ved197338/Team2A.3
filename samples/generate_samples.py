import pandas as pd 
import numpy as np 

def create_messy_customer_data ():
    data ={
    " customer_id":[
    "CUST_1001","CUST_1002","CUST_1003","CUST_1004","CUST_1005",
    "CUST_1006","CUST_1007","CUST_1008","CUST_1009","CUST_1010",
    "CUST_1001",
    "CUST_1011","CUST_1012","CUST_1013","CUST_1014","CUST_1015",
    "CUST_1016","CUST_1017","CUST_1018","CUST_1019"
    ],
    "age ":[
    "25","28","29","31","250",
    "34",None ,"45","NA","38",
    "25",
    "-4","52","29","31","105",
    "42","38","999","33"
    ],
    "city":[
    "Bangalore","bangalore"," Bangalore ","BENGALURU","Mumbai",
    "mumbai","Delhi","New Delhi","kolkata","Calcutta",
    "Bangalore",
    "Chennai","Madras","Bangalore","Bengaluru","Pune",
    "pune","Mumbai","BENGALURU","Delhi"
    ],
    "email":[
    "rahul.sharma@example.com","priya_k@gmail.com","not-an-email","arun@domain","sneha.p@company.org",
    "vikram@fintech.io","","deepa.r@outlook.com","invalid@@domain.com","kavita@ai.org",
    "rahul.sharma@example.com",
    "amit.verma@tech.com","nisha@xyz.co","missing_at_symbol.com","rohit@web.net","suresh@data.gov",
    "meera@corp.in","tarun@domain.io","test_user@domain.com","pooja@cloud.ai"
    ],
    "credit_card":[
    "4532015112830366","5425233430109903","4532015112830366","4111111111111111","5500000000000004",
    "378282246310005","4532-0151-1283-0366","4012888888881881","5105105105105100","4222222222222",
    "4532015112830366",
    "5425233430109903","4111111111111111","4532015112830366","5500000000000004","378282246310005",
    "4012888888881881","5105105105105100","4222222222222","4532015112830366"
    ],
    "completion_rate":[
    85.5 ,92.0 ,78.4 ,180.0 ,64.2 ,
    99.1 ,None ,45.0 ,-15.0 ,88.0 ,
    85.5 ,
    72.3 ,91.0 ,83.5 ,100.0 ,50.0 ,
    66.7 ,89.2 ,94.0 ,79.5 
    ],
    "quantity":[
    5 ,12 ,0 ,-3 ,8 ,
    15 ,2 ,4 ,-1 ,10 ,
    5 ,
    20 ,1 ,7 ,3 ,14 ,
    9 ,6 ,11 ,2 
    ],
    "system_status":[
    "ACTIVE","ACTIVE","ACTIVE","ACTIVE","ACTIVE",
    "ACTIVE","ACTIVE","ACTIVE","ACTIVE","ACTIVE",
    "ACTIVE",
    "ACTIVE","ACTIVE","ACTIVE","ACTIVE","ACTIVE",
    "ACTIVE","ACTIVE","ACTIVE","ACTIVE"
    ],
    "legacy_notes":[
    None ,None ,None ,None ,None ,
    None ,None ,None ,None ,None ,
    None ,
    None ,None ,None ,None ,None ,
    None ,None ,None ,None 
    ]
    }
    df =pd .DataFrame (data )
    df .to_csv ("/home/april/Documents/project1/samples/messy_ai_training_data.csv",index =False )

    df_parquet =df .copy ()
    for col in df_parquet .select_dtypes (include ='object').columns :
        df_parquet [col ]=df_parquet [col ].astype (str )
    df_parquet .to_parquet ("/home/april/Documents/project1/samples/messy_ai_training_data.parquet",index =False )
    print ("Generated messy customer datasets successfully (CSV + Parquet).")

if __name__ =="__main__":
    create_messy_customer_data ()
