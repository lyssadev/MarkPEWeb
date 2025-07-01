import requests
import os
import json
import binascii
import base64
import struct
import hashlib
import datetime
import time

import colorama
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

TITLE_ID = "20CA2"
TITLE_SHARED_SECRET = "S8RS53ZEIGMYTYG856U3U19AORWXQXF41J7FT3X9YCWAC7I35X"

PLAYFAB_HEADERS = {
"User-Agent": "libhttpclient/1.0.0.0", 
"Content-Type": "application/json", 
"Accept-Language": "en-US"
}

PLAYFAB_SESSION = requests.Session()
PLAYFAB_SESSION.headers.update(PLAYFAB_HEADERS)

PLAYFAB_DOMAIN = "https://" + TITLE_ID.lower() + ".playfabapi.com"

SETTING_FILE = "settings.json"
PLAYFAB_SETTINGS = {}

def sendPlayFabRequest(endpoint, data, hdrs={}):
    response = PLAYFAB_SESSION.post(PLAYFAB_DOMAIN + endpoint, json=data, headers=hdrs).json()
    if response['code'] != 200:
        print(response)
        return response
    else:
        return response['data']
        
def genCustomId():
    return "MCPF"+binascii.hexlify(os.urandom(16)).decode("UTF-8").upper()
    
def genPlayerSecret():
    return base64.b64encode(os.urandom(32)).decode("UTF-8")
    
def getMojangCsp():
    return base64.b64decode(sendPlayFabRequest("/Client/GetTitlePublicKey", {
        "TitleId":TITLE_ID,
        "TitleSharedSecret": TITLE_SHARED_SECRET
    })['RSAPublicKey'])
    
def importCspKey(csp):
    e = struct.unpack("I", csp[0x10:0x14])[0]
    n = bytearray(csp[0x14:])
    n.reverse()
    n = int(binascii.hexlify(n), 16)
    return RSA.construct((n, e))

def genPlayFabTimestamp():
    return datetime.datetime.now().isoformat()+"Z"

def genPlayFabSignature(requestBody, timestamp):
    sha256 = hashlib.sha256()
    sha256.update(requestBody.encode("UTF-8") + b"." + timestamp.encode("UTF-8") + b"." + configGet("PLAYER_SECRET").encode("UTF-8"))
    return base64.b64encode(sha256.digest())

def configLoad():
    global PLAYFAB_SETTINGS
    global SETTING_FILE
    if os.path.exists(SETTING_FILE):
        PLAYFAB_SETTINGS = json.loads(open(SETTING_FILE, "r").read())
        
def configGet(key):
    global PLAYFAB_SETTINGS
    configLoad()
    if key in PLAYFAB_SETTINGS:
        return PLAYFAB_SETTINGS[key]
    return None
    
    
def configSet(key, newValue):
    global PLAYFAB_SETTINGS  
    configLoad()    
    PLAYFAB_SETTINGS[key] = newValue
    open(SETTING_FILE, "w").write(json.dumps(PLAYFAB_SETTINGS))
    return newValue
    
def LoginWithCustomId():
    global TITLE_ID

    customId = configGet("CUSTOM_ID")
    playerSecret = configGet("PLAYER_SECRET")
    createNewAccount = False

    if customId is None:
        customId = genCustomId()
        createNewAccount = True

    if playerSecret is None:
        playerSecret = genPlayerSecret()
        createNewAccount = True

    configSet("CUSTOM_ID", customId)
    configSet("PLAYER_SECRET", playerSecret)

    payload = {
        "InfoRequestParameters": {
            "GetCharacterInventories": False,
            "GetCharacterList": False,
            "GetPlayerProfile": True,
            "GetPlayerStatistics": False,
            "GetTitleData": False,
            "GetUserAccountInfo": True,
            "GetUserData": False,
            "GetUserInventory": False,
            "GetUserReadOnlyData": False,
            "GetUserVirtualCurrency": False,
            "PlayerStatisticNames": None,
            "ProfileConstraints": None,
            "TitleDataKeys": None,
            "UserDataKeys": None,
            "UserReadOnlyDataKeys": None
        },
        "TitleId": TITLE_ID
    }

    req = None
    attempt = 0
    max_attempts = 5

    while attempt < max_attempts:
        if createNewAccount:
            new_payload = {
                "CreateAccount": True,
                "TitleId": TITLE_ID,
                "InfoRequestParameters": payload["InfoRequestParameters"]
            }
            
            toEnc = json.dumps({"CustomId": customId, "PlayerSecret": playerSecret}).encode("UTF-8")
            pubkey = importCspKey(getMojangCsp())
            cipher_rsa = PKCS1_OAEP.new(pubkey)
            ciphertext = cipher_rsa.encrypt(toEnc)
            
            new_payload["EncryptedRequest"] = base64.b64encode(ciphertext).decode("UTF-8")
            
            req = sendPlayFabRequest("/Client/LoginWithCustomID", new_payload)
            
            configSet("CUSTOM_ID", customId)
            configSet("PLAYER_SECRET", playerSecret)
        else:
            login_payload = {
                "CustomId": customId,
                "CreateAccount": False,
                "TitleId": TITLE_ID,
                "InfoRequestParameters": payload["InfoRequestParameters"]
            }
            
            ts = genPlayFabTimestamp()
            sig = genPlayFabSignature(json.dumps(login_payload), ts)
            req = sendPlayFabRequest("/Client/LoginWithCustomID", login_payload, {"X-PlayFab-Signature": sig, "X-PlayFab-Timestamp": ts})

            if req and "errorCode" in req and req["errorCode"] == 1001:
                print("Account not found. Switching to account creation mode...")
                customId = genCustomId()
                playerSecret = genPlayerSecret()
                createNewAccount = True
                continue

        if req and "EntityToken" in req:
            break
        
        if req and "errorCode" in req and req["errorCode"] == 1199:
            wait_time = req.get("retryAfterSeconds", 5)
            print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            attempt += 1
            continue

        print(f"Request failed. Attempt {attempt+1} of {max_attempts}.")
        attempt += 1
        time.sleep(2)

    if not req or "EntityToken" not in req:
        raise Exception("Login failed after multiple attempts.")

    entitytoken = req["EntityToken"]["EntityToken"]
    PLAYFAB_SESSION.headers.update({"X-EntityToken": entitytoken})

    return req
    
