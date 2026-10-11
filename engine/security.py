import os 
import re 
import uuid 
import zipfile 
from typing import Any ,Optional ,Tuple 

MAX_FILE_SIZE_BYTES =100 *1024 *1024 
MAX_ROWS =1_000_000 
MAX_COLUMNS =5_000 
MAX_UNCOMPRESSED_ZIP_BYTES =250 *1024 *1024 
MAX_ZIP_EXPANSION_RATIO =50.0 

ALLOWED_EXTENSIONS ={
'.csv','.tsv','.txt',
'.json','.jsonl','.ndjson',
'.parquet','.feather','.arrow',
'.xlsx','.xls',
'.xml','.ods',
'.pdf'
}

EXECUTABLE_SIGNATURES =[
b'MZ',
b'\x7fELF',
b'#!',
b'\xca\xfe\xba\xbe',
b'\xfe\xed\xfa\xce',
b'\xfe\xed\xfa\xcf',
]

STORAGE_DIR =os .path .abspath (os .path .join (os .path .dirname (__file__ ),"..",".storage","temp"))

def ensure_storage_dir ():
    os .makedirs (STORAGE_DIR ,exist_ok =True )

def sanitize_display_filename (client_filename :str )->str :
    base =os .path .basename (client_filename )
    safe =re .sub (r'[^a-zA-Z0-9_.-]','_',base )
    return safe [:120 ]if safe else "uploaded_file.dat"

def generate_secure_storage_path ()->Tuple [str ,str ]:
    ensure_storage_dir ()
    file_id =uuid .uuid4 ().hex 
    secure_path =os .path .join (STORAGE_DIR ,f"{file_id }.dat")
    return file_id ,secure_path 

def validate_file_content_and_size (data :bytes ,original_filename :str )->Tuple [bool ,str ,str ]:
    if not data or len (data )==0 :
        return False ,"The uploaded file is empty.",""

    if len (data )>MAX_FILE_SIZE_BYTES :
        return False ,f"File exceeds the maximum size limit of {MAX_FILE_SIZE_BYTES //(1024 *1024 )} MB.",""

    _ ,ext =os .path .splitext (original_filename .lower ())
    if ext not in ALLOWED_EXTENSIONS :
        return False ,f"File format '{ext }' is not supported.",""

    prefix =data [:16 ]
    for sig in EXECUTABLE_SIGNATURES :
        if prefix .startswith (sig ):
            return False ,"Security check failed: File appears to be an executable or unsupported binary format.",""

    if ext =='.parquet':
        if not data .startswith (b'PAR1'):
            return False ,"Invalid file signature: File does not appear to be a valid Parquet dataset.",ext 
    elif ext in ('.feather','.arrow'):
        if not data .startswith (b'ARROW1'):
            return False ,"Invalid file signature: File does not appear to be a valid Feather/Arrow dataset.",ext 
    elif ext =='.pdf':
        if not data .startswith (b'%PDF'):
            return False ,"Invalid file signature: File does not appear to be a valid PDF document.",ext 
    elif ext =='.xlsx':
        if not data .startswith (b'PK\x03\x04'):
            return False ,"Invalid file signature: Excel file is corrupted or not a valid XLSX document.",ext 
        try :
            import io 
            with zipfile .ZipFile (io .BytesIO (data ))as zf :
                total_uncompressed =0 
                for info in zf .infolist ():
                    total_uncompressed +=info .file_size 
                    if total_uncompressed >MAX_UNCOMPRESSED_ZIP_BYTES :
                        return False ,"Security check failed: Archive expansion exceeds maximum allowed size.",ext 
                if len (data )>0 and (total_uncompressed /len (data ))>MAX_ZIP_EXPANSION_RATIO :
                    return False ,"Security check failed: Suspicious compression ratio detected.",ext 
        except Exception :
            return False ,"Security check failed: Unable to parse Excel archive structure.",ext 
    elif ext =='.xls':
        if not data .startswith (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
            return False ,"Invalid file signature: Legacy Excel file is corrupted.",ext 

    return True ,"",ext 

def sanitize_cell_for_export (val :Any )->Any :
    """Neutralize formula injection in CSV/Excel exports."""
    if not isinstance (val ,str ):
        return val 
    if val and val [0 ]in ('=','+','-','@','\t','\r'):
        return "'"+val 
    return val 

def secure_delete (path :str )->bool :
    try :
        resolved =os .path .abspath (path )
        if resolved .startswith (STORAGE_DIR )and os .path .isfile (resolved ):
            os .remove (resolved )
            return True 
    except Exception :
        pass 
    return False 
