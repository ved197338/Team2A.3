import csv 
import io 
import json 
import os 
from typing import Any ,Dict ,List ,Optional ,Tuple 
import pandas as pd 
import defusedxml .ElementTree as ET 
import pdfplumber 

from engine .security import MAX_ROWS ,MAX_COLUMNS 

def detect_text_delimiter (sample_text :str )->str :
    try :
        sniffer =csv .Sniffer ()
        dialect =sniffer .sniff (sample_text [:4096 ],delimiters =[',','\t',';','|'])
        return dialect .delimiter 
    except Exception :
        pass 

    lines =[line for line in sample_text .splitlines ()if line .strip ()][:10 ]
    if not lines :
        return ','

    delims =[',','\t',';','|']
    scores ={}
    for d in delims :
        counts =[line .count (d )for line in lines ]
        if all (c >0 for c in counts )and len (set (counts ))==1 :
            scores [d ]=counts [0 ]*10 
        elif any (c >0 for c in counts ):
            scores [d ]=sum (counts )
        else :
            scores [d ]=0 

    best =max (scores .items (),key =lambda x :x [1 ])
    return best [0 ]if best [1 ]>0 else ','

def get_spreadsheet_sheet_names (data :bytes ,ext :str )->List [str ]:
    ext =ext .lower ()
    if ext =='.xlsx':
        import openpyxl 
        wb =openpyxl .load_workbook (io .BytesIO (data ),read_only =True ,data_only =True )
        names =wb .sheetnames 
        wb .close ()
        return names 
    elif ext =='.xls':
        import xlrd 
        wb =xlrd .open_workbook (file_contents =data ,on_demand =True )
        return wb .sheet_names ()
    return []

def parse_xml_to_dataframe (data :bytes )->pd .DataFrame :
    try :
        root =ET .fromstring (data )
    except Exception as e :
        raise ValueError (f"Could not parse XML structure: {str (e )}")

    records :List [Dict [str ,Any ]]=[]
    children =list (root )
    if not children :
        raise ValueError ("XML document contains no child records.")

    for child in children :
        row ={}
        for sub in child :
            tag =sub .tag 
            text =(sub .text or "").strip ()
            row [tag ]=text 
        if not row and child .attrib :
            row =dict (child .attrib )
        if row :
            records .append (row )

    if not records :
        raise ValueError ("Could not find tabular records in XML document.")
    return pd .DataFrame (records )

def parse_pdf_to_dataframe (data :bytes )->Tuple [pd .DataFrame ,Dict [str ,Any ]]:
    try :
        with pdfplumber .open (io .BytesIO (data ))as pdf :
            num_pages =len (pdf .pages )
            if num_pages ==0 :
                raise ValueError ("PDF document has 0 pages.")


            for page_idx ,page in enumerate (pdf .pages [:5 ]):
                tables =page .extract_tables ()
                if tables and len (tables )>0 :
                    for table in tables :

                        cleaned_table =[[(cell or "").strip ()for cell in row ]for row in table if any (row )]
                        if len (cleaned_table )>=2 and len (cleaned_table [0 ])>=2 :

                            headers =cleaned_table [0 ]

                            safe_headers =[]
                            for idx ,h in enumerate (headers ):
                                h_clean =h if h else f"Col_{idx +1 }"
                                if h_clean in safe_headers :
                                    h_clean =f"{h_clean }_{idx +1 }"
                                safe_headers .append (h_clean )

                            df =pd .DataFrame (cleaned_table [1 :],columns =safe_headers )
                            preview_text =(page .extract_text ()or "")[:400 ]
                            meta ={
                            "pdf":True ,
                            "num_pages":num_pages ,
                            "page_number":page_idx +1 ,
                            "extracted_table":True ,
                            "detected_tables_count":len (tables ),
                            "preview_text":preview_text ,
                            "method":"Structured table extraction (pdfplumber)"
                            }
                            return df ,meta 


            first_page =pdf .pages [0 ]
            text =first_page .extract_text ()or ""
            lines =[line .strip ()for line in text .splitlines ()if line .strip ()]

            if lines :

                sample ="\n".join (lines [:10 ])
                delim =detect_text_delimiter (sample )
                split_lines =[l .split (delim )for l in lines ]
                max_cols =max (len (sl )for sl in split_lines )
                if max_cols >=2 :
                    headers =[f"Col_{i +1 }"for i in range (max_cols )]

                    padded =[sl +[""]*(max_cols -len (sl ))for sl in split_lines ]
                    df =pd .DataFrame (padded ,columns =headers )
                else :
                    df =pd .DataFrame ({"line_number":range (1 ,len (lines )+1 ),"content":lines })
            else :
                df =pd .DataFrame ({"info":["No selectable text layer found in PDF (scanned or image-only)."]})

            meta ={
            "pdf":True ,
            "num_pages":num_pages ,
            "page_number":1 ,
            "extracted_table":False ,
            "detected_tables_count":0 ,
            "preview_text":text [:500 ]if text else "Scanned document or empty page.",
            "method":"Text layer extraction (no explicit tables found)"
            }
            return df ,meta 

    except Exception as e :
        raise ValueError (f"Could not parse PDF document: {str (e )}")