def GetEntityToken(playfabId, accType):
    req = sendPlayFabRequest("/Authentication/GetEntityToken", {
       "Entity" : {
          "Id" : playfabId,
          "Type" : accType
       }
    })
    entitytoken = req["EntityToken"]
    PLAYFAB_SESSION.headers.update({"X-EntityToken": entitytoken})
    return req
                                                
def Search(query, orderBy, select, top, skip, customIds):
    if isinstance(customIds, str):
        filter_query = f"Id eq '{customIds}'"
    elif isinstance(customIds, list):
        filter_query = " or ".join([f"Id eq '{id}'" for id in customIds])
    else:
        raise ValueError("Invalid type for customIds. It should be a string or a list.")
    return sendPlayFabRequest("/Catalog/Search", {
                                                "count": True,
                                                "query": query,
                                                "filter": f"{filter_query}",
                                                "orderBy": orderBy,
                                                "scid": "4fc10100-5f7a-4470-899b-280835760c07",
                                                "select": select,
                                                "top": top,
                                                "skip": skip
                                                })

def SearchFriendlyUuid(query, orderBy, select, top, skip, customIds):
    if isinstance(customIds, list):
        filter_query = " or ".join([f"contentType eq 'MarketplaceDurableCatalog_V1.2' and tags/any(t: t eq '{id}')" for id in customIds])
    else:
        raise ValueError("Invalid type for customIds. It should be a string or a list.")
    
    return sendPlayFabRequest("/Catalog/Search", {
                                                "count": True,
                                                "query": query,
                                                "filter": f"{filter_query}",
                                                "orderBy": orderBy,
                                                "scid": "4fc10100-5f7a-4470-899b-280835760c07",
                                                "select": select,
                                                "top": top,
                                                "skip": skip
                                                })

def process_friendlyuuid(friendlyuuid):
    MAX_SEARCH = 150

    results_dict = {}

    total_friendlyuuid = len(friendlyuuid)
    processed_friendlyuuid = 0

    use_progress_bar = total_friendlyuuid > 300

    for i in range(0, len(friendlyuuid), MAX_SEARCH):
        chunk = list(friendlyuuid.keys())[i:i + MAX_SEARCH]
        search_result = SearchFriendlyUuid("", "creationDate ASC", "title", MAX_SEARCH, 0, chunk)
        search_results = search_result["Items"]

        if search_results:
            for item in search_results:
                result_uuid = item["Id"]
                if result_uuid not in results_dict:
                    results_dict[result_uuid] = []
                results_dict[result_uuid].append(item)
        else:
            print(f"No results found for {i+1}-{min(i+MAX_SEARCH, len(friendlyuuid))}")

        processed_friendlyuuid += len(chunk)
        if use_progress_bar:
            print_progress_bar(processed_friendlyuuid, total_friendlyuuid, prefix='Converting:', suffix='Complete', length=25)
        else:
            progress_percent = (processed_friendlyuuid / total_friendlyuuid) * 100
            print(f"Progress: {progress_percent:.2f}%\r", end="", flush=True)
            print()

    unique_lines = set()
    with open("personal_keys.tsv", "w", encoding="utf-8") as df_file:
        for result_uuid, items in results_dict.items():
            for item in items:
                display_properties = item.get("DisplayProperties", {})
                pack_identity = display_properties.get("packIdentity", [])
                for identity in pack_identity:
                    if identity["uuid"] in friendlyuuid:
                        pack_type = identity.get("type").replace("worldtemplate", "world_template")
                        custom_id = identity["uuid"]
                        key = friendlyuuid[custom_id]
                        line = f"{result_uuid}\t{custom_id}\t{pack_type}\t{key}\n"
                        unique_lines.add(line)

        for line in unique_lines:
            df_file.write(line)

    unique_info_lines = set()
    with open("personal_list.txt", "w", encoding="utf-8") as f:
        for result_uuid, items in results_dict.items():
            for item in items:
                title = item.get("Title", {}).get("en-US", "")
                creator_name = item.get("DisplayProperties", {}).get("creatorName", "")
                tags = item.get("Tags", [])
                pack_type = "DLC" if "worldtemplate" in tags else "DLC"
                pack_type = "Addon" if "addon" in tags else pack_type
                pack_type = "TexturePack" if "resourcepack" in tags else pack_type
                pack_type = "Mashup" if "mashup" in tags else pack_type
                info_line = f"{title} ( {creator_name} ) - {pack_type} {result_uuid}\n"
                unique_info_lines.add(info_line)

        for info_line in unique_info_lines:
            f.write(info_line)

    print(f"{colorama.Fore.GREEN}{len(unique_lines)} converted keys!{colorama.Fore.RESET}")

