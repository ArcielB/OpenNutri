# OpenNutri — Arciel Aliognis Baez Zamora — Savunma Sunumu (slayt-hazır, Türkçe)

> **Bu belge nedir.** Arciel Baez Zamora'nın bireysel savunma sunumu (backend) için slayt-slayt bir metin. Tam metin `Arciel_Baez_Zamora_Presentation_TR.md`'den türetilmiştir; buradaki metin daha hafiftir — ana fikirler artı yüksek sesle söylemeye değer ayrıntılar. İngilizce slayt destesi ayrı bir dosyadadır: `Arciel_Baez_Zamora_Slides_EN.md`.
>
> **Nasıl okunur.** Maddeler ≈ slaytta ne yer alacağı (gerçek slaytta kısa tutun; sözlü genişletin). `🖼️ GÖRSEL` = oraya hangi şemayı veya ekran görüntüsünü koyacağınızı ve neyi göstereceğinizi söyleyen bir yer tutucu. Bir backend destesi çoğunlukla **şemalar** artı kurduğunuz gerçek kokpit ekranlarıdır (Pipeline hunisi, Faydalı Makaleler + YZ detayı). Burada gizli bir not izi yoktur — rakamlar ve teknik adlar bilerek slayt içeriğine yazılmıştır: normal slayt metni gibi okunur ve bir hoca takip sorusu sorduğunda kafanızda olmasını isteyeceğiniz şeylerdir.
>
> **Ekip bölümü (bir kez söyle, Slayt 2):** Arciel — backend'in tamamı (bu sunum); Ayşegül — etiketleyici frontend'inin tamamı; Huan — yeniden kullanılabilir parçalar (`fuzzyMatch`, öneriler, parola-sıfırlama düzeltmesi, tema merkezileştirmesi, sonsuz kaydırma).

---

## Slayt 0 — Başlık

> 🖼️ **GÖRSEL — kahraman şema:** tüm hat tek bir soldan-sağa akış olarak — **Tarayıcı → YZ kademesi → Normalleştirici + güven kapısı → Veritabanı → (düşük güven) İnsan kuyruğu / (yüksek güven) otomatik-kesinleştirilmiş.** İnsan kutusu hariç her şey "benim" tonunda. Başlık üstte.
> *Altyazı:* "Tüm literatürü güvenilir adaylardan oluşan temiz bir kuyruğa çeviren — ve kendi kendini çalıştıran — backend."

- **OpenNutri — Backend**
- Arciel Aliognis Baez Zamora
- *"Makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanını bir insana saklayan sistemi kurdum — ücretsiz altyapıda, her beş dakikada bir kendi kendine çalışarak."*

---

## Slayt 1 — Problem: besin verisi hâlâ elle kuruluyor

> 🖼️ **GÖRSEL — bölünmüş illüstrasyon:** solda yoğun bir PDF tablosu; sağda seyrek bir veritabanı. Arada ok: "elle, tek tek yazılıyor." Altında: "🐌 yavaş · 💸 pahalı · 📉 dar & eski."
> *Altyazı:* "Veri var. Onu elle çıkarmak ölçeklenmiyor; denetimsiz bir YZ ile okumak güvenilir değil."

- Her besin etiketi, diyet uygulaması ve beslenme kılavuzu **besin bileşim verisine** dayanır — protein, yağ, demir, C vitamini…
- Bugün **elle** kurulur: makaleyi oku, tabloyu bul, her sayıyı tek tek veritabanına yaz.
- Yavaş ve pahalı → veritabanları **dar** kalır ve **eskir**.
- Veri zaten var — sürekli yayımlanıyor — ama yapısız PDF'lerin içinde kilitli.
- Bir YZ'ye denetimsiz okutamazsınız: bir etikette güvenilemeyecek kadar **çok yanlış sayı**.

---

## Slayt 2 — Bunu (ekip olarak) nasıl çözdük

> 🖼️ **GÖRSEL — mimari şema:** **[Backend hattı] → [Veritabanı] → [Etiketleyici frontend]**, YZ kutusu "düşük güven → insan" ve "yüksek güven → otomatik tutulur" dallarıyla. Backend + veritabanının **benim**, frontend'in Ayşegül'ün olduğunu vurgula.
> *Altyazı:* "Yapay zekâ sayıları önerir. İnsan, emin olmadıklarını doğrular."

- İşi tersine çevirdik: **yapay zekâ makaleyi okuyup sayıları önerir; insan, yapay zekânın emin olmadıklarını doğrular** (düşük güvenli olanları).
- Üç parça:
  - **Backend hattı** (ben) — makaleleri bulur, PDF'leri çeker, YZ kademesini çalıştırır → *aday* değerler ve güvenilir-mi-belirsiz-mi kararını verir.
  - **Veritabanı** (ben) — her şeyi saklar, inceleme iş akışını yürütür.
  - **Etiketleyici web uygulaması** (Ayşegül) — bir insanın belirsiz adayları kontrol ettiği yer.
- **Benim parçam backend'in tamamı — insandan önce ve etrafında olan her şey. Bu sunumun geri kalanı bununla ilgili.**

---

## Slayt 3 — Benim parçam ve neden gerekli

> 🖼️ **GÖRSEL:** Slayt 0'daki hattın aynısı, ama **insan kutusu sonda küçük** ve onu besleyen her şey "benim" etiketli. Backend üstüne dört küçük risk simgesi: 🔓 sızan bir RLS politikası · 🛑 takılan bir işçi · 💸 boşa giden model kotası · ❌ yanlış bir otomatik-kabul.
> *Altyazı:* "Frontend ancak kendisine ulaşan şey kadar iyi olabilir. Backend, ona ulaşan şeydir."

- Benim parçam **backend'in tamamı** — veritabanı, YZ hattı, tarayıcı, öğrenme döngüsü ve bunların hepsini gözetimsiz, ücretsiz altyapıda, her 5 dakikada bir çalıştıran otomasyon.
- **Neden gerekli:** birinin doğru makaleleri *bulması*, PDF'leri düşman yayıncı sitelerinden *çekmesi*, ucuza *okuması*, güvenilir-mi-belirsiz-mi *karar vermesi*, bir güvenlik modeli altında *saklaması* ve sunucu/bütçe olmadan *makineyi çalışır tutması* gerekir.
- Projenin asıl riskini taşır: yanlış bir otomatik-kabul bir gıda veritabanını bozar; bozuk bir politika veri sızdırır; takılan bir işçi her şeyi durdurur. **"Doğru, ucuz ve gözetimsiz"in hepsi aynı anda doğru olmalı.**

---

## Slayt 4 — Yaptıklarım: yedi parça

> 🖼️ **GÖRSEL — "harita" slaytı:** hat akışı boyunca dizilmiş yedi numaralı kutu (ön kapı → … → kendi kendine çalışır). Ajanda görevi de görür.
> *Altyazı:* "Supabase ve GitHub ücretsiz katmanlarında, kendi kendini çalıştıran bir araştırma hattı."

1. **Veritabanı & güvenlik sözleşmesi** — 31 tablo, 75 RLS politikası, herkesin çağırdığı RPC'ler.
2. **Makale-keşif tarayıcısı** — ön kapı: arama → filtre → edinim.
3. **Üç-aşamalı YZ kademesi** — Gemma → Flash-Lite → Flash, tek paylaşılan sözleşme.
4. **Deterministik normalleştirici & güven kapısı** — tahmin → güvenilir veri, ya da bir insanın işi.
5. **Geri besleme-öğrenme döngüsü** — insan onayları sonraki taramayı yeniden puanlar.
6. **Günlük-operasyon otomasyonu** — 5 dk'lık cron'da bir denetleyici + 5 paralel işçi.
7. **Referans veri, sağlamlaştırma, testler & doküman** — bunu demo değil sistem yapan şey.

---

## Slayt 5 — 1) Veritabanı & güvenlik sözleşmesi

> 🖼️ **GÖRSEL — katmanlı şema:** beş katman — **Referans (gıdalar/besinler) · Keşif (makaleler/arama defteri) · Etiketleme · İş akışı motoru · YZ yönlendirme** — yan rozetle: **31 tablo · 75 RLS politikası · 26 RPC · 22 SECURITY DEFINER.** `current_user_can_write() = NOT current_user_is_tester()` tek-satırını ekle.
> *Altyazı:* "`migration.sql` — 5.396 satır: Python hattı ile React uygulaması arasındaki sözleşme."

