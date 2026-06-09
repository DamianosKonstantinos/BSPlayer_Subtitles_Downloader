import os
import argparse
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
def download_subtitle(subdomain, handle, movie_hash, movie_size, movie_path, force=False):
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
            
            # Try preferred languages first (Greek), then fallback (English)
            for target_lang in ['gre', 'eng']:
                for item in root.iter('item'):
                    lang_tag = item.find('.//subLang')
                    link_tag = item.find('.//subDownloadLink')
                    if lang_tag is not None and lang_tag.text == target_lang:
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

                                # Skip if file already exists and not force
                                if not DOWNLOAD_ALL_VERSIONS and os.path.exists(sub_filename):
                                    if not force:
                                        print(f"[=] {movie_name}: Subtitle already exists, skipping.")
                                        return True
                                    # Backup existing file before overwrite
                                    backup_filename = f"{sub_filename}.bak"
                                    os.replace(sub_filename, backup_filename)
                                    print(f"[*] {movie_name}: Backed up existing subtitle to {os.path.basename(backup_filename)}")

                                with open(sub_filename, "w", encoding="utf-8-sig") as f:
                                    f.write(text_content)
                                
                                #Αν το flag είναι true συνεχίζει την αναζήτηση όλων των πιθανών υποτίτλων
                                if DOWNLOAD_ALL_VERSIONS:
                                    lang_label = "Greek" if target_lang == 'gre' else "English"
                                    print(f"[+] {movie_name}: Downloaded {lang_label} version #{sub_counter}")
                                    sub_counter += 1
                                    found_any = True
                                else:
                                    lang_label = "Greek" if target_lang == 'gre' else "English"
                                    print(f"[+] {movie_name}: Success! {lang_label} subtitle downloaded and fixed.")
                                    return True
                                
                            except Exception as e:
                                print(f"[-] {movie_name}: Processing error: {e}")
                
                # If found in this language pass, don't try next language
                if found_any or (not DOWNLOAD_ALL_VERSIONS and sub_counter > 1):
                    return True
            
            return found_any
    except Exception as e:
        print(f"[-] Error connecting to {subdomain.upper()}: {e}")
    return False


# Main Loop
def run_batch_test(folder_path, force=False):
    print("=" * 60)
    print(f"BS.Player SOAP Subtitle Downloader")
    print("=" * 60)
    
    valid_extensions = ('.mp4', '.mkv', '.avi')
    movie_files = []
    
    if os.path.isfile(folder_path):
        # Single file provided
        if folder_path.lower().endswith(valid_extensions):
            movie_files = [folder_path]
    else:
        # Folder provided - recursively search subdirectories
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(valid_extensions):
                    movie_files.append(os.path.join(root, f))

    if not movie_files:
        print("[-] No video files found.")
        return

    #Υπάρχουν αρκετοί ακόμα subdomains αλλά για γνωστές ταινίες και οικονομία χρόνου κοιτάμε τους πρώτους 4
    subdomains = ['s1', 's2', 's3', 's4']
    success_count = 0
    
    for full_path in movie_files:
        movie_name = os.path.basename(full_path)
        m_hash, m_size = get_file_info(full_path)
        if not m_hash:
            continue
            
        downloaded = False
        for sub in subdomains:
            handle = get_soap_session(sub)
            if not handle:
                continue
            if download_subtitle(sub, handle, m_hash, m_size, full_path, force=force):
                success_count += 1
                downloaded = True
                break 
                
        if not downloaded:
            print(f"[-] {movie_name}: No subtitles found.")
                
    print("\n" + "=" * 60)
    print(f"Finished: {success_count}/{len(movie_files)} movies processed successfully.")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BS.Player SOAP Subtitle Downloader")
    parser.add_argument("target", nargs="?", default=os.getcwd(), help="Video file or folder to scan (default: current working directory)")
    parser.add_argument("-f", "--force", action="store_true", help="Force redownload and overwrite existing subtitles (creates .bak backup)")
    args = parser.parse_args()

    if os.path.exists(args.target):
        run_batch_test(args.target, force=args.force)
    else:
        print(f"[-] Target path does not exist: {args.target}")