# fukaha.github.io

**Fukahâ**: klasik fıkıh eserleri, fakihler, tezler, kitaplar ve makaleler için Türkçe, Arapça ve İngilizce bir kaynak rehberi. Site <https://fukaha.github.io> adresinde yayımlanır.

Site [Jekyll](https://jekyllrb.com/) ile yazıldı ve GitHub Pages tarafından otomatik olarak derlenir. Ayrı bir derleme adımı yoktur.

## Yapı

| Yer | İçerik |
| --- | --- |
| `index.html`, `klasik-eserler/`, `tezler/` … | Türkçe sayfalar |
| `en/`, `ar/` | İngilizce ve Arapça sayfalar |
| `_posts/<dil>/haber/`, `_posts/<dil>/blog/` | Haberler ve blog yazıları (Markdown) |
| `data/*.json` | Tablo verileri |
| `_data/jurists.json`, `_fakihler/` | Fakih sayfaları: sayfa başına veri ve her dil için birer boş sayfa dosyası (ikisi de içe aktarma betiğiyle yazılır) |
| `_data/stats.yml` | Ana sayfadaki sayılar, grafikler ve “Günün fakihi” listesi (içe aktarma betiğiyle yazılır) |
| `_data/tables.yml` | Her tablonun sütunları, filtreleri ve ilk sıralaması |
| `_data/i18n.yml` | Arayüz metinleri (üç dil) |
| `_data/nav.yml` | Menü, sayfa adresleri ve bölüm görselleri |
| `_data/images.yml` | Görseller, altyazıları ve lisansları |
| `assets/` | CSS, JavaScript, görseller |
| `tools/` | Veri ve görsel aktarma betikleri |

## Yazı eklemek

`_posts/tr/blog/2026-10-01-yazi-adi.md` biçiminde bir dosya oluşturun:

```markdown
---
ref: yazi-adi        # aynı yazının diğer dillerdeki sürümleriyle ortak anahtar
title: Başlık
summary: Bir cümlelik özet
image: mabsut        # _data/images.yml içindeki bir görsel
---

Metin…
```

Haberler için `haber` klasörünü, diğer diller için `en` ve `ar` klasörlerini kullanın.

## Kitap ve makale eklemek

`data/kitaplar.json` ve `data/makaleler.json` dosyaları kayıt listesidir. Alan adları `_data/tables.yml` dosyasındaki sütunlarla aynıdır. Örnek:

```json
[{"title": "…", "author": "…", "publisher": "…", "city": "İstanbul", "year": 2020, "lang": "tr", "pages": 320, "isbn": "…"}]
```

## Verileri yenilemek

```sh
python3 tools/import_fuqaha.py ../fuqaha   # fakihler, fakih sayfaları, klasik eserler, tezler
python3 tools/fetch_images.py              # görseller (Wikimedia Commons)
```

## Yerelde çalıştırmak

```sh
gem install jekyll -v 3.10.0 kramdown-parser-gfm jekyll-sitemap webrick
jekyll serve
```

## Kaynaklar ve lisanslar

- Biyografiler ve klasik eserler: Leknevî, *el-Fevâidü’l-behiyye fî terâcimi’l-Hanefiyye* (Mısır 1324).
- Tezler: YÖK Ulusal Tez Merkezi.
- Görseller: Wikimedia Commons. Her görselin sahibi ve lisansı `_data/images.yml` dosyasında ve sitenin Hakkında sayfasında yer alır.