- **Tek dosya, projenin omurgası** — o olmadan hiçbir şey etiket gönderemez, makale kaydedemez, görev alamaz veya gerçeği gösteremez.
- **Tek, yakınsayan, idempotent migrasyon** — canlı DB'de sonsuza dek yeniden çalıştırmaya güvenli (`ADD COLUMN IF NOT EXISTS`, önce `information_schema`'yı kontrol eden `DO` bloklarında yeniden kurulan kısıtlar).
- **En-az-ayrıcalıklı güvenlik: 75 RLS politikası** 6 `SECURITY DEFINER` yüklem üzerine — salt-okunur eğitim erişimi *tek bir olumsuzlamadan* düşer, `NOT is_tester()`.
- **Ekibi kilitleyemezsiniz:** admin RPC'si sıfır etkin kokpit-yazma inceleyicisi bırakmayı reddeder; kayıt allowlist'i, tarayıcının ne okuyabildiği ne aşabildiği bir auth hook'uyla uygulanır.

---

## Slayt 6 — 1) Sözleşme: atomik alım + hash-aynı gerçek

> 🖼️ **GÖRSEL — iki panel:** (sol) `claim_paper_stage_tasks` SQL'i **`FOR UPDATE SKIP LOCKED`** vurgulu, beş işçi oku her biri ayrık bir görev kümesi alıyor; (sağ) **İnsan gönderisi** ve **YZ çıkarımı** ikisi de "kanonik JSON → SHA-256"e akıyor ve **aynı hash**'i üretiyor.
> *Altyazı:* "Tek tümce 5 paralel işçiyi güvenli yapar. Tek disiplin YZ çıktısını insanınkiyle kıyaslanabilir yapar."

- **`claim_paper_stage_tasks`** kuyruktaki görevleri `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED` ile alır — o tek tümce, **5 paralel GitHub işçisinin** sıfır koordinasyon, sıfır çift-işleme ile ayrık görevler almasını sağlar.
- **Deterministik yük inşacıları:** bir SQL inşacısı bir insan gönderisini Python normalleştiricisiyle *aynı* sıralama + `round(value,6)` kurallarıyla kurar; böylece bir insan gönderisi ile aynı verinin YZ çıkarımı **birebir aynı hash'lenir**.
- **`build_label_payload_diff`** — SQL'de tam yapısal fark (eklenen/eksik satırlar için anti-join) → etiketleyici-performans metriklerinin ham maddesi.

---

## Slayt 7 — 2) Makale-keşif tarayıcısı (ön kapı)

> 🖼️ **GÖRSEL — huni şeması:** **Arama (Europe PMC / OpenAlex / Semantic Scholar / DergiPark) → Filtre (toplamsal, sert veto yok, başlık+özet üzerinde) → Edinim (indir → katı tam-metin kapısı).** "Önce ucuz metadata, sonra pahalı PDF" işaretle. Filtre aşamasına kırmızı "sert-negatif veto yok" damgası koy.
> *Altyazı:* "Ürünün alan tanımını puanlamaya kodla — gerçek bir makaleyi tek bir başıboş kelime için öldürmeden."

- Tarayıcı yanlış makaleleri kabul ederse **model kotası ve etiketleyici zamanı boşa gider**; çok katıysa gerçek tabloları hiç bulamaz.
- **Arama → Filtre → Edinim** — önce ucuz metadata'da filtrele; PDF'i (yavaş, hataya açık) yalnızca geçenler için indir.
- **Tamamen toplamsal puanlama, asla sert veto:** bir negatif ifade ("klinik çalışma") bir *cezadır*, otomatik-ret değil — tek bir kelime, bir bileşim tablosu da olan bir makaleyi öldüremez.
- **İçeri gevşek, dışarı katı:** metadata kapısı geri-çağırımı en üst düzeye çıkarır; tam-metin kapısı katıdır — yöntem kanıtı (AOAC/HPLC/GC/ICP), `mg/100g` birimleri, tablo sinyali, gıda sinyali ve proksimat panelle ≥4 örtüşme gerektirir.
- Kelime eşleşmesi Unicode kelime-sınırı duyarlı — Türkçe "et", "diet" içinde değil, bir kelime olarak eşleşir.

