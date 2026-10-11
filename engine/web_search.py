"""
Web Search Engine for innovATE / innov8.
Provides fast, reliable, zero-api-key web retrieval for fact-checking and Q&A.
Uses DuckDuckGo Instant Answer API and Wikipedia Search & Summary API.
"""

import json 
import re 
import urllib .parse 
import urllib .request 
from typing import Dict ,Optional 


def clean_snippet (text :str )->str :
    """Strip HTML tags and normalize whitespace."""
    if not text :
        return ""
    text =re .sub (r"<[^>]+>"," ",text )
    text =re .sub (r"&[a-z]+;"," ",text )
    text =re .sub (r"\s+"," ",text ).strip ()
    return text 


def clean_search_query (query :str )->str :
    """Clean conversational filler words from query for search engines."""
    q =re .sub (r"^(web:|search web:|search for:|search:|google:|find on web:|look up:)\s*","",query ,flags =re .IGNORECASE ).strip ()
    q =re .sub (r"^(who is|what is|where is|when was|when did|tell me about|explain|describe)\s+(?:(a|an|the)\s+)?","",q ,flags =re .IGNORECASE ).strip ()
    q =q .rstrip ("?.,!").strip ()
    return q if q else query .rstrip ("?.,!").strip ()


def search_duckduckgo_api (query :str ,timeout :float =4.0 )->Optional [Dict [str ,str ]]:
    """Query DuckDuckGo Instant Answer API."""
    try :
        encoded =urllib .parse .quote_plus (query )
        url =f"https://api.duckduckgo.com/?q={encoded }&format=json&no_html=1&skip_disambig=1"
        req =urllib .request .Request (
        url ,
        headers ={
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        )
        with urllib .request .urlopen (req ,timeout =timeout )as resp :
            data =json .loads (resp .read ().decode ("utf-8",errors ="ignore"))
            if data .get ("AbstractText")and len (data ["AbstractText"])>40 :
                return {
                "title":data .get ("Heading",query ),
                "text":data ["AbstractText"],
                "url":data .get ("AbstractURL","https://duckduckgo.com/?q="+encoded ),
                "source":data .get ("AbstractSource","DuckDuckGo")
                }
            elif data .get ("RelatedTopics"):
                for topic in data ["RelatedTopics"]:
                    if isinstance (topic ,dict )and "Text"in topic and len (topic ["Text"])>40 :
                        return {
                        "title":topic .get ("Text","")[:60 ],
                        "text":topic ["Text"],
                        "url":topic .get ("FirstURL","https://duckduckgo.com/?q="+encoded ),
                        "source":"DuckDuckGo Knowledge"
                        }
    except Exception :
        pass 
    return None 


def search_wikipedia_api (query :str ,timeout :float =4.0 )->Optional [Dict [str ,str ]]:
    """Query Wikipedia Search and Summary API."""
    try :
        encoded =urllib .parse .quote_plus (query )
        search_url =f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded }&utf8=&format=json&srlimit=5"
        req =urllib .request .Request (
        search_url ,
        headers ={"User-Agent":"innovATE/1.0 (educational research; contact@innovate.local)"}
        )
        with urllib .request .urlopen (req ,timeout =timeout )as resp :
            data =json .loads (resp .read ().decode ("utf-8",errors ="ignore"))
            results =data .get ("query",{}).get ("search",[])
            if not results :
                return None 


            selected =results [0 ]
            for r in results :
                t =r .get ("title","")
                if not any (t .lower ().startswith (p )for p in ["outline of","list of","index of","category:"]):
                    selected =r 
                    break 

            title =selected .get ("title","")
            title_enc =urllib .parse .quote (title .replace (" ","_"))


            sum_url =f"https://en.wikipedia.org/api/rest_v1/page/summary/{title_enc }"
            req_sum =urllib .request .Request (
            sum_url ,
            headers ={"User-Agent":"innovATE/1.0 (educational research; contact@innovate.local)"}
            )
            try :
                with urllib .request .urlopen (req_sum ,timeout =timeout )as sresp :
                    sdata =json .loads (sresp .read ().decode ("utf-8",errors ="ignore"))
                    extract =sdata .get ("extract","")
                    page_url =sdata .get ("content_urls",{}).get ("desktop",{}).get ("page",f"https://en.wikipedia.org/wiki/{title_enc }")
                    if extract and len (extract )>40 :
                        return {
                        "title":title ,
                        "text":extract ,
                        "url":page_url ,
                        "source":"Wikipedia"
                        }
            except Exception :
                snippet =clean_snippet (selected .get ("snippet",""))
                if snippet :
                    return {
                    "title":title ,
                    "text":snippet ,
                    "url":f"https://en.wikipedia.org/wiki/{title_enc }",
                    "source":"Wikipedia"
                    }
    except Exception :
        pass 
    return None 


def search_web (query :str )->Optional [Dict [str ,str ]]:
    """
    Search the live web using multi-source fallback.
    Returns dictionary with title, text, url, and source, or None if unavailable.
    """
    target =clean_search_query (query )
    if not target :
        return None 


    res =search_wikipedia_api (target )
    if res and len (res .get ("text",""))>60 :
        return res 


    res =search_duckduckgo_api (target )
    if res and len (res .get ("text",""))>40 :
        return res 


    if target !=query :
        res =search_wikipedia_api (query .rstrip ("?.,!"))
        if res and len (res .get ("text",""))>60 :
            return res 

    return None 
