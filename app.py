from flask import Flask, render_template, request, jsonify
try:
    from flask_cors import CORS
    cors_available = True
except ImportError:
    cors_available = False
import pandas as pd
import numpy as np
from datetime import datetime
import glob
import os

app = Flask(__name__)
if cors_available:
    CORS(app)

def loe_hinnad(failitee):
    """Loeb CSV faili ja parsib hinnad"""
    try:
        encodings = ['cp1252', 'windows-1252', 'latin1', 'iso-8859-1', 'utf-8']
        df = None
        
        for enc in encodings:
            try:
                df = pd.read_csv(failitee, sep=';', encoding=enc)
                if len(df.columns) >= 3:
                    break
            except:
                continue
        
        if df is None or len(df.columns) < 3:
            return pd.DataFrame()
        
        date_col = None
        price_col = None
        
        for col in df.columns:
            if 'Kuup' in col or 'aeg' in col.lower() or 'date' in col.lower():
                date_col = col
            if 'NPS' in col or 'hind' in col.lower() or 'price' in col.lower():
                price_col = col
        
        if date_col is None or price_col is None:
            if len(df.columns) >= 3:
                date_col = df.columns[1]
                price_col = df.columns[2]
            else:
                return pd.DataFrame()
        
        df['Kuupäev'] = pd.to_datetime(df[date_col], format='%d.%m.%Y %H:%M', errors='coerce')
        df['Hind'] = pd.to_numeric(df[price_col].astype(str).str.replace(',', '.'), errors='coerce')
        df = df.dropna(subset=['Kuupäev', 'Hind'])
        df = df.sort_values('Kuupäev').reset_index(drop=True)
        
        return df[['Kuupäev', 'Hind']]
    except Exception as e:
        return pd.DataFrame()