def parse_resilient_csv (text :str ,delimiter :str =",")->pd .DataFrame :
    """
    Resilient CSV/TSV parser for jagged rows, extra fields, unclosed quotes,
    and corrupted delimiters. Never crashes with 'Expected N fields, saw M'.
    """
    lines =text .replace ("\r\n","\n").replace ("\r","\n").splitlines ()
    if not lines :
        return pd .DataFrame ()

    first_line =lines [0 ].strip ()
    try :
        header_row =next (csv .reader ([first_line ],delimiter =delimiter ))
    except Exception :
        header_row =[c .strip ()for c in first_line .split (delimiter )]
    header_cols =[c .strip ()for c in header_row if c .strip ()]
    if not header_cols :
        header_cols =[f"col_{i +1 }"for i in range (len (header_row ))]

    parsed_rows =[]
    max_len =len (header_cols )

    for line_idx ,line in enumerate (lines [1 :],start =2 ):
        s_line =line .strip ()
        if not s_line :
            continue 

        if s_line .lower ().replace (" ","")==first_line .lower ().replace (" ",""):
            continue 


        if s_line .count ('"')%2 !=0 :
            s_line =s_line .replace ('"','')

        row_fields =None 
        try :
            row_fields =next (csv .reader ([s_line ],delimiter =delimiter ))
        except Exception :
            row_fields =s_line .split (delimiter )

        if row_fields :
            clean_fields =[f .strip ()for f in row_fields ]
            parsed_rows .append (clean_fields )
            if len (clean_fields )>max_len :
                max_len =len (clean_fields )

    final_cols =list (header_cols )
    if max_len >len (final_cols ):
        for extra_idx in range (len (final_cols )+1 ,max_len +1 ):
            final_cols .append (f"extra_col_{extra_idx -len (header_cols )}")

    aligned_rows =[]
    for r in parsed_rows :
        if len (r )<max_len :
            r =r +[""]*(max_len -len (r ))
        elif len (r )>max_len :
            r =r [:max_len ]
        aligned_rows .append (r )

    return pd .DataFrame (aligned_rows ,columns =final_cols )