---

## Slayt 8 — 2) PDF edinimi: yayıncı bot-duvarlarını yenmek

> 🖼️ **GÖRSEL — yedek merdiveni:** aşağı doğru numaralı adımlar — **1. PMC OA paketi (.tar.gz'den en büyük .pdf'i çıkar) → 2. doğrudan çekim (`%PDF` doğrula) → 3. tarayıcı User-Agent'lı curl → 4. PMC proof-of-work çöz → 5. HTML .pdf linkini kazı.** 4. adımı küçük bir "madencilik döngüsü" simgesiyle vurgula.
> *Altyazı:* "Bir bot-duvarı, gerçek bir MD5 proof-of-work çözücüyle yenildi."

- Yayıncı PDF'leri direnir — bu yüzden edinim, **katmanlı bir yedek merdivenidir** (5 adım), her biri öncekinin alamadığını yakalar.
- **Zor olan:** bir yayıncı HTML bot-duvarı döndürdüğünde, `_solve_pmc_pow` meydan okumayı ayrıştırır ve **bir hashcash nonce'unu brute-force eder** — `md5(meydan+nonce)` N sıfırla başlayana dek artırır — sonra çözüm çereziyle tekrar dener.
- **Aynı makaleyi asla iki kez taramaz:** her canlı `canonical_key` + yerel terminal durumlardan (metadata retleri dâhil) bir atlama-kümesi.
- **Duvar-saati sınırlı (2.400 sn):** zaman aşımında temiz durur ve yine de her kabul edilen makaleyi + bir huni manifestini yazar — bir GitHub zaman aşımı asla iş kaybetmez.

---

## Slayt 9 — 3) Üç-aşamalı YZ kademesi

> 🖼️ **GÖRSEL — huni:** üç küçülen çubuk — **Küçük / Gemma ~1.500/gün → Orta / Flash-Lite ~500/gün → Güçlü / Gemini Flash ~20/gün → human_review_ready.** Her birini model adı + giriş moduyla etiketle. Aşamalar arasına "öncelik puanı en iyi-N'yi seçer" oku.
> *Altyazı:* "Günde ~20 pahalı çıkarımı, elenmiş ~1.500'ün en iyisine harca — ilk gelene değil."

- Nihai Gemini çıkarımı **kıttır (ücretsiz kotada ~20/gün)** — her şeyi onunla elemek bütçeyi işe yaramaz makalelere harcardı.
- Bu yüzden **üç-aşamalı huni:** ucuz eleyici (Gemma ~1.500/gün) → orta yeniden-sıralayıcı (Flash-Lite ~500/gün) → pahalı çıkarıcı (Gemini ~20/gün).
- **Bir öncelik puanı onu huni yapar:** her aşama, en eski değil, yararlılığa göre **en iyi-N**'yi işler — böylece 20 çağrı en iyi adaylara düşer.
- Hattın şekli **kod değil, veridir** — eşikler, yedek modeller ve giriş modu bir `routing_stage_configs` tablosunda; bir model kod değişmeden değiştirilebilir.

---

## Slayt 10 — 3) Üç model boyunca tek sözleşme — gerçeklikten sağ çıkmak

> 🖼️ **GÖRSEL — kod/JSON illüstrasyonu:** üç model simgesini besleyen tek bir **paylaşılan prompt**; altında, dört farklı-şekilli JSON bloğu (nesne · çıplak dizi · 1-elemanlı dizi · iç içe food→nutrients) hepsi **tek kanonik köke** iniyor. Ek: "Gemma + PDF modu → ⏱️ 5 sayfada 600 sn'yi aştı → metin modu."
> *Altyazı:* "Geçerli-ama-farklı-şekilli çıktı kurtarılır, bir döngüye yeniden-denenmez."

