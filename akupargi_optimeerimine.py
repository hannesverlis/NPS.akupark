import pandas as pd
import numpy as np
from datetime import datetime
import glob
import os

# Parameetrid
AKU_MAHTUVUS_MWH = 100  # MWh (maksimaalne laadimismahtuvus)
AKU_VOIMSUS_MW = 50  # MW
EFEKTIIVSUS = 0.87  # 87%
MAX_AEG_VAHEL = 8  # tundi maksimaalselt laadimise ja tühjendamise vahel
# Laadime täielikult 100 MWh, tagastame 100 * 0.87 = 87 MWh
TAGASTATAV_ENERGIA = AKU_MAHTUVUS_MWH * EFEKTIIVSUS  # 87 MWh

def loe_hinnad(failitee):
    """Loeb CSV faili ja parsib hinnad"""
    try:
        # Loeme faili, proovime erinevaid kodeeringuid
        encodings = ['cp1252', 'windows-1252', 'latin1', 'iso-8859-1', 'utf-8']
        df = None
        
        for enc in encodings:
            try:
                df = pd.read_csv(failitee, sep=';', encoding=enc)
                # Kontrollime, kas veerud on õiged
                if len(df.columns) >= 3:
                    break
            except:
                continue
        
        if df is None or len(df.columns) < 3:
            return pd.DataFrame()
        
        # Leia õige veeru nimi (võib olla erinevates kodeeringutes)
        date_col = None
        price_col = None
        
        for col in df.columns:
            if 'Kuup' in col or 'aeg' in col.lower() or 'date' in col.lower():
                date_col = col
            if 'NPS' in col or 'hind' in col.lower() or 'price' in col.lower():
                price_col = col
        
        if date_col is None or price_col is None:
            # Proovime kasutada teist veergu kuupäevaks ja kolmandat hinnaks
            if len(df.columns) >= 3:
                date_col = df.columns[1]
                price_col = df.columns[2]
            else:
                return pd.DataFrame()
        
        # Parsime kuupäeva
        df['Kuupäev'] = pd.to_datetime(df[date_col], format='%d.%m.%Y %H:%M', errors='coerce')
        
        # Parsime hinna (komaga kümnendkohad)
        df['Hind'] = pd.to_numeric(df[price_col].astype(str).str.replace(',', '.'), errors='coerce')
        
        # Eemaldame NaN väärtused
        df = df.dropna(subset=['Kuupäev', 'Hind'])
        
        # Sorteerime kuupäeva järgi
        df = df.sort_values('Kuupäev').reset_index(drop=True)
        
        return df[['Kuupäev', 'Hind']]
    except Exception as e:
        import sys
        try:
            print(f"Viga faili {failitee} lugemisel: {e}", file=sys.stderr)
        except:
            pass
        return pd.DataFrame()

def optimeeri_tsukkel(hinnad_paev):
    """
    Optimeerib ühe päeva kohta laadimise ja tühjendamise hetke.
    Tagastab: (laadimise_indeks, tühjendamise_indeks, tulu)
    """
    if len(hinnad_paev) < 2:
        return None, None, 0
    
    max_tulu = 0
    parim_laadimine = None
    parim_tuhjendamine = None
    
    # Arvutame laadimiseks vajaliku aja (tunnid)
    laadimise_ajad = AKU_MAHTUVUS_MWH / AKU_VOIMSUS_MW  # 100 / 50 = 2 tundi
    
    # Itereerime läbi kõik võimalikud laadimise hetked
    for i in range(len(hinnad_paev)):
        # Laadimise kulu (ostame energiat)
        # Laadime täielikult AKU_MAHTUVUS_MWH (100 MWh) energiat
        laadimise_hind = hinnad_paev.iloc[i]['Hind']
        laadimise_kulu = AKU_MAHTUVUS_MWH * laadimise_hind  # EUR
        
        # Otsime maksimaalselt 8 tunni jooksul parimat müügihinda
        max_indeks = min(i + MAX_AEG_VAHEL + 1, len(hinnad_paev))
        
        for j in range(i + 1, max_indeks):
            # Tühjendamise tulu (müüme energiat)
            # Efektiivsusega saame tagasi: 100 MWh * 0.87 = 87 MWh
            tuhjendamise_hind = hinnad_paev.iloc[j]['Hind']
            tuhjendamise_tulu = TAGASTATAV_ENERGIA * tuhjendamise_hind  # EUR
            
            # Tulu = müügitulu - ostukulu
            tulu = tuhjendamise_tulu - laadimise_kulu
            
            if tulu > max_tulu:
                max_tulu = tulu
                parim_laadimine = i
                parim_tuhjendamine = j
    
    return parim_laadimine, parim_tuhjendamine, max_tulu

