import os 
import re 
import math 
from typing import List ,Dict ,Tuple ,Optional ,Any 
import pandas as pd 

class RAGEngine :
    def __init__ (self ):
        self .documents :List [Dict [str ,Any ]]=[]
        self .doc_index :List [Dict [str ,int ]]=[]
        self .doc_lengths :List [int ]=[]
        self .avg_doc_len :float =0.0 
        self .idf :Dict [str ,float ]={}

    def _tokenize (self ,text :str )->List [str ]:
        words =re .findall (r"\w+",text .lower ())
        char_ngrams =[text [i :i +3 ].lower ()for i in range (len (text )-2 )if " "not in text [i :i +3 ]]
        return words +char_ngrams [:len (words )]

    def index_dataframe (self ,df :pd .DataFrame ,source_name :str ="dataset.csv")->int :
        self .documents =[]
        self .doc_index =[]
        self .doc_lengths =[]

        schema_text =f"Dataset: {source_name }. Total Rows: {len (df )}. Total Columns: {len (df .columns )}. Columns: {', '.join (df .columns )}. Summary of features: "
        for col in df .columns :
            non_null =df [col ].notna ().sum ()
            sample_vals =[str (x )for x in df [col ].dropna ().unique ()[:4 ]]
            schema_text +=f"Column '{col }' ({non_null }/{len (df )} populated, samples: {', '.join (sample_vals )}). "

        self .documents .append ({
        "id":0 ,
        "source":source_name ,
        "type":"schema",
        "content":schema_text .strip ()
        })

        for idx ,row in df .head (100 ).iterrows ():
            row_items =[f"{col }: {val }"for col ,val in row .items ()if pd .notna (val )]
            row_text =f"Record {idx +1 } from {source_name }: "+" | ".join (row_items )
            self .documents .append ({
            "id":len (self .documents ),
            "source":source_name ,
            "type":"row",
            "row_index":idx ,
            "content":row_text 
            })

        self ._build_index ()
        return len (self .documents )

    def index_text_content (self ,text :str ,source_name :str ="document.txt")->int :
        self .documents =[]
        self .doc_index =[]
        self .doc_lengths =[]

        paragraphs =[p .strip ()for p in text .split ("\n\n")if len (p .strip ())>15 ]
        if not paragraphs :
            paragraphs =[p .strip ()for p in text .split ("\n")if len (p .strip ())>15 ]

        for i ,p in enumerate (paragraphs [:150 ]):
            self .documents .append ({
            "id":len (self .documents ),
            "source":source_name ,
            "type":"text_chunk",
            "chunk_index":i ,
            "content":p 
            })

        self ._build_index ()
        return len (self .documents )

    def _build_index (self ):
        total_docs =len (self .documents )
        if total_docs ==0 :
            return 

        df_counts :Dict [str ,int ]={}
        self .doc_lengths =[]
        self .doc_index =[]

        for doc in self .documents :
            tokens =self ._tokenize (doc ["content"])
            self .doc_lengths .append (len (tokens ))
            term_freq :Dict [str ,int ]={}
            for t in tokens :
                term_freq [t ]=term_freq .get (t ,0 )+1 
            self .doc_index .append (term_freq )
            for t in term_freq :
                df_counts [t ]=df_counts .get (t ,0 )+1 

        self .avg_doc_len =sum (self .doc_lengths )/max (1 ,total_docs )
        self .idf ={}
        for t ,count in df_counts .items ():
            self .idf [t ]=math .log (1.0 +(total_docs -count +0.5 )/(count +0.5 ))

    def retrieve (self ,query :str ,top_k :int =3 )->List [Dict [str ,Any ]]:
        if not self .documents :
            return []

        q_tokens =self ._tokenize (query )
        if not q_tokens :
            return self .documents [:top_k ]

        scores =[]
        k1 =1.5 
        b =0.75 

        for i ,doc in enumerate (self .documents ):
            score =0.0 
            doc_len =self .doc_lengths [i ]
            tf_dict =self .doc_index [i ]
            for qt in q_tokens :
                if qt in tf_dict :
                    tf =tf_dict [qt ]
                    idf_val =self .idf .get (qt ,0.1 )
                    num =tf *(k1 +1.0 )
                    denom =tf +k1 *(1.0 -b +b *(doc_len /max (1.0 ,self .avg_doc_len )))
                    score +=idf_val *(num /denom )

            if score >0 :
                scores .append ((score ,doc ))

        scores .sort (key =lambda x :x [0 ],reverse =True )
        if not scores :
            return self .documents [:top_k ]
        return [doc for score ,doc in scores [:top_k ]]

    def format_rag_prompt (self ,query :str ,top_k :int =2 )->str :
        hits =self .retrieve (query ,top_k =top_k )
        if not hits :
            return f"rag: context: No documents indexed. | query: {query } | answer:"

        chunks =[h ["content"]for h in hits ]
        context_str =" ... ".join (chunks )
        if len (context_str )>260 :
            context_str =context_str [:260 ]+"..."
        return f"rag: context: {context_str } | query: {query } | answer:"

RAG_INSTANCE =RAGEngine ()

def get_rag_engine ()->RAGEngine :
    return RAG_INSTANCE 
