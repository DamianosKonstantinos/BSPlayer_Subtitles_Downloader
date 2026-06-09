import os
import sys
import xml.etree.ElementTree as ET
import gzip
import requests

DOWNLOAD_ALL_VERSIONS = False

# Υπολογισμός του BS.Player Hash
def get_file_info(file_path):
    try:
        file_size = os.path.getsize(file_path)
        hash_val = file_size
        with open(file_path, "rb") as f:
            chunk = f.read(65536)
            hash_val += sum(int.from_bytes(chunk[i:i+8], 'little') for i in range(0, len(chunk), 8))
            f.seek(max(0, file_size - 65536), 0)
            chunk = f.read(65536)
            hash_val += sum(int.from_bytes(chunk[i:i+8], 'little') for i in range(0, len(chunk), 8))
        return f"{hash_val & 0xFFFFFFFFFFFFFFFF:016x}", file_size
    except Exception as e:
        print(f"[-] Error reading file {os.path.basename(file_path)}: {e}")
        return None, None

# SOAP Login Handshake
def get_soap_session(subdomain):
    url = f"http://{subdomain}.api.bsplayer-subtitles.com/v1.php"
    headers = {
        'User-Agent': 'BSPlayer/2.x (1106.12378)',
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://api.bsplayer-subtitles.com/v1.php#logIn"'
    }
    login_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://{subdomain}.api.bsplayer-subtitles.com/v1.php">
    <SOAP-ENV:Body>
        <ns1:logIn>
            <username></username>
            <password></password>
            <AppID>BSPlayer v2.7</AppID>
        </ns1:logIn>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
    try:
        res = requests.post(url, headers=headers, data=login_xml, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for data_tag in root.iter('data'):
                if data_tag.text:
                    return data_tag.text
    except Exception:
        pass
    return None

# SOAP Αναζήτηση Υπότιτλου και Βελτιστοποίηση Αποτελεσμάτων
def download_subtitle(subdomain, handle, movie_hash, movie_size, movie_path):
    movie_name = os.path.basename(movie_path)
    movie_dir = os.path.dirname(movie_path)
    url = f"http://{subdomain}.api.bsplayer-subtitles.com/v1.php"
    headers = {
        'User-Agent': 'BSPlayer/2.x (1106.12378)',
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://api.bsplayer-subtitles.com/v1.php#searchSubtitles"'
    }
    search_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" 
                   xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" 
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
                   xmlns:ns1="http://api.bsplayer-subtitles.com/v1.php">
    <SOAP-ENV:Body SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
        <ns1:searchSubtitles>
            <handle xsi:type="xsd:string">{handle}</handle>
            <movieHash xsi:type="xsd:string">{movie_hash}</movieHash>
            <movieSize xsi:type="xsd:string">{movie_size}</movieSize>
            <languageId xsi:type="xsd:string">gre,ell,eng,grc</languageId>
            <imdbId xsi:type="xsd:string">*</imdbId>
        </ns1:searchSubtitles>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
    try:
        res = requests.post(url, headers=headers, data=search_xml, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            found_any = False
            sub_counter = 1
            for item in root.iter('item'):
                lang_tag = item.find('.//subLang')
                link_tag = item.find('.//subDownloadLink')
                if lang_tag is not None and lang_tag.text == 'gre':
                    if link_tag is not None and link_tag.text:
                        sub_url = link_tag.text
                        movie_base = os.path.splitext(movie_name)[0]
                        sub_filename = os.path.join(movie_dir, f"{movie_base}_{sub_counter}.srt" if DOWNLOAD_ALL_VERSIONS else f"{movie_base}.srt")
                        sub_res = requests.get(sub_url, headers={'User-Agent': 'BSPlayer/2.x (1106.12378)'})
                        try:
                            #Ο server επιστρέφει τα δεδομένα συμπιεσμένα
                            decompressed_bytes = gzip.decompress(sub_res.content)
                            text_content = None

                            #Ελέγχουμε σε ποια κωδικοποίηση εμφανίζονται τα ελληνικά φωνήεντα (θα είναι αυτή που θα χρησιμοποιηθεί)
                            for enc in ['utf-8', 'windows-1253', 'iso-8859-7', 'utf-16']:
                                try:
                                    text_content = decompressed_bytes.decode(enc)
                                    if "-->" in text_content and any(c in text_content for c in "αεηιουωΑΕΗΙΟΥΩ"):
                                        break
                                except UnicodeDecodeError:
                                    continue
                            if not text_content:
                                text_content = decompressed_bytes.decode('windows-1253', errors='replace')
                            with open(sub_filename, "w", encoding="utf-8-sig") as f:
                                f.write(text_content)
                            
                            #Αν το flag είναι true συνεχίζει την αναζήτηση όλων των πιθανών υποτίτλων
                            if DOWNLOAD_ALL_VERSIONS:
                                print(f"[+] {movie_name}: Downloaded version #{sub_counter}")
                                sub_counter += 1
                                found_any = True
                            else:
                                print(f"[+] {movie_name}: Success! Subtitle downloaded and fixed.")
                                return True
                            
                        except Exception as e:
                            print(f"[-] {movie_name}: Processing error: {e}")
            return found_any
    except Exception as e:
        print(f"[-] Error connecting to {subdomain.upper()}: {e}")
    return False


# Main Loop
def run_batch_test(folder_path):
    print("=" * 60)
    print(f"BS.Player SOAP Subtitle Downloader")
    print("=" * 60)
    
    if os.path.isfile(folder_path):
        movie_files = [os.path.basename(folder_path)]
        folder_path = os.path.dirname(folder_path)
    else:
        valid_extensions = ('.mp4', '.mkv', '.avi')
        # Case-insensitive extension check for Linux compatibility
        movie_files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]

    if not movie_files:
        print("[-] No video files found.")
        return

    #Υπάρχουν αρκετοί ακόμα subdomains αλλά για γνωστές ταινίες και οικονομία χρόνου κοιτάμε τους πρώτους 4
    subdomains = ['s1', 's2', 's3', 's4']
    success_count = 0
    
    for movie in movie_files:
        full_path = os.path.join(folder_path, movie)
        m_hash, m_size = get_file_info(full_path)
        if not m_hash:
            continue
            
        downloaded = False
        for sub in subdomains:
            handle = get_soap_session(sub)
            if not handle:
                continue
            if download_subtitle(sub, handle, m_hash, m_size, full_path):
                success_count += 1
                downloaded = True
                break 
                
        if not downloaded:
            print(f"[-] {movie}: No Greek subtitles found.")
                
    print("\n" + "=" * 60)
    print(f"Finished: {success_count}/{len(movie_files)} movies processed successfully.")
    print("=" * 60)

if __name__ == "__main__":
    # Το script τρέχει για ταινίες που περνάει ο χρήστης ως παράμετρο
    # Αν ο χρήστης δεν δώσει παράμετρο, χρησιμοποιούμε το working directory
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    if os.path.exists(target):
        run_batch_test(target)
    else:
        print(f"[-] Target path does not exist: {target}")