import os 
from reportlab .lib .pagesizes import letter 
from reportlab .platypus import SimpleDocTemplate ,Paragraph ,Spacer ,Table ,TableStyle 
from reportlab .lib .styles import getSampleStyleSheet 
from reportlab .lib import colors 

pdf_path ="/home/april/Documents/project1/samples/messy_report.pdf"
doc =SimpleDocTemplate (pdf_path ,pagesize =letter )
elements =[]
styles =getSampleStyleSheet ()

elements .append (Paragraph ("Quarterly Account Verification Report",styles ['Title']))
elements .append (Spacer (1 ,12 ))
elements .append (Paragraph ("This document contains extracted customer verification and transaction details.",styles ['Normal']))
elements .append (Spacer (1 ,16 ))

table_data =[
["customer_id","full_name","country","card_number","status"],
["C101","john smith","india","4532015112830366","ACTIVE"],
["C102","Jane Doe","India","5425233430109903","ACTIVE"],
["C103","RAHUL","IN","4111111111111111","PENDING"],
["C101","john smith","india","4532015112830366","ACTIVE"],
["C104","Alice Brown","USA","378282246310005","ACTIVE"]
]

t =Table (table_data )
t .setStyle (TableStyle ([
('BACKGROUND',(0 ,0 ),(-1 ,0 ),colors .whitesmoke ),
('GRID',(0 ,0 ),(-1 ,-1 ),1 ,colors .black ),
('TEXTCOLOR',(0 ,0 ),(-1 ,0 ),colors .black ),
('FONTNAME',(0 ,0 ),(-1 ,0 ),'Helvetica-Bold'),
('BOTTOMPADDING',(0 ,0 ),(-1 ,0 ),6 ),
]))

elements .append (t )
doc .build (elements )
print ("Generated sample PDF at:",pdf_path )