- Üç aşama da **aynı promptu** çalıştırır (`opennutri_evidence_payload_v2`) — *ürünü tanımlayan* ~25 satır: "yararlı bileşim verisi" nedir vs. neyin boş olduğu (müdahaleler, tek-seferlik formülasyonlar, derlemeler).
- Her satır **kanıt metadata'sı** taşır (`table_label`, `page_hint`, ≤20-kelime birebir `source_quote`) ki frontend vurgulayabilsin — ve `page_hint`, **PDF sayfa indeksidir, asla basılı sayfa değil** (vurgulamayı çalıştıran talimat).
- **JSON sapmasından sağ çıkıldı:** markdown çitlerini soy, elle yazılmış dengeli-parantez tarayıcısı, **4 kabul edilen şekil** → tek kök; kötü bir satır düşürülür, ölümcül değil.
- **Güçlü aşama için yerel PDF** (gerçek sayfa numaraları); **Gemma metin-modu kalır** çünkü **5 sayfalık bir PDF'te 600 sn'yi aşarak** zaman aşımına uğradığı ölçüldü — ~1.500/gün'de ölümcül. Karar, geri alınmaması için kodlandı + belgelendi.

---

## Slayt 11 — 4) Deterministik normalleştirici

> 🖼️ **GÖRSEL — eleme şeması:** bir model satırı soldan-sağa kapılardan geçiyor — **zorunlu-alan → birim politikası (7 birim; kuru-madde reddedilir) → referans çözümleme (ID→ad→takma; belirsiz→hiçbiri) → deterministik sıra + round(6) → SHA-256.** Sonra gerçek bir **AI Extraction Detail** paneli ekran görüntüsü (Güven, Kabul/giriş satır, red-nedeni rozetleri).
> *Altyazı:* "Model çıktısı, bir insanın göndereceği tam şekle dönüştürülmüş — ve her satırın neden düşürüldüğünün kaydı."

- Bir modelin ham çıktısı veritabanı verisi değildir — bir insanın gönderdiği **tam aynı normalize şekle** dönüşmeli.
- **Katı birim bekçisi:** yalnızca `g/100g · mg/100g · μg/100g · kcal/100g · kJ/100g · IU/100g · %` sağ kalır; per-100g zorunlu, **kuru-madde reddedilir**, taze/yaş/olduğu-gibi kabul.
- **Güvenli referans çözümleme:** iddia edilen bir DB id'sini *ve* adının eşleştiğini doğrula; **belirsiz adlar hiçbir şeye çözülür** (asla yanlış bağ); çözülmemiş gıdalar/besinler açık *özel* satırlar olarak tutulur.
- **Deterministik sıra + `round(6)` → SHA-256** — böylece bir YZ çıkarımı bir insan gönderisiyle bayt-bayt kıyaslanabilir ve bir `rejection_reasons` histogramı satırların *neden* düştüğünü gösterir.

---

## Slayt 12 — 4) Güven kapısı — tut, ya da bir insana gönder?

> 🖼️ **GÖRSEL — kapı şeması:** bir eksen üzerinde iki eşikli güven; oklar — **düşük-güven → İnsan kuyruğu · yüksek-pozitif → otomatik-kesinleştirilmiş · otomatik-kesinleştirilmişin örneklenen bir dilimi → İnsana geri zorlanır (AUDIT).** Gerçek ekran görüntüsü: `conf 0.xx` + **LIVE / AUDIT** rozeti gösteren bir **Faydalı Makaleler** satırı.
> *Altyazı:* "Bu, 'YZ önerir, insan emin olmadıklarını doğrular'ın kesin, yeniden-üretilebilir ve kendini-kontrol eden hâli."

- **Güven nasıl karar verir:** her makale, aşamanın kendi eşiklerine karşı yüksek/düşük × pozitif/negatif kümelenir.
- **Kapı:** **düşük-güven → insan etiketleme kuyruğu**; **yüksek-güven-pozitif → otomatik-kesinleştirilir**; zaten insan gerçeği olan bir makalenin üzerine asla yazılmaz.
- **Otomatik-kabuller güvenilmez, denetlenir:** `stable_audit_sample` (`SHA256(paper|stage|model)` vs `audit_rate·2⁶⁴`) **deterministiktir** ve yüksek-güvenli kesinleştirmelerin bile örneklenen bir kesrini bir insana geri zorlar — otomatik yol üzerinde sürekli kalite kontrolü.
- **Tamamen yeniden-üretilebilir + denetlenebilir:** aynı makale → aynı karar, her seferinde, ve nedenini her zaman görebilirsiniz. *(Sistemin ölçeklenen kısmı budur — insan yalnızca belirsiz makaleleri görür.)*

---

