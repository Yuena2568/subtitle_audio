import sqlite3, tempfile, shutil, os, json, base64, ctypes, ctypes.wintypes
from Cryptodome.Cipher import AES

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

def dpapi_decrypt(encrypted):
    blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
    blob_out = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return result
    return None

def get_master_key():
    local_state_path = os.path.expanduser(r'~\AppData\Local\Microsoft\Edge\User Data\Local State')
    with open(local_state_path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])[5:]  # strip 'DPAPI'
    return dpapi_decrypt(encrypted_key)

def decrypt_cookie(encrypted_value, master_key):
    if not encrypted_value:
        return ''
    prefix = encrypted_value[:3]
    if prefix in (b'v10', b'v11'):
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:-16]
        tag = encrypted_value[-16:]
        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    else:
        result = dpapi_decrypt(encrypted_value)
        return result.decode('utf-8') if result else ''

def main():
    edge_data = os.path.expanduser(r'~\AppData\Local\Microsoft\Edge\User Data')
    
    print('Getting master key...')
    master_key = get_master_key()
    print(f'Master key: {len(master_key)} bytes')
    
    src = os.path.join(edge_data, 'Default', 'Network', 'Cookies')
    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, 'Cookies')
    shutil.copy2(src, dst)
    
    conn = sqlite3.connect(dst)
    cur = conn.cursor()
    cur.execute("SELECT host_key, name, encrypted_value, path, expires_utc, is_secure FROM cookies WHERE host_key LIKE '%bilibili%'")
    rows = cur.fetchall()
    print(f'Found {len(rows)} bilibili cookies')
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cookies_path = os.path.join(script_dir, 'cookies.txt')
    with open(cookies_path, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\n# Generated from Edge (decrypted)\n\n')
        for host, name, enc_val, path, expires, secure in rows:
            value = decrypt_cookie(enc_val, master_key)
            secure_str = 'TRUE' if secure else 'FALSE'
            unix_expires = (expires - 11644473600000000) // 1000000 if expires > 0 else 0
            if host and not host.startswith('.'):
                host = '.' + host
            f.write(f'{host}\tTRUE\t{path}\t{secure_str}\t{unix_expires}\t{name}\t{value}\n')
    
    print(f'Cookies saved to {cookies_path}')
    conn.close()
    shutil.rmtree(tmpdir)

if __name__ == '__main__':
    main()