def Search_name(query, orderBy, select, top, skip, search_type, search_term=None):
    base_filter = "(contentType eq 'MarketplaceDurableCatalog_V1.2')"
    tags_filter = {
        "texture": "tags/any(t: t eq 'resourcepack')",
        "mashup": "tags/any(t: t eq 'mashup')",
        "addon": "tags/any(t: t eq 'addon')",
        "persona": "(contentType eq 'PersonaDurable')",
        "capes": "(displayProperties/pieceType eq 'persona_capes')",
        "hidden": "tags/any(t: t eq 'hidden_offer')",
        "skin": "tags/any(t: t eq 'skinpack')"
    }

    if search_type in ["name", "hidden", "newest", "skin"]:
        filter_query = base_filter
        if search_type == "hidden":
            filter_query += f" and {tags_filter['hidden']}"
            search_query = None
        elif search_type == "skin":
            filter_query += f" and {tags_filter['skin']}"
            search_query = None
        elif search_type == "newest":
            filter_query = base_filter
            search_query = None
        else:
            search_query = f"\"{search_term}\""
        
        request_payload = {
            "count": True,
            "query": query,
            "filter": filter_query,
            "orderBy": "creationDate DESC",
            "scid": "4fc10100-5f7a-4470-899b-280835760c07",
            "select": select,
            "top": top,
            "skip": skip,
            "search": search_query
        }
        
        response = sendPlayFabRequest("/Catalog/Search", request_payload)
        items = response.get("Items", [])
        return items

    else:
        if search_type == "texture":
            filter_query = f"{base_filter} and {tags_filter['texture']}"
            search_query = None
        elif search_type == "mashup":
            filter_query = f"{base_filter} and {tags_filter['mashup']}"
            search_query = None
        elif search_type == "addon":
            filter_query = f"{base_filter} and {tags_filter['addon']}"
            search_query = None
        elif search_type == "allhidden":
            filter_query = f"{base_filter} and {tags_filter['hidden']}"
            search_query = None
        elif search_type == "persona":
            filter_query = f"{tags_filter['persona']}"
            search_query = f"{search_term}"
        elif search_type == "capes":
            filter_query = f"{tags_filter['capes']}"
            search_query = None

        all_items = []
        while True:
            request_payload = {
                "count": True,
                "query": query,
                "filter": filter_query,
                "orderBy": orderBy,
                "scid": "4fc10100-5f7a-4470-899b-280835760c07",
                "select": select,
                "top": top,
                "skip": skip
            }

            if search_query:
                request_payload["search"] = search_query

            response = sendPlayFabRequest("/Catalog/Search", request_payload)
            total_count = response.get("Count", 0)

            items = response.get("Items", [])
            all_items.extend(items)

            if len(items) < top or len(all_items) >= total_count:
                break

            skip += top
            if total_count - skip < top:
                top = total_count - skip

        return all_items

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    if iteration == total:
        print()

def main(custom_id):

    MAX_SEARCH = 300

    results_dict = {}

    if isinstance(custom_id, list):
        custom_ids = custom_id
    else:
        custom_ids = [custom_id]

    total_chunks = (len(custom_ids) + MAX_SEARCH - 1) // MAX_SEARCH

    show_progress_bar = len(custom_ids) > 100

    # Split the custom_ids list into chunks
    for i in range(0, len(custom_ids), MAX_SEARCH):
        chunk = custom_ids[i:i + MAX_SEARCH]
        search_result = Search("", "creationDate DESC", "contents", MAX_SEARCH, 0, chunk)
        search_results = search_result["Items"]

        if search_results:
            # Merge the results into the results_dict
            results_dict.update({item["Id"]: item for item in search_results})
        else:
            print(colorama.Fore.RED + f"No results found for {i+1}-{min(i+MAX_SEARCH, len(custom_ids))}")

        if show_progress_bar:
            # Print progress bar
            print_progress_bar(i // MAX_SEARCH + 1, total_chunks, prefix='Searching:', suffix='Complete', length=50)

    return results_dict