## Slayt 13 — 5) Geri besleme-öğrenme döngüsü

> 🖼️ **GÖRSEL — döngü şeması:** **insan onayları (paper_review_outcomes) → log-odds n-gram puanlama (iyi / kötü / arka plan) → latest.json → tarayıcı sonraki sefer daha iyi sıralar → daha çok iyi makale → daha çok onay.** YZ-sonuçları düğümüne "kendi üzerinde eğitilmez" damgası (döngüden çıkarılarak üstü çizili).
> *Altyazı:* "Statik bir anahtar-kelime tarayıcısı ile gelişen bir araştırma hattı arasındaki fark."

- Her insan onayı/reddi, hangi kelimelerin *yararlı* bir makaleyi öngördüğüne dair kanıttır — ve **sonraki taramayı** yeniden puanlar.
- **Kendi üzerinde asla eğitilmez:** yalnızca `truth_source_kind = 'human_review'` sonuçları sayılır; YZ-kesinleştirilmiş olanlar dışlanır; açık çakışmalar ve bekleyen gönderiler öğretmez.
- **İyi / kötü / arka plan üzerinde yumuşatılmış log-odds** — **arka plan kovası** hiledir: yaygın kelimeleri değil, yararlı makalelere *özgü* terimleri öne çıkarır. Başlık vs. başlık+özet ayrı puanlanır (bir başlık ifadesi daha güçlü kanıttır).
- **Dile-özgü yedi öğrenilmiş havuz** üretir (filtre ağırlıkları, sorgu ifadeleri, gömme çapaları, kaynak/çift/batch/konsept puanları) — ve geri besleme bir **yumuşak puandır**, asla sert-ret değil.

---

## Slayt 14 — 6) Günlük-operasyon otomasyonu — kendi kendine çalışır, ücretsiz

> 🖼️ **GÖRSEL — ops şeması:** 5 dakikalık bir saat, **bir serileştirilmiş `refill-controller`**'ı (tara/yükle/doldur) + **5 paralel `drain-workers` matrisini** sürüyor; beşi de DB'ye tek bir **`FOR UPDATE SKIP LOCKED`** kutusundan işaret ediyor. Gerçek ek: bir GitHub Actions çalışma listesi, ya da **Pipeline → "Şu An"** kokpit ızgarası.
> *Altyazı:* "GitHub-barındırmalı runner'larda ve ücretsiz bir Gemini kotasında gerçek, sürekli bir hat — sunucu yok."

- Tüm hat sürekli *çalışmalı* — tara, günde ~1.500 ele, triyaj yap, çıkar — **sunucu ve bütçe olmadan**.
- **Bir serileştirilmiş denetleyici** (tarama yapabilen tek iş; tarama ortasında asla öldürülmez) **+ beş paralel boşaltma işçisi** (kapısız — "denetleyici başarısız olsa bile boşaltma devam etmeli").
- Beş işçi paralel güvenli **çünkü** `FOR UPDATE SKIP LOCKED` — her biri ayrık bir görev kümesi alır, kilit yok, koordinasyon yok.
- **Sürdürülebilir bir tık, daemon değil:** bayat-görev yeniden-kuyruğu, en-az-deneme-önce sıralama ve 5 dakikalık pencere içinde açık bir dur/dolum karar ağacı — öldürülen ve çakışan runner'lardan sağ çıkar.

---

## Slayt 15 — 6) Ücretsiz-katman tavanı için mühendislik

> 🖼️ **GÖRSEL — kısıtlar paneli:** dört etiketli çip — **2 saat dilimi boyunca kota-günü** (Gemma=UTC, Gemini=America/Los_Angeles) · **3 iç içe duvar-saati bütçesi** (denetleyici 75 dk / tarayıcı 2.400 sn / model 300 sn) · **kaynak-URL PDF'ler** (Supabase depolama yok) · **aynı-köken PDF proxy** (SSRF-sağlam). İsteğe bağlı **Pipeline hunisi** ekran görüntüsü.
> *Altyazı:* "Buradaki her mimari seçim tek bir kısıttan kaynaklanır: bunu ücretsiz yap."

