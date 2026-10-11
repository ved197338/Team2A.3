"""
High-Performance Text Mistake Corrector for innovATE / innov8.
Handles massive multi-paragraph texts, grammar repairs, typo rectification,
punctuation normalization, currency formatting, sensitive PII redaction,
and visual inline diff generation.
"""

import re 
from typing import Dict ,List ,Tuple 


COMMON_TYPOS ={

r"\bim\b":"I'm",
r"\bdont\b":"don't",
r"\bwont\b":"won't",
r"\bcant\b":"can't",
r"\bdidnt\b":"didn't",
r"\bisnt\b":"isn't",
r"\bwasnt\b":"wasn't",
r"\barent\b":"aren't",
r"\bwerent\b":"weren't",
r"\bhavent\b":"haven't",
r"\bhasnt\b":"hasn't",
r"\bcouldnt\b":"couldn't",
r"\bshouldnt\b":"shouldn't",
r"\bwouldnt\b":"wouldn't",
r"\byoure\b":"you're",
r"\btheyre\b":"they're",
r"\bweve\b":"we've",
r"\btheyve\b":"they've",
r"\bi ve\b":"I've",
r"\bi m\b":"I'm",


r"\bcould of\b":"could have",
r"\bshould of\b":"should have",
r"\bwould of\b":"would have",
r"\bmust of\b":"must have",
r"\balot\b":"a lot",
r"\bnoone\b":"no one",
r"\ballmost\b":"almost",


r"\bteh\b":"the",
r"\btaht\b":"that",
r"\bwaht\b":"what",
r"\bwiht\b":"with",
r"\bfro\b":"for",
r"\badn\b":"and",
r"\bbecuase\b":"because",
r"\bdroping\b":"dropping",
r"\bsuply\b":"supply",
r"\bcompanys\b":"company's",
r"\bcostumer\b":"customer",
r"\bcustmer\b":"customer",
r"\bunautorized\b":"unauthorized",
r"\bunauthorizd\b":"unauthorized",
r"\bpleas\b":"please",
r"\bplz\b":"please",
r"\bunpayed\b":"unpaid",
r"\badmited\b":"admitted",
r"\bfevr\b":"fever",
r"\brecieved\b":"received",
r"\brecieve\b":"receive",
r"\bseperate\b":"separate",
r"\bdefinately\b":"definitely",
r"\buntill\b":"until",
r"\binforamtion\b":"information",
r"\btransation\b":"transaction",
r"\bbalence\b":"balance",
r"\bacount\b":"account",
r"\badress\b":"address",
r"\bperssonal\b":"personal",
r"\bcanceld\b":"cancelled",
r"\bfaild\b":"failed",
r"\bsubcription\b":"subscription",
r"\bsuccesfull\b":"successful",
r"\bsucessful\b":"successful",
r"\bdocto\b":"doctor",
r"\bhosptial\b":"hospital",
r"\bdiagnsis\b":"diagnosis",
r"\bmedisin\b":"medicine",
r"\bprescrip\b":"prescription",
r"\bgoverment\b":"government",
r"\bneccessary\b":"necessary",
r"\btommorow\b":"tomorrow",
r"\boccured\b":"occurred",
r"\baccomodate\b":"accommodate",
r"\benviroment\b":"environment",
r"\breccomend\b":"recommend",
r"\bwierd\b":"weird",
r"\btruely\b":"truly",
r"\binterupt\b":"interrupt",
r"\bbegining\b":"beginning",
r"\bbeleive\b":"believe",
r"\bcalender\b":"calendar",
r"\bexistance\b":"existence",
r"\bforiegn\b":"foreign",
r"\bguarentee\b":"guarantee",
r"\bhight\b":"height",
r"\bimmediatly\b":"immediately",
r"\bindependant\b":"independent",
r"\bknowlege\b":"knowledge",
r"\bnoticable\b":"noticeable",
r"\bpriviledge\b":"privilege",
r"\brelevent\b":"relevant",
r"\bsieze\b":"seize",
r"\bwe was\b":"we were",
r"\bthey was\b":"they were",
r"\byou was\b":"you were",
r"\byesturday\b":"yesterday",
r"\bwich\b":"which",
r"\bsuprising\b":"surprising",
r"\bsuprisingly\b":"surprisingly",
r"\bconact\b":"contact",
r"\bminuites\b":"minutes",
r"\bafternon\b":"afternoon",
r"\bgrocer store\b":"grocery store",
r"\binsted\b":"instead",
r"\bexcelent\b":"excellent",
r"\bbycicle\b":"bicycle",
r"\bby some milk\b":"buy some milk",
r"\bby some\b":"buy some"
}