def optimeeri_tsukkel(hinnad_paev, aku_mahtuvus_mwh, aku_voimsus_mw, efektiivsus, max_aeg_vahel):
    """
    Optimeerib ühe päeva kohta laadimise ja tühjendamise hetke.
    Arvestab liitumise võimsust - laadimine ja müük võivad olla mitte-järjestikused tunnid.
    """
    if len(hinnad_paev) < 2:
        return None, None, 0
    
    tagastatav_energia = aku_mahtuvus_mwh * efektiivsus
    
    # Arvutame vajalikud tunnid
    laadimise_tunnid = int(np.ceil(aku_mahtuvus_mwh / aku_voimsus_mw))  # 100 MWh / 50 MW = 2 tundi
    tuhjendamise_tunnid = int(np.ceil(tagastatav_energia / aku_voimsus_mw))  # 87 MWh / 50 MW = 2 tundi
    
    max_tulu = float('-inf')
    parim_laadimine_indeksid = None
    parim_tuhjendamine_indeksid = None
    
    # Optimeerime laadimise - valime odavaimad tunnid
    # Võime valida järjestikused või mitte-järjestikused tunnid
    for laadimise_algus in range(len(hinnad_paev) - laadimise_tunnid + 1):
        # Variant 1: Järjestikused tunnid laadimiseks
        laadimise_järjestikused = list(range(laadimise_algus, laadimise_algus + laadimise_tunnid))
        if laadimise_algus + laadimise_tunnid > len(hinnad_paev):
            continue
        
        laadimise_kulu_järjestikused = sum(hinnad_paev.iloc[i]['Hind'] for i in laadimise_järjestikused) * aku_voimsus_mw
        
        # Variant 2: Optimeerime mitte-järjestikuste tundide valiku
        # Valime odavaimad tunnid päevast
        kogu_paev_hinnad = [(i, hinnad_paev.iloc[i]['Hind']) for i in range(len(hinnad_paev))]
        kogu_paev_hinnad.sort(key=lambda x: x[1])  # Sorteerime hinnad järgi
        odavaimad_tunnid = [idx for idx, _ in kogu_paev_hinnad[:laadimise_tunnid]]
        laadimise_kulu_mitte_järjestikused = sum(hinnad_paev.iloc[i]['Hind'] for i in odavaimad_tunnid) * aku_voimsus_mw
        
        # Valime parema variandi
        if laadimise_kulu_mitte_järjestikused < laadimise_kulu_järjestikused:
            laadimise_indeksid = odavaimad_tunnid
            laadimise_kulu = laadimise_kulu_mitte_järjestikused
        else:
            laadimise_indeksid = laadimise_järjestikused
            laadimise_kulu = laadimise_kulu_järjestikused
        
        # Laadimise lõpphetk
        laadimise_lopp = max(laadimise_indeksid)
        
        # Otsime tühjendamise hetki (peab olema pärast laadimist)
        tuhjendamise_algus_võimalik = laadimise_lopp + 1
        tuhjendamise_lopp_võimalik = min(laadimise_lopp + max_aeg_vahel + 1, len(hinnad_paev))
        
        if tuhjendamise_algus_võimalik >= len(hinnad_paev):
            continue
        
        # Optimeerime tühjendamise - valime kallimad tunnid müügiks
        for tuhjendamise_algus in range(tuhjendamise_algus_võimalik, tuhjendamise_lopp_võimalik - tuhjendamise_tunnid + 1):
            # Variant 1: Järjestikused tunnid tühjendamiseks
            tuhjendamise_järjestikused = list(range(tuhjendamise_algus, tuhjendamise_algus + tuhjendamise_tunnid))
            if tuhjendamise_algus + tuhjendamise_tunnid > len(hinnad_paev):
                continue
            
            # Arvutame müügitulu (arvestades efektiivsust)
            # Laaditud energia: laadimise_tunnid * aku_voimsus_mw
            # Tagastatav energia: laaditud energia * efektiivsus
            laaditud_energia = laadimise_tunnid * aku_voimsus_mw
            tagastatav_energia = laaditud_energia * efektiivsus
            
            # Variant 1: Järjestikused tunnid tühjendamiseks
            # Müüme tagastatava energia, jagame tühjendamise tundide vahel
            keskmine_hind_järjestikused = sum(hinnad_paev.iloc[i]['Hind'] for i in tuhjendamise_järjestikused) / tuhjendamise_tunnid
            tuhjendamise_tulu_järjestikused = tagastatav_energia * keskmine_hind_järjestikused
            
            # Variant 2: Optimeerime mitte-järjestikuste tundide valiku
            # Valime kallimad tunnid müügiks (vahemikus pärast laadimist)
            võimalikud_tunnid = [(i, hinnad_paev.iloc[i]['Hind']) 
                                 for i in range(tuhjendamise_algus_võimalik, tuhjendamise_lopp_võimalik)]
            võimalikud_tunnid.sort(key=lambda x: x[1], reverse=True)  # Sorteerime kallimad esimeseks
            kallimad_tunnid = [idx for idx, _ in võimalikud_tunnid[:tuhjendamise_tunnid]]
            keskmine_hind_mitte_järjestikused = sum(hinnad_paev.iloc[i]['Hind'] for i in kallimad_tunnid) / tuhjendamise_tunnid
            tuhjendamise_tulu_mitte_järjestikused = tagastatav_energia * keskmine_hind_mitte_järjestikused
            
            # Valime parema variandi
            if tuhjendamise_tulu_mitte_järjestikused > tuhjendamise_tulu_järjestikused:
                tuhjendamise_indeksid = kallimad_tunnid
                tuhjendamise_tulu = tuhjendamise_tulu_mitte_järjestikused
            else:
                tuhjendamise_indeksid = tuhjendamise_järjestikused
                tuhjendamise_tulu = tuhjendamise_tulu_järjestikused
            
            # Tulu = müügitulu - ostukulu
            tulu = tuhjendamise_tulu - laadimise_kulu
            
            if tulu > max_tulu:
                max_tulu = tulu
                parim_laadimine_indeksid = laadimise_indeksid
                parim_tuhjendamine_indeksid = tuhjendamise_indeksid
    
    if max_tulu == float('-inf'):
        return None, None, 0
    
    return parim_laadimine_indeksid, parim_tuhjendamine_indeksid, max_tulu

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/arvuta', methods=['POST'])
def arvuta():
    try:
        data = request.json
        aku_voimsus_mw = float(data.get('aku_voimsus_mw', 50))
        aku_mahtuvus_mwh = float(data.get('aku_mahtuvus_mwh', 100))
        efektiivsus = float(data.get('efektiivsus', 0.87))
        max_aeg_vahel = int(data.get('max_aeg_vahel', 8))
        
        # Loeme kõik CSV failid
        # Kasutame rakenduse kausta
        app_dir = os.path.dirname(os.path.abspath(__file__))
        csv_failid = glob.glob(os.path.join(app_dir, 'Tuulikutasu*.csv'))
        
        kogu_andmed = []
        for fail in csv_failid:
            df = loe_hinnad(fail)
            if not df.empty:
                kogu_andmed.append(df)
        
        if not kogu_andmed:
            return jsonify({'error': 'Andmeid ei leitud'}), 400
        
        kogu_df = pd.concat(kogu_andmed, ignore_index=True)
        kogu_df = kogu_df.sort_values('Kuupäev').reset_index(drop=True)
        
        kogu_df['Päev'] = kogu_df['Kuupäev'].dt.date
        kogu_df['Kuu'] = kogu_df['Kuupäev'].dt.to_period('M')
        
        tulemused = []
        kuu_tulud = {}
        kuu_hinnad = {}  # Keskmine NPS hind kuus
        
        unikaalsed_paevad = kogu_df['Päev'].unique()
        
        for paev in unikaalsed_paevad:
            paeva_andmed = kogu_df[kogu_df['Päev'] == paev].copy()
            
            if len(paeva_andmed) < 2:
                continue
            
            laadimine_idx, tuhjendamine_idx, tulu = optimeeri_tsukkel(
                paeva_andmed, aku_mahtuvus_mwh, aku_voimsus_mw, efektiivsus, max_aeg_vahel
            )
            
            if laadimine_idx is not None and tuhjendamine_idx is not None:
                kuu = paeva_andmed.iloc[0]['Kuu']
                
                tulemused.append({
                    'kuupaev': str(paev),
                    'kuu': str(kuu),
                    'tulu': float(tulu)
                })
                
                if kuu not in kuu_tulud:
                    kuu_tulud[kuu] = []
                kuu_tulud[kuu].append(tulu)
                
                # Arvutame kuu keskmise NPS hinna
                kuu_andmed = kogu_df[kogu_df['Kuu'] == kuu]
                if kuu not in kuu_hinnad:
                    kuu_hinnad[kuu] = float(kuu_andmed['Hind'].mean())
        
        # Arvutame kuude statistika
        kuu_statistika = []
        kogu_tulu = 0
        kogu_tsuklite_arv = 0
        
        for kuu in sorted(kuu_tulud.keys()):
            kuu_tulu = sum(kuu_tulud[kuu])
            tsuklite_arv = len(kuu_tulud[kuu])
            keskmine_tulu = kuu_tulu / tsuklite_arv if tsuklite_arv > 0 else 0
            keskmine_nps_hind = kuu_hinnad.get(kuu, 0)
            
            kogu_tulu += kuu_tulu
            kogu_tsuklite_arv += tsuklite_arv
            
            kuu_statistika.append({
                'kuu': str(kuu),
                'tsuklite_arv': tsuklite_arv,
                'kogutulu': float(kuu_tulu),
                'keskmine_tulu': float(keskmine_tulu),
                'keskmine_nps_hind': float(keskmine_nps_hind)
            })
        
        # Arvutame üldise keskmise
        uldine_keskmine = kogu_tulu / kogu_tsuklite_arv if kogu_tsuklite_arv > 0 else 0
        
        # Lisame erinevuse keskmisest
        for stat in kuu_statistika:
            stat['erinevus_keskmisest'] = float(stat['keskmine_tulu'] - uldine_keskmine)
        
        return jsonify({
            'kuu_statistika': kuu_statistika,
            'kokku_tsukleid': kogu_tsuklite_arv,
            'kogutulu': float(kogu_tulu),
            'keskmine_tulu': float(uldine_keskmine)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

