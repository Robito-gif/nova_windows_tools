# Nova Windows Tools ⚡

**Nova Windows Tools** is a professional, terminal-based Windows utility platform and ecosystem management engine written in Python.

Copyright (C) 2026 Robin Güneş.

**Current version:** 2.4.0 (Yeni Nesil Mimari)

Nova Windows Tools brings together Windows power management, screen recording, live scene composition studio, FastMCP server management, local authenticated WebSocket relays, hierarchical ecosystem configuration, on-demand hardware discovery, and secure update workflows under a unified, strict 5-category command protocol.

> **Platform:** Windows 10/11 (Power, display, and recording controls); Windows, macOS, and Linux (MCP center, settings, discovery, and relays)  
> **Language:** Python >= 3.10  
> **Interface:** Terminal / CLI, with interactive settings REPL and graphical tools  
> **License:** GNU General Public License v3 only (GPL-3.0-only)

---

## ⚡ 5-Kategorili Yeni Nesil Komut Sistemi

Nova Windows Tools, komut karmaşasını önlemek ve güvenliği artırmak için her komutu ön ek sembolüyle kesin olarak ayrılmış beş temel kategoride yürütür. Baştaki boşluklar ve ön ekler ham girdi düzeyinde korunur (`strip()` ile baştaki boşluklar silinmez).

### A. Normal Komutlar — Başında 1 Boşluk (` `)
Günlük ve temel işlemler için kullanılır. Başında tam olarak **bir adet boşluk** bulunmalıdır:

- ` help` — Kapsamlı ve kategorize edilmiş yardım menüsünü açar.
- ` version` — Nova Windows Tools sürüm, platform ve Python bilgilerini gösterir.
- ` status` — Bilgisayarın uyanıklık durumu, ekran koruması ve oturum istatistiklerini görüntüler.
- ` clear` — Terminal ekranını temizler ve karşılama panelini yeniden basar.
- ` apps` — Algılanan masaüstü uygulamalarını ve paket yöneticilerini listeler.
- ` exit` — Servisleri durdurur, güç ayarlarını normale döndürür ve güvenle çıkar.
- ` start [süre]` — Uyanık modunu başlatır (örn: ` start 30dk`, ` start 1h`).
- ` stop` — Uyanık modunu sonlandırır.
- ` display on / off` — Monitörün kararmasını engeller veya uykuya izin verir.
- ` pomodoro` — 25 dakikalık odaklanma oturumu başlatır.
- ` meeting` — 60 dakikalık toplantı modu başlatır.
- ` record [süre] [seçenekler]` — Yüksek performanslı MP4 ekran kaydı başlatır.
- ` studio` — Canlı sahne ve kaynak kompozisyon stüdyosunu açar.
- ` license` — GNU GPLv3 lisans ve garanti bildirimini gösterir.

> **Önemli Kural:** Kullanıcı başında boşluk bırakmadan örneğin `help` yazarsa sistem bunu sessizce çalıştırmaz; kullanıcıya normal komutlar için başında bir boşluk bırakılması gerektiğini belirten açıklayıcı bir ipucu (`Did you mean ' help'?`) gösterir.

### B. Önemli Sistem Komutları — Başında Slash (`/`)
Sistem genelinde daha kritik veya yönetimsel işlemleri gerçekleştiren, yetki ve onay denetimine tabi komutlardır:

- `/system` — Windows işletim sistemi, CPU, bellek, mimari ve UAC yetki durumunu gösterir.
- `/diagnostics` — Windows API'leri, AppData yazma izinleri, FFmpeg ve FastMCP tanılaması yapar.
- `/processes [filtre]` — Çalışan süreçleri listeler, ada göre filtreler ve izler.
- `/mcp [list|create|start|stop|settings]` — MCP sunucularını ve güvenlik izinlerini yönetir.
- `/ecosystem` — Nova ekosistemindeki tüm bileşenlerin (AI, Dev, Sistem, MCP) gerçek durumlarını gösterir.
- `/security` — Yönetici (Administrator) yetkilerini, UAC durumunu ve güvenlik denetim günlüğünü (Audit Log) gösterir.
- `/update` — Uygulama güncelleme merkezini açar.

### C. Nova Ekosistem Ayarlar Merkezi — Başında Büyüktür (`>`)
Bilgisayarda algılanan sistemlerin, yapay zekâ entegrasyonlarının, geliştirme araçlarının ve ağ bileşenlerinin **ayrıntılı, hiyerarşik ve etkileşimli** ayarlar merkezini açar:

- `>` — Ana Nova Ayarlar Merkezi REPL'ini açar.
- `> apps` — Algılanan uygulamaların başlatma parametreleri ve ayarları.
- `> ai` — Yapay zekâ modelleri, sıcaklık, yerel Ollama/FastMCP uç noktaları.
- `> mcp` — MCP varsayılan portları, taşıma protokolü (`stdio`/`streamable-http`) ve izinler.
- `> development` — Python sanal ortamları, Git zaman aşımı ve paket yöneticisi tercihleri.
- `> system` — Windows güç politikası, ekran koruma ve düşük donanım modu.
- `> updates` — Güncelleme kanalları (`stable`/`beta`/`nightly`) ve otomatik denetim.
- `> network` — Yerel WebSocket bind host, port ve bağlantı limitleri.
- `> security` — Kritik işlem onayları ve denetim günlüğü hassas veri maskelemesi.

