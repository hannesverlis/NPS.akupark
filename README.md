# Akupargi Kauplemise Simulaator

Web-rakendus akupargi kauplemise simuleerimiseks Nord Pool Spot (NPS) elektrienergia tunnihindade põhjal.

## Funktsioonid

- Sisestage akupargi võimsus (MW) ja mahtuvus (MWh)
- Optimeerib laadimise ja tühjendamise hetked
- Näitab igakuist kasumit
- Näitab erinevust keskmisest kuu sissetulekust
- Näitab kuu keskmist NPS hinda

## Paigaldamine

1. Veenduge, et teil on installitud Python 3.x
2. Installige vajalikud paketid:
```bash
pip install flask pandas numpy
```

## Käivitamine

1. Avage terminal ja navigeerige projekti kausta
2. Käivitage rakendus:
```bash
python app.py
```

3. Avage brauseris: http://localhost:5000

## Kasutamine

### Kohalikult (Flask)

1. Käivitage rakendus:
```bash
python app.py
```

2. Avage brauseris: http://localhost:5000

### Vercel'is (Staatiline)

1. Sisestage akupargi parameetrid:
   - Aku Võimsus (MW) - vaikimisi 50 MW
   - Aku Mahtuvus (MWh) - vaikimisi 100 MWh
   - Efektiivsus (%) - vaikimisi 87%
   - Maksimaalne aeg laadimise ja tühjendamise vahel (tunnid) - vaikimisi 8h

2. Vajutage nuppu "Arvuta"

3. Vaadake tulemusi:
   - Kokkuvõte (kokku tsükleid, kogutulu, keskmine tulu)
   - Igakuine tabel koos:
     - Tsüklite arv
     - Kogutulu
     - Keskmine tulu tsükli kohta
     - Erinevus keskmisest (värvikoodiga)
     - Keskmine NPS hind kuus

## Vercel'i Paigaldamine

1. Liituge Vercel'iga: https://vercel.com
2. Importige GitHub repositoorium: https://github.com/hannesverlis/NPS.akupark
3. Vercel tuvastab automaatselt `vercel.json` faili
4. Deploy toimub automaatselt

Rakendus töötab täielikult kliendipoolselt - CSV failid laaditakse otse GitHubist.

## Failid

- `app.py` - Flask backend API
- `templates/index.html` - Frontend HTML/CSS/JavaScript
- `Tuulikutasu*.csv` - Elektrienergia tunnihindade andmed

## Märkused

- Rakendus loeb kõik CSV failid kaustast, mis algavad "Tuulikutasu"
- Arvutused põhinevad optimaalse laadimise ja tühjendamise hetke leidmisel
- Efektiivsus arvestatakse nii laadimisel kui tühjendamisel

