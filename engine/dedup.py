"""
Entity Matching and Deduplication Module.

Implements Levenshtein dynamic programming distance, Jaccard token similarity,
phonetic Soundex blocking, and entity deduplication cluster resolution.
"""

from dataclasses import dataclass ,field 
import re 
from typing import Any ,Dict ,List ,Optional ,Set ,Tuple 
import pandas as pd 


@dataclass 
class DuplicateEntityMatch :
    cluster_id :int 
    record_index_1 :int 
    record_index_2 :int 
    matched_columns :List [str ]
    similarity_score :float 
    confidence :str 
    entity_key_1 :str 
    entity_key_2 :str 


class EntityDeduplicator :
    """
    Fuzzy entity resolution and deduplication engine.
    """

    @staticmethod 
    def levenshtein_distance (s1 :str ,s2 :str )->int :
        if s1 ==s2 :
            return 0 
        m ,n =len (s1 ),len (s2 )
        if m ==0 :
            return n 
        if n ==0 :
            return m 
        dp =list (range (n +1 ))
        for i in range (1 ,m +1 ):
            new_dp =[i ]+[0 ]*n 
            for j in range (1 ,n +1 ):
                cost =0 if s1 [i -1 ]==s2 [j -1 ]else 1 
                new_dp [j ]=min (dp [j ]+1 ,new_dp [j -1 ]+1 ,dp [j -1 ]+cost )
            dp =new_dp 
        return dp [n ]

    @classmethod 
    def string_similarity (cls ,s1 :str ,s2 :str )->float :
        s1 ,s2 =str (s1 ).strip ().lower (),str (s2 ).strip ().lower ()
        if not s1 and not s2 :
            return 1.0 
        max_len =max (len (s1 ),len (s2 ))
        if max_len ==0 :
            return 1.0 
        dist =cls .levenshtein_distance (s1 ,s2 )
        return float (1.0 -(dist /max_len ))

    @staticmethod 
    def jaccard_similarity (s1 :str ,s2 :str )->float :
        toks1 =set (re .findall (r"\w+",str (s1 ).lower ()))
        toks2 =set (re .findall (r"\w+",str (s2 ).lower ()))
        if not toks1 and not toks2 :
            return 1.0 
        union =toks1 .union (toks2 )
        if not union :
            return 1.0 
        return float (len (toks1 .intersection (toks2 ))/len (union ))

    @staticmethod 
    def soundex (name :str )->str :
        name =str (name ).strip ().upper ()
        if not name :
            return ""
        first =name [0 ]
        mapping ={
        "B":"1","F":"1","P":"1","V":"1",
        "C":"2","G":"2","J":"2","K":"2","Q":"2","S":"2","X":"2","Z":"2",
        "D":"3","T":"3",
        "L":"4",
        "M":"5","N":"5",
        "R":"6"
        }
        coded =[first ]
        prev =mapping .get (first ,"0")
        for char in name [1 :]:
            code =mapping .get (char ,"0")
            if code !="0":
                if code !=prev :
                    coded .append (code )
                prev =code 
            else :
                prev ="0"
            if len (coded )==4 :
                break 
        return "".join (coded ).ljust (4 ,"0")

    @classmethod 
    def find_duplicate_entities (
    cls ,
    df :pd .DataFrame ,
    entity_columns :List [str ],
    similarity_threshold :float =0.85 
    )->List [DuplicateEntityMatch ]:
        """
        Detect fuzzy duplicates across specified entity columns.
        """
        matches :List [DuplicateEntityMatch ]=[]
        n_rows =len (df )
        cluster_counter =0 


        exact_dups =df .duplicated (subset =entity_columns ,keep =False )
        if exact_dups .any ():
            exact_indices =df [exact_dups ].index .tolist ()

            grouped =df [exact_dups ].groupby (entity_columns )
            for _ ,grp in grouped :
                idx_list =grp .index .tolist ()
                for i in range (len (idx_list )):
                    for j in range (i +1 ,len (idx_list )):
                        cluster_counter +=1 
                        matches .append (DuplicateEntityMatch (
                        cluster_id =cluster_counter ,
                        record_index_1 =int (idx_list [i ]),
                        record_index_2 =int (idx_list [j ]),
                        matched_columns =entity_columns ,
                        similarity_score =1.0 ,
                        confidence ="HIGH",
                        entity_key_1 =str (df .loc [idx_list [i ],entity_columns ].to_dict ()),
                        entity_key_2 =str (df .loc [idx_list [j ],entity_columns ].to_dict ())
                        ))



        if entity_columns and n_rows <=2000 :
            key_col =entity_columns [0 ]
            blocks :Dict [str ,List [int ]]={}
            for idx ,val in df [key_col ].dropna ().items ():
                b_key =cls .soundex (str (val ))
                blocks .setdefault (b_key ,[]).append (int (idx ))


            record_cache ={idx :{col :str (df .at [idx ,col ])for col in entity_columns }for idx in df .index }
            for b_key ,row_indices in blocks .items ():
                if len (row_indices )>1 and len (row_indices )<=30 :
                    for i in range (len (row_indices )):
                        idx1 =row_indices [i ]
                        r1 =record_cache [idx1 ]
                        for j in range (i +1 ,len (row_indices )):
                            idx2 =row_indices [j ]
                            r2 =record_cache [idx2 ]

                            scores =[]
                            for col in entity_columns :
                                v1 ,v2 =r1 [col ],r2 [col ]
                                if v1 ==v2 :
                                    scores .append (1.0 )
                                else :
                                    s_lev =cls .string_similarity (v1 ,v2 )
                                    s_jac =cls .jaccard_similarity (v1 ,v2 )
                                    scores .append (max (s_lev ,s_jac ))

                            avg_score =sum (scores )/max (1 ,len (scores ))
                            if avg_score >=similarity_threshold and avg_score <1.0 :
                                cluster_counter +=1 
                                conf ="HIGH"if avg_score >=0.92 else "MEDIUM"
                                matches .append (DuplicateEntityMatch (
                                cluster_id =cluster_counter ,
                                record_index_1 =idx1 ,
                                record_index_2 =idx2 ,
                                matched_columns =entity_columns ,
                                similarity_score =round (avg_score ,4 ),
                                confidence =conf ,
                                entity_key_1 =str (r1 ),
                                entity_key_2 =str (r2 )
                                ))

        return matches 