#### Ayarlar REPL Komutları:
- `ls` / `list` — Mevcut menüdeki ayarları veya alt kategorileri listeler.
- `cd <kategori>` — Belirtilen kategoriye geçer (örn: `cd ai`). `cd ..` üst menüye döner.
- `get <anahtar>` — Ayarın açıklamasını, geçerli değer aralığını ve bağımlılıklarını gösterir.
- `set <anahtar> <değer>` — Ayar değerini değiştirir ve staged olarak işaretler.
- `save` — Tüm değişiklikleri atomik olarak diske kaydeder ve otomatik yedek alır.
- `revert` — Kaydedilmemiş değişiklikleri iptal eder.
- `reset [kategori]` — Ayarları varsayılan fabrika değerlerine döndürür.
- `search <ifade>` — Tüm ayarlar arasında arama yapar.
- `export <dosya.json>` / `import <dosya.json>` — Ayarları dışa veya içe aktarır.

### D. Ayarlardan Çıkış — Başında Küçüktür (`<`)
Açık olan Nova Ayarlar Merkezi'nde gezinmek veya çıkmak için kullanılır:

- Alt kategorideyken `<` yazıldığında bir üst kategoriye dönülür.
- Ana ayarlar ekranındayken `<` yazıldığında ayarlar merkezinden çıkılarak ana terminale dönülür.
- **Kaydedilmemiş Değişiklik Güvenliği:** Çıkış sırasında kaydedilmemiş değişiklikler varsa sistem kullanıcıyı uyarır ve 3 seçenek sunar:
  - `[E]` Kaydet ve çık
  - `[H]` Değişiklikleri iptal et ve çık
  - `[D]` Düzenlemeye devam et

### E. Tam Güncelleme Sistemi — Başında Kare (`#`)
Nova Windows Tools ve onaylı Nova ekosistem bileşenleri için kapsamlı, doğrulanmış ve güvenli güncelleme yönetimi:

- `#` — Güncelleme merkezini açar ve kullanılabilir komutları listeler.
- `# check` — Güncelleme kanallarındaki yeni sürümleri denetler ve semver karşılaştırması yapar.
- `# preview` — Yapılacak değişiklikleri, indirme boyutunu ve changelog'u önizler.
- `# download [bileşen]` — Güncellemeyi geçici hazırlık (`staging`) dizinine indirir ve **SHA256 hash doğrulaması** yapar.
- `# install [bileşen]` — Kullanıcıdan açık onay alarak, mevcut sistemin tam yedeğini alır ve güncellemeyi kurar.
- `# full` — `Check -> Preview -> Confirm -> Download & Verify -> Backup -> Install` iş akışını baştan sona güvenle yürütür.
- `# history` — Önceki güncelleme ve geri alma işlemlerinin kayıtlarını gösterir.
- `# rollback` — Herhangi bir aksilik durumunda sistemi tek komutla önceki çalışır yedeğine döndürür.

---

## 🔒 Güvenlik Modeli

1. **Kullanıcı Onayı:** Hiçbir kritik işlem veya güncelleme kurulumu kullanıcının açık onayı olmadan çalıştırılmaz.
2. **Bütünlük Kontrolü:** İndirilen güncelleme paketlerinin SHA256 karma değeri doğrulanmadan kuruluma izin verilmez.
3. **Otomatik Geri Alma (Rollback):** Kurulum aşamasında bir hata meydana gelirse sistem anında önceki çalışan sürüme geri döner.
4. **Denetim Günlüğü (Audit Log):** Hassas ve kritik tüm işlemler `%APPDATA%\NovaWindowsTools\audit.log` dosyasına maskelenmiş olarak kaydedilir.
5. **Yetki Kontrolü:** Yönetici yetkisi gerektiren işlemler tespit edilerek kullanıcı net şekilde uyarılır.

---

## 🚀 Kurulum ve Başlatma

### Gereksinimler
- Windows 10 veya Windows 11 (Tüm güç ve ekran özellikleri için)
- Python 3.10 veya daha yeni bir sürüm

### Hızlı Başlatma
Proje dizinindeki `baslat.bat` dosyasını çalıştırabilir veya terminalden doğrudan başlatabilirsiniz:

```powershell
python nova_windows_tools.py
```

Düşük donanımlı sistemler veya pil tasarrufu için:

```powershell
python nova_windows_tools.py --low-resource
```

Paket olarak kurmak için:

```powershell
pip install .
nova
```

*(Geriye dönük uyumluluk için `EWT` ve `NWT` komutları da korunmaktadır).*

---

## 🧪 Testler

Nova Windows Tools, 12 temel gereksinim alanı dahil olmak üzere kapsamlı bir unittest süitine sahiptir:

```powershell
python -m unittest discover tests
```

Tüm 31 test (WebSocket, MCP Center, Studio, Nova Command Architecture) %100 başarıyla çalışmaktadır.

---

## 📄 Lisans

Nova Windows Tools, **GNU General Public License v3 (GPL-3.0-only)** kapsamında lisanslanmıştır.  
Ayrıntılar için `LICENSE` dosyasına bakınız.
