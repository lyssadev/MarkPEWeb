import requests
import os
import re
import json
from colorama import init, Fore
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

init(autoreset=True)

file_path = 'keys.tsv'
list_path = "list.txt"
settings_file = "settings.json"

def xor_data(data, key):
    return bytes([b ^ key for b in data])

xor_key = 42

_u1_encoded = b'B^^ZY\x10\x05\x05Y_DLFE]OX\x1a\x1b\x04\\OXIOF\x04KZZ\x05HCD\x19\x18\x1e\x18\x1c\x1f'
_u2_encoded = b'B^^ZY\x10\x05\x05Y_DLFE]OX\x1a\x1b\x04\\OXIOF\x04KZZ\x05HCD\x19\x1e\x1d\x1c\x12'

_u1 = xor_data(_u1_encoded, xor_key).decode()
_u2 = xor_data(_u2_encoded, xor_key).decode()

def decrypt_data(encrypted_data, key):
    key = key.ljust(32, b'\0')[:32]
    iv = encrypted_data[:AES.block_size]
    ciphertext = encrypted_data[AES.block_size:]
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return plaintext

def read_settings(settings_file):
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as file:
            return json.load(file)
    else:
        return {}

def read_local_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return [line.strip() for line in file.readlines()]
    else:
        return []

def get_url_from_settings(key, default_url):
    settings = read_settings(settings_file)
    return settings.get(key, default_url)

def fetch_remote_data(url, is_encrypted, decryption_key=None):
    response = requests.get(url)
    response.raise_for_status()
    
    if is_encrypted:
        if not decryption_key:
            raise ValueError("Decryption key required.")
        encrypted_data = response.content
        decrypted_data = decrypt_data(encrypted_data, decryption_key)
        return [line.strip() for line in decrypted_data.decode('utf-8').splitlines()]
    else:
        return [line.strip() for line in response.text.splitlines()]

def update_keys():
    settings = read_settings(settings_file)
    tsv_url = get_url_from_settings("tsv", _u2)
    is_encrypted = tsv_url == _u2
    decryption_key = b'Nz9K1WvfZ5bEN2rjpzyURRDIB7zJ1ojb' if is_encrypted else None

    if settings.get("UpdateKeys", "True") == "False":
        print("Auto-update Keys is disabled.")
        return
    
    print("Checking for new keys...", end='', flush=True)
    local_data = read_local_file(file_path)
    
    try:
        remote_data = fetch_remote_data(tsv_url, is_encrypted, decryption_key)
        if local_data != remote_data:
            num_new_lines = len(remote_data) - len(local_data)
            with open(file_path, 'w') as file:
                file.write('\n'.join(remote_data) + '\n')
            print("\r" + " " * len("Checking for new keys...") + "\r", end="", flush=True)
            print(Fore.GREEN + f"Keys updated! +{num_new_lines} added")
        else:
            print("\r" + " " * len("Checking for new keys...") + "\r", end="", flush=True)
    except Exception as e:
        print("\r" + " " * len("Checking for new keys...") + "\r", end="", flush=True)
        print(Fore.RED + f"Failed to update keys")

def normalize_text(text):
    text = re.sub(r'[^\x20-\x7E]', '', text)
    return text.strip()

def check_dlc_list(force_update_list=False):
    settings = read_settings(settings_file)
    list_url = get_url_from_settings("list", _u1)
    
    if not force_update_list and settings.get("UpdateKeys", "True") == "False":
        return [], False
        
    print("Checking for new dlc list...", end='', flush=True)
    local_data = read_local_file(list_path)
    
    try:
        remote_data = fetch_remote_data(list_url, False)
        local_data = [normalize_text(line) for line in local_data]
        remote_data = [normalize_text(line) for line in remote_data]
        new_lines = [line for line in remote_data if line not in local_data]
        num_new_lines = len(new_lines)
        
        if num_new_lines > 0:
            with open(list_path, 'w', encoding='utf-8') as file:
                file.write('\n'.join(remote_data) + '\n')
            print("\r" + " " * len("Checking for new dlc list...") + "\r", end="", flush=True)
            print(Fore.GREEN + f"List updated! +{num_new_lines} added")
            print("(type --new to see the new items)")
            
        return new_lines, num_new_lines > 0
    except Exception as e:
        print("\r" + " " * len("Checking for new dlc list...") + "\r", end="", flush=True)
        print(Fore.RED + f"Failed to update dlc list")
        return [], False

def force_update_keys():
    tsv_url = get_url_from_settings("tsv", _u2)
    is_encrypted = tsv_url == _u2
    decryption_key = b'Nz9K1WvfZ5bEN2rjpzyURRDIB7zJ1ojb' if is_encrypted else None

    local_data = read_local_file(file_path)

    try:
        remote_data = fetch_remote_data(tsv_url, is_encrypted, decryption_key)
        
        if local_data != remote_data:
            num_new_lines = len(remote_data) - len(local_data)
            with open(file_path, 'w') as file:
                file.write('\n'.join(remote_data) + '\n')
            print(Fore.GREEN + f"Keys updated! +{num_new_lines} added")
        else:
            print(Fore.GREEN + "Keys are already up to date!")
    except Exception as e:
        print(Fore.RED + f"Failed to update keys")