def simuleeri_akupark():
    """Peamine simuleerimise funktsioon"""
    
    # Leia kõik CSV failid
    csv_failid = glob.glob(os.path.join('c:\\Cursor\\NPS', 'Tuulikutasu*.csv'))
    
    if not csv_failid:
        print("CSV faile ei leitud!")
        return
    
    print(f"Leitud {len(csv_failid)} faili")
    
    # Loeme kõik andmed
    kogu_andmed = []
    for fail in csv_failid:
        print(f"Loetakse faili: {os.path.basename(fail)}")
        df = loe_hinnad(fail)
        if not df.empty:
            kogu_andmed.append(df)
    
    if not kogu_andmed:
        print("Andmeid ei leitud!")
        return
    
    # Ühendame kõik andmed
    kogu_df = pd.concat(kogu_andmed, ignore_index=True)
    kogu_df = kogu_df.sort_values('Kuupäev').reset_index(drop=True)
    
    print(f"Kokku {len(kogu_df)} tundi andmeid")
    
    # Rühmitame päevade kaupa
    kogu_df['Päev'] = kogu_df['Kuupäev'].dt.date
    kogu_df['Kuu'] = kogu_df['Kuupäev'].dt.to_period('M')
    
    # Optimeerime iga päeva kohta
    tulemused = []
    kuu_tulud = {}
    
    unikaalsed_paevad = kogu_df['Päev'].unique()
    
    for paev in unikaalsed_paevad:
        paeva_andmed = kogu_df[kogu_df['Päev'] == paev].copy()
        
        if len(paeva_andmed) < 2:
            continue
        
        laadimine_idx, tuhjendamine_idx, tulu = optimeeri_tsukkel(paeva_andmed)
        
        if laadimine_idx is not None and tuhjendamine_idx is not None:
            laadimise_aeg = paeva_andmed.iloc[laadimine_idx]['Kuupäev']
            tuhjendamise_aeg = paeva_andmed.iloc[tuhjendamine_idx]['Kuupäev']
            laadimise_hind = paeva_andmed.iloc[laadimine_idx]['Hind']
            tuhjendamise_hind = paeva_andmed.iloc[tuhjendamine_idx]['Hind']
            kuu = paeva_andmed.iloc[0]['Kuu']
            
            tulemused.append({
                'Kuupäev': paev,
                'Kuu': str(kuu),
                'Laadimise_aeg': laadimise_aeg,
                'Tühjendamise_aeg': tuhjendamise_aeg,
                'Laadimise_hind': laadimise_hind,
                'Tühjendamise_hind': tuhjendamise_hind,
                'Tulu': tulu,
                'Aeg_vahel': (tuhjendamise_aeg - laadimise_aeg).total_seconds() / 3600
            })
            
            # Kogume kuude kaupa
            if kuu not in kuu_tulud:
                kuu_tulud[kuu] = 0
            kuu_tulud[kuu] += tulu
    
    # Loome tulemuste DataFrame
    tulemused_df = pd.DataFrame(tulemused)
    
    if tulemused_df.empty:
        print("Tulemusi ei leitud!")
        return
    
    # Väljastame kuude kaupa
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("AKUPARGI KAUPLEMISE SIMULATSIOONI TULEMUSED")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append(f"Aku mahtuvus: {AKU_MAHTUVUS_MWH} MWh (maksimaalne laadimismahtuvus)")
    output_lines.append(f"Aku võimsus: {AKU_VOIMSUS_MW} MW")
    output_lines.append(f"Efektiivsus: {EFEKTIIVSUS * 100}%")
    output_lines.append(f"Laadimise maht: {AKU_MAHTUVUS_MWH} MWh")
    output_lines.append(f"Tagastatav energia: {TAGASTATAV_ENERGIA:.2f} MWh ({AKU_MAHTUVUS_MWH} MWh × {EFEKTIIVSUS * 100}%)")
    output_lines.append(f"Maksimaalne aeg laadimise ja tühjendamise vahel: {MAX_AEG_VAHEL} tundi")
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append("TULEMUSED KUUDE KAUPA")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # Sorteerime kuud
    sorted_kuud = sorted(kuu_tulud.keys())
    
    for kuu in sorted_kuud:
        kuu_tulu = kuu_tulud[kuu]
        kuu_andmed = tulemused_df[tulemused_df['Kuu'] == str(kuu)]
        tsuklite_arv = len(kuu_andmed)
        
        output_lines.append(f"Kuu: {kuu}")
        output_lines.append(f"  Tsüklite arv: {tsuklite_arv}")
        output_lines.append(f"  Kogutulu: {kuu_tulu:.2f} EUR")
        output_lines.append(f"  Keskmine tulu tsükli kohta: {kuu_tulu/tsuklite_arv:.2f} EUR" if tsuklite_arv > 0 else "  Keskmine tulu tsükli kohta: 0.00 EUR")
        output_lines.append("")
    
    output_lines.append("=" * 80)
    output_lines.append("KOKKUVÕTE")
    output_lines.append("=" * 80)
    output_lines.append(f"Kokku tsükleid: {len(tulemused_df)}")
    output_lines.append(f"Kogutulu: {tulemused_df['Tulu'].sum():.2f} EUR")
    output_lines.append(f"Keskmine tulu tsükli kohta: {tulemused_df['Tulu'].mean():.2f} EUR")
    output_lines.append("")
    
    # Detailne nimekiri päevade kaupa (valikuliselt)
    output_lines.append("=" * 80)
    output_lines.append("DETAILNE NIMEKIRI (ESIMESED 50 PÄEVA)")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append(f"{'Kuupäev':<12} {'Laadimise aeg':<20} {'Tühjendamise aeg':<20} {'Ostuhind':<12} {'Müügihind':<12} {'Tulu':<12} {'Aeg vahel':<12}")
    output_lines.append("-" * 80)
    
    for idx, row in tulemused_df.head(50).iterrows():
        kuupaev_str = row['Kuupäev'].strftime('%d.%m.%Y') if hasattr(row['Kuupäev'], 'strftime') else str(row['Kuupäev'])
        output_lines.append(
            f"{kuupaev_str:<12} "
            f"{row['Laadimise_aeg'].strftime('%d.%m.%Y %H:%M'):<20} "
            f"{row['Tühjendamise_aeg'].strftime('%d.%m.%Y %H:%M'):<20} "
            f"{row['Laadimise_hind']:>10.2f} EUR "
            f"{row['Tühjendamise_hind']:>10.2f} EUR "
            f"{row['Tulu']:>10.2f} EUR "
            f"{row['Aeg_vahel']:>10.1f} h"
        )
    
    # Salvestame faili
    output_tekst = "\n".join(output_lines)
    output_fail = os.path.join('c:\\Cursor\\NPS', 'akupargi_tulemused.txt')
    
    with open(output_fail, 'w', encoding='utf-8') as f:
        f.write(output_tekst)
    
    print(f"\nTulemused salvestatud faili: {output_fail}")
    print(f"Kokku tsükleid: {len(tulemused_df)}")
    print(f"Kogutulu: {tulemused_df['Tulu'].sum():.2f} EUR")
    
    # Salvestame ka CSV faili detailsete andmetega
    csv_output = os.path.join('c:\\Cursor\\NPS', 'akupargi_tulemused.csv')
    tulemused_df.to_csv(csv_output, index=False, encoding='utf-8-sig')
    print(f"Detailne CSV salvestatud faili: {csv_output}")

if __name__ == "__main__":
    simuleeri_akupark()