- **İki saat dilimi boyunca kota-günü muhasebesi** — Gemma bir UTC gününü; her iki Gemini aşaması Google'ın sıfırlamasıyla eşleşmek için bir `America/Los_Angeles` gününü sayar; böylece huni tam olarak günlük bütçeyi harcar.
- **Üç iç içe duvar-saati bütçesi** (denetleyici 75 dk · kısmi-sonuç yazımlı tarayıcı 2.400 sn · `SIGALRM` ile her model çağrısı 300 sn) — bir yavaş makale iş sınırını aşamaz.
- **PDF'ler kaynak-URL/talep-üzerine** (onları saklamak Supabase ücretsiz sınırlarını aşardı); bir **aynı-köken PDF proxy'si** (`api/pdf.js`) CORS-dostu-olmayan yayıncı PDF'lerini **SSRF sağlamlaştırması, bir `%PDF-` sihirli-bayt kontrolü, 25 MB sınırı ve 1-yıllık değişmez önbellekle** çeker — her makale yukarı akıştan en fazla bir kez çekilir.

---

## Slayt 16 — 7) Referans veri, testler & dokümantasyon

> 🖼️ **GÖRSEL — üç panel:** (1) **USDA CSV → idempotent upsert → kanonik gıdalar/besinler**; (2) bir spesifikasyon gibi okunan gerçek test adları listesi (`rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `build_labels_excludes_ai_model_outcomes`); (3) bir doküman yığını (README · AGENTS · STATE · iş-akışı haritası).
> *Altyazı:* "Bir demo ile altı ay işletilmiş bir sistem arasındaki farkı yapan gösterişsiz katman."

- **Referans ETL:** idempotent yükleyiciler USDA FoodData Central'ı kanonik gıdalar/besinlere akıtır — çakışmada upsert + **deterministik UUID'ler** her referans ID'sini, foreign key'lerin işaret etmesi için kararlı tutar.
- **Tehlikeli koda ağırlık veren testler:** ~5.600 satır; tek başına `test_ai_routing.py` **2.469 satır / 60 test** — normalleştirme determinizmi, birim politikası, denetim-örnekleme determinizmi, "model asla kendi üzerinde eğitilmez".
- **Operasyonel altyapı olarak doküman:** README / AGENTS / STATE, *neden* Gemma metin-modu, *neden* tarayıcı vetosu yok, *neden* kaynak-URL PDF'ler olduğunu yakalar — böylece yük taşıyan kararlar geri alınmaz.

---

## Slayt 17 — Bitiş: hepsi neye varıyor

> 🖼️ **GÖRSEL — "rakamlarla" kartı + Slayt 0'daki kahraman hat şeması:** büyük rakamlar — **~31.800 backend satırı · 216 commit · 5.396-satır şema · ~5.600 test satırı · 1.500 → 20/gün kademe · 6 aydır canlı.**
> *Altyazı:* "Üretimde işletildi, migrate edildi ve kurtarıldı — ücretsiz altyapıda."

- **216 commit** boyunca **~31.800 satır** backend/ops/şema; tek başına veritabanı sözleşmesi **5.396 satırdır** (31 tablo, 75 RLS politikası) ve tehlikeli mantık **~5.600 satır testle** sabitlenmiştir.
- Günde ~1.500 eleyip en iyi ~20'yi çıkaran bir **üç-modelli kademe**; çıktısı bir insanınkiyle **birebir aynı hash'lenen** bir **deterministik normalleştirici**; ve güveniliri otomatik tutan, belirsizi insana yönlendiren ve geri kalanın örneklenen bir dilimini denetleyen bir **güven kapısı**.
- Bot-duvarlarını bir proof-of-work çözücüyle yenen bir **tarayıcı**, kendi üzerinde eğitilmeden öğrenen bir **geri besleme döngüsü** ve hepsini 5 dakikalık bir cron'da Supabase + Gemini ücretsiz katmanları içinde çalıştıran bir **otomasyon**.
- **Prototip değil — altı ay boyunca canlı, işletildi/migrate edildi/kurtarıldı**, bozuk bir politikanın veri sızdıracağı ve yanlış bir otomatik-kabulün bir veritabanını bozacağı bir yerde, bu yüzden her biri olmayacak şekilde tasarlandı. **Benim backend'im, makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanını bir insana saklayan makine — her gün çalışacak kadar ucuz, bir besin etiketinde güvenilecek kadar dürüst.**