def load_dataset_from_bytes (
data :bytes ,
filename :str ,
sheet_name :Optional [str ]=None 
)->Tuple [pd .DataFrame ,Dict [str ,Any ]]:
    _ ,ext =os .path .splitext (filename .lower ())
    meta :Dict [str ,Any ]={"format":ext .lstrip ('.')}

    try :
        if ext in ('.csv','.tsv','.txt'):
            text_content =""
            for enc in ['utf-8','utf-8-sig','latin1','cp1252']:
                try :
                    text_content =data .decode (enc )
                    meta ['encoding']=enc 
                    break 
                except UnicodeDecodeError :
                    continue 
            if not text_content :
                raise ValueError ("Could not decode text file using standard character encodings.")

            delimiter ='\t'if ext =='.tsv'else detect_text_delimiter (text_content [:8192 ])
            meta ['delimiter']=delimiter 
            try :
                df =pd .read_csv (io .StringIO (text_content ),sep =delimiter ,low_memory =False ,dtype =object )
            except Exception :
                df =parse_resilient_csv (text_content ,delimiter =delimiter )

        elif ext in ('.json','.jsonl','.ndjson'):
            text_content =data .decode ('utf-8',errors ='replace')
            if ext in ('.jsonl','.ndjson')or '\n'in text_content .strip ():
                try :
                    df =pd .read_json (io .StringIO (text_content ),lines =True ,dtype =object )
                    meta ['json_type']='lines'
                except Exception :
                    parsed =json .loads (text_content )
                    if isinstance (parsed ,list ):
                        df =pd .DataFrame (parsed )
                    elif isinstance (parsed ,dict ):
                        list_key =next ((k for k ,v in parsed .items ()if isinstance (v ,list )),None )
                        df =pd .DataFrame (parsed [list_key ])if list_key else pd .DataFrame ([parsed ])
                    else :
                        raise ValueError ("JSON content is not a valid list of records.")
            else :
                parsed =json .loads (text_content )
                if isinstance (parsed ,list ):
                    df =pd .DataFrame (parsed )
                elif isinstance (parsed ,dict ):
                    list_key =next ((k for k ,v in parsed .items ()if isinstance (v ,list )),None )
                    df =pd .DataFrame (parsed [list_key ])if list_key else pd .DataFrame ([parsed ])
                else :
                    raise ValueError ("JSON file does not contain a structured record array.")

        elif ext =='.parquet':
            df =pd .read_parquet (io .BytesIO (data ))

        elif ext in ('.feather','.arrow'):
            df =pd .read_feather (io .BytesIO (data ))

        elif ext =='.xlsx':
            available_sheets =get_spreadsheet_sheet_names (data ,ext )
            meta ['available_sheets']=available_sheets 
            target_sheet =sheet_name or (available_sheets [0 ]if available_sheets else 0 )
            meta ['selected_sheet']=target_sheet 
            df =pd .read_excel (io .BytesIO (data ),sheet_name =target_sheet ,engine ='openpyxl')

        elif ext =='.xls':
            available_sheets =get_spreadsheet_sheet_names (data ,ext )
            meta ['available_sheets']=available_sheets 
            target_sheet =sheet_name or (available_sheets [0 ]if available_sheets else 0 )
            meta ['selected_sheet']=target_sheet 
            df =pd .read_excel (io .BytesIO (data ),sheet_name =target_sheet ,engine ='xlrd')

        elif ext =='.xml':
            df =parse_xml_to_dataframe (data )

        elif ext =='.pdf':
            df ,pdf_meta =parse_pdf_to_dataframe (data )
            meta .update (pdf_meta )

        else :
            raise ValueError (f"File format '{ext }' is currently unsupported.")

    except Exception as e :
        err_msg =str (e )
        if "No columns to parse"in err_msg or "Empty data"in err_msg :
            raise ValueError ("Could not read this file. The dataset appears to be empty.")
        elif "JSONDecodeError"in err_msg :
            raise ValueError ("Could not read this file. The JSON structure is invalid.")
        else :
            raise ValueError (f"Could not read this file: {err_msg }")

    if len (df )>MAX_ROWS :
        raise ValueError (f"Dataset exceeds the maximum limit of {MAX_ROWS :,} rows.")
    if len (df .columns )>MAX_COLUMNS :
        raise ValueError (f"Dataset exceeds the maximum limit of {MAX_COLUMNS :,} columns.")

    return df ,meta 