def create_highlighted_diffs (raw_text :str ,fixed_text :str ,diffs :List [Tuple [str ,str ,str ]])->Tuple [str ,str ]:
    """
    Creates visual Before and After text with inline <del> and <ins> highlight chips
    so the user immediately sees every single difference.
    """
    hl_before =raw_text 
    hl_after =fixed_text 


    sorted_diffs =sorted (diffs ,key =lambda d :len (str (d [0 ])),reverse =True )

    seen_raw =set ()
    for orig ,rep ,act in sorted_diffs :
        orig_s =str (orig )
        if orig_s in seen_raw or not orig_s .strip ():
            continue 
        seen_raw .add (orig_s )
        try :
            pattern =r"(?<!\w)"+re .escape (orig_s )+r"(?!\w)"
            hl_before =re .sub (pattern ,f'<del class="diff-del">{orig_s }</del>',hl_before ,count =2 )
        except Exception :
            pass 

    seen_rep =set ()
    for orig ,rep ,act in sorted_diffs :
        rep_s =str (rep )
        if rep_s in seen_rep or not rep_s .strip ():
            continue 
        seen_rep .add (rep_s )
        try :
            pattern =r"(?<!\w)"+re .escape (rep_s )+r"(?!\w)"
            hl_after =re .sub (pattern ,f'<ins class="diff-ins">{rep_s }</ins>',hl_after ,count =2 )
        except Exception :
            pass 

    return hl_before ,hl_after 


def correct_massive_text (raw_text :str )->Tuple [str ,List [Tuple [str ,str ,str ]],Dict [str ,int ]]:
    """
    Corrects any volume of text (single line, paragraphs, or thousands of words).
    Returns (corrected_text, diff_transformations, stats).
    """
    diff_transformations =[]
    stats ={
    "typos":0 ,
    "pii":0 ,
    "currency":0 ,
    "punctuation":0 ,
    "paragraphs":0 ,
    "words":len (raw_text .split ())
    }

    paragraphs =raw_text .split ("\n")
    cleaned_paragraphs =[]

    for p in paragraphs :
        s =p .strip ()
        if not s :
            cleaned_paragraphs .append ("")
            continue 

        stats ["paragraphs"]+=1 


        ssn_matches =re .findall (r"\b\d{3}[- ]\d{2}[- ]\d{4}\b",s )
        for m in ssn_matches :
            masked =re .sub (r"\b(\d{3})[- ](\d{2})[- ](\d{4})\b",r"***-**-\3",m )
            diff_transformations .append ((m ,masked ,"Sensitive PII Masked (SSN)"))
            stats ["pii"]+=1 
        s =re .sub (r"\b(\d{3})[- ](\d{2})[- ](\d{4})\b",r"***-**-\3",s )

        card_matches =re .findall (r"\b(?:\d{4}[- ]){3}\d{4}\b",s )
        for m in card_matches :
            masked =re .sub (r"\b(?:\d{4}[- ]){3}(\d{4})\b",r"****-****-****-\1",m )
            diff_transformations .append ((m ,masked ,"Sensitive PII Masked (Credit Card)"))
            stats ["pii"]+=1 
        s =re .sub (r"\b(?:\d{4}[- ]){3}(\d{4})\b",r"****-****-****-\1",s )
        s =re .sub (r"\b\d{16}\b",lambda m :f"****-****-****-{m .group (0 )[-4 :]}",s )

        phone_iter =list (re .finditer (r"\b(?:\+?1[-. ]?)?\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})\b",s ))
        for pm in phone_iter :
            orig_p =pm .group (0 )
            masked_p =f"***-***-{pm .group (3 )}"
            diff_transformations .append ((orig_p ,masked_p ,"Sensitive PII Masked (Phone Number)"))
            stats ["pii"]+=1 
        s =re .sub (r"\b(?:\+?1[-. ]?)?\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})\b",r"***-***-\3",s )


        for pat ,rep in COMMON_TYPOS .items ():
            matches =re .findall (pat ,s ,flags =re .IGNORECASE )
            for m in matches :
                if m .lower ()!=rep .lower ():
                    target_rep =rep .capitalize ()if m [0 ].isupper ()else rep 
                    diff_transformations .append ((m ,target_rep ,"Grammar & Typo Repair"))
                    stats ["typos"]+=1 
            s =re .sub (pat ,rep ,s ,flags =re .IGNORECASE )


        dup_matches =re .findall (r"\b([a-zA-Z]+)\s+\1\b",s ,flags =re .IGNORECASE )
        for dm in dup_matches :
            diff_transformations .append ((f"{dm } {dm }",dm ,"Removed Duplicate Word"))
            stats ["typos"]+=1 
        s =re .sub (r"\b([a-zA-Z]+)\s+\1\b",r"\1",s ,flags =re .IGNORECASE )


        curr_matches =re .findall (r"(-\$|\$-)(\d+(?:\.\d+)?)",s )
        for m in curr_matches :
            orig_c =f"{m [0 ]}{m [1 ]}"
            fixed_c =f"-${m [1 ]}.00"if "."not in m [1 ]else f"-${m [1 ]}"
            diff_transformations .append ((orig_c ,fixed_c ,"Currency Normalized"))
            stats ["currency"]+=1 

        s =re .sub (r"(-\$|\$-)(\d+(?:\.\d+)?)",lambda m :f"-${m .group (2 )}",s )
        s =re .sub (r"\$(\d+)(?!\.\d)",lambda m :f"${m .group (1 )}.00",s )


        s =re .sub (r"@+","@",s )
        s =re .sub (r"\s+([,.:;?!])",r"\1",s )
        s =re .sub (r"([,.:;?!])(?=[A-Za-z])",r"\1 ",s )
        s =re .sub (r"\s{2,}"," ",s )


        s =re .sub (r"(^|[.?!]\s+)([a-z])",lambda m :m .group (1 )+m .group (2 ).upper (),s )

        cleaned_paragraphs .append (s )

    corrected_text ="\n".join (cleaned_paragraphs )
    return corrected_text ,diff_transformations ,stats 
