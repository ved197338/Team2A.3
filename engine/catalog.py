"""
Enterprise Data Catalog and Lineage Module.

Implements metadata schemas and lineage DAGs compatible with
DataHub, Amundsen, and Collibra specifications.
"""

from dataclasses import asdict ,dataclass ,field 
from datetime import datetime ,timezone 
import hashlib 
from typing import Any ,Dict ,List ,Optional 
import pandas as pd 


@dataclass 
class ColumnMetadata :
    name :str 
    data_type :str 
    is_nullable :bool =True 
    is_primary_key :bool =False 
    description :str =""
    tags :List [str ]=field (default_factory =list )
    classification :str ="INTERNAL"


@dataclass 
class CatalogDataset :
    urn :str 
    name :str 
    platform :str 
    environment :str 
    schema_hash :str 
    columns :List [ColumnMetadata ]
    row_count :int 
    size_bytes :int 
    created_at :str 
    last_modified :str 
    owner :str ="data-governance-team@innovate.internal"
    upstream_urns :List [str ]=field (default_factory =list )
    downstream_urns :List [str ]=field (default_factory =list )
    custom_properties :Dict [str ,Any ]=field (default_factory =dict )


class EnterpriseCatalog :
    """
    Enterprise Catalog and Lineage registry compatible with DataHub and Amundsen.
    """

    def __init__ (self ,platform_name :str ="lakehouse-delta"):
        self .platform_name =platform_name 
        self .registry :Dict [str ,CatalogDataset ]={}

    @staticmethod 
    def compute_schema_hash (df :pd .DataFrame )->str :
        schema_repr ="|".join (f"{col }:{str (df [col ].dtype )}"for col in sorted (df .columns ))
        return hashlib .sha256 (schema_repr .encode ("utf-8")).hexdigest ()[:16 ]

    def register_dataframe (
    self ,
    name :str ,
    df :pd .DataFrame ,
    environment :str ="PROD",
    upstream_urns :Optional [List [str ]]=None ,
    downstream_urns :Optional [List [str ]]=None ,
    primary_keys :Optional [List [str ]]=None ,
    column_classifications :Optional [Dict [str ,str ]]=None 
    )->CatalogDataset :
        urn =f"urn:li:dataset:(urn:li:dataPlatform:{self .platform_name },{name },{environment })"
        now_iso =datetime .now (timezone .utc ).isoformat ()
        schema_hash =self .compute_schema_hash (df )

        pks =set (primary_keys or [])
        col_class =column_classifications or {}

        columns :List [ColumnMetadata ]=[]
        for col_name in df .columns :
            dtype_str =str (df [col_name ].dtype )
            nullable =bool (df [col_name ].isna ().any ())
            is_pk =col_name in pks 
            classification =col_class .get (str (col_name ),"INTERNAL")

            columns .append (ColumnMetadata (
            name =str (col_name ),
            data_type =dtype_str ,
            is_nullable =nullable ,
            is_primary_key =is_pk ,
            description =f"Field {col_name } of type {dtype_str }",
            classification =classification 
            ))

        dataset =CatalogDataset (
        urn =urn ,
        name =name ,
        platform =self .platform_name ,
        environment =environment ,
        schema_hash =schema_hash ,
        columns =columns ,
        row_count =len (df ),
        size_bytes =int (df .memory_usage (deep =True ).sum ()),
        created_at =now_iso ,
        last_modified =now_iso ,
        upstream_urns =upstream_urns or [],
        downstream_urns =downstream_urns or [],
        custom_properties ={
        "column_count":len (df .columns ),
        "ai_ready":False ,
        "certification":"UNAUDITED"
        }
        )

        self .registry [urn ]=dataset 
        return dataset 

    def export_datahub_mcp (self ,urn :str )->Dict [str ,Any ]:
        """Export Metadata Change Proposal (MCP) payload for DataHub ingestion."""
        if urn not in self .registry :
            raise KeyError (f"Dataset {urn } not found in catalog.")

        dataset =self .registry [urn ]
        return {
        "entityType":"dataset",
        "entityUrn":dataset .urn ,
        "changeType":"UPSERT",
        "aspectName":"schemaMetadata",
        "aspect":{
        "schemaName":dataset .name ,
        "platform":f"urn:li:dataPlatform:{dataset .platform }",
        "version":0 ,
        "hash":dataset .schema_hash ,
        "fields":[
        {
        "fieldPath":col .name ,
        "type":{"type":col .data_type },
        "nullable":col .is_nullable ,
        "description":col .description ,
        "globalTags":{"tags":[{"tag":f"urn:li:tag:{t }"}for t in col .tags ]}
        }
        for col in dataset .columns 
        ]
        }
        }

    def export_lineage_graph (self )->Dict [str ,Any ]:
        """Export full lineage Directed Acyclic Graph (DAG) for visual rendering."""
        nodes =[]
        edges =[]
        for urn ,dataset in self .registry .items ():
            nodes .append ({
            "id":urn ,
            "name":dataset .name ,
            "platform":dataset .platform ,
            "environment":dataset .environment ,
            "row_count":dataset .row_count ,
            "schema_hash":dataset .schema_hash 
            })
            for up in dataset .upstream_urns :
                edges .append ({"source":up ,"target":urn ,"type":"DATA_FLOW"})
            for down in dataset .downstream_urns :
                edges .append ({"source":urn ,"target":down ,"type":"AI_CONSUMPTION"})

        return {
        "version":"1.0",
        "generated_at":datetime .now (timezone .utc ).isoformat (),
        "nodes":nodes ,
        "edges":edges 
        }
