# tefas-fon-api

TEFAS'taki ~2.500 yatırım, emeklilik ve borsa yatırım fonunun günlük fiyatlarını
**statik JSON dosyalarına** dönüştürür. Sunucu, veritabanı veya ücret gerekmez:
GitHub Actions veriyi her gün çeker, GitHub Pages dosyaları API gibi sunar.

[ParaLens](https://github.com/ofzorbaci/ParaLens) uygulamasının veri katmanından ayrıldı.

## Ne üretir?

```
funds/
  latest.json            tüm fonların son fiyatı, büyüklüğü, yatırımcı sayısı, getirileri
  history/<KOD>.json     bir fonun 5 yıllık günlük fiyat geçmişi
  daily/<YYYY-MM>.json   o ayın her işlem gününde tüm fonların fiyatı
  meta.json              güncelleme zamanı, fon sayısı, fon başına son fiyat tarihi
```

`latest.json` içindeki bir fon:

```json
{
  "code": "AAL",
  "name": "ATA PORTFÖY PARA PİYASASI (TL) FONU",
  "kind": "YAT",
  "price": 3.750239,
  "date": "2026-11-17",
  "aum": 1167109298,
  "investors": 4068,
  "returns": { "m1": 0.0213, "m3": 0.0651, "m6": 0.1342, "ytd": 0.3011, "y1": 0.3554 }
}
```

`returns` değerleri orandır (0.0213 = %2,13; yukarıdakiler örnektir); yeterli geçmiş yoksa `null`.
`kind`: `YAT` yatırım fonu, `EMK` emeklilik fonu, `BYF` borsa yatırım fonu.
Her dosyada `schema` alanı vardır; şema değişirse bu sayı artar.

## Kendi API'nizi 3 adımda kurun

1. Bu depoyu **fork**'layın.
2. Actions sekmesinde **Fon verisi** iş akışını **Run workflow** ile çalıştırın.
   İlk çekim 5 yıllık veri indirir (TEFAS dakikada 6 istek sınırı koyduğu için ~40 dk sürer).
3. **Settings > Pages**'te kaynak olarak `gh-pages` dalını seçin.

Dosyalar şu adreste yayınlanır:
`https://<kullanıcı-adınız>.github.io/tefas-fon-api/funds/latest.json`

Günlük otomatik güncelleme için `.github/workflows/sync.yml` içindeki `schedule`
satırlarını açın.

## Yerelde çalıştırma

```bash
pip install git+https://github.com/ofzorbaci/tefas-fon-api
tefas-fon-api --out ./site                # ilk seferde 5 yıl, sonra yalnızca yeni günler
tefas-fon-api --out ./site --mode topup   # son günü de yeniden çeker (geç gelen fiyatlar)
```

Python içinden:

```python
from datetime import date
from pathlib import Path
from tefas_fon_api import sync

sync(Path("site"), "main", date.today())
```

## Güvenilirlik

- Yeni dosyalar önce geçici klasöre yazılır, doğrulanır, sonra tek hamlede yerine konur.
  Çekim yarıda kalırsa eski veri olduğu gibi kalır.
- İlk yüklemede 500'den az fon gelirse yanıt bozuk sayılır ve hiçbir şey yazılmaz.
- Biten bir indirme geçici klasörde saklanır; son adımda hata olursa uzun çekim tekrarlanmaz.

## Veri ve lisans

Bu deponun **kodu** MIT lisanslıdır. **Fon verisi** ise TEFAS'a (Takasbank) aittir ve bu
lisansın kapsamında değildir. Verinin, özellikle ticari amaçla yeniden yayınlanması
TEFAS kullanım koşullarına tabidir. Kendi kopyanızda veriyi herkese açık yayınlamadan
önce bu koşulları kontrol etmek sizin sorumluluğunuzdadır. Bu proje TEFAS veya
Takasbank ile bağlantılı değildir. Veriler yatırım tavsiyesi değildir.

TEFAS'a erişim [pytefas](https://pypi.org/project/pytefas/) (MIT) üzerinden yapılır.
