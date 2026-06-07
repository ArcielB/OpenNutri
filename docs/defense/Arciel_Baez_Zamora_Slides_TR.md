# OpenNutri — Arciel Aliognis Baez Zamora — Savunma Sunumu (slayt taslağı, Türkçe)

> **Bu belge nedir.** Arciel Baez Zamora'nın bireysel savunma sunumu (backend) için slayt slayt bir taslak. Tam metin olan `Arciel_Baez_Zamora_Presentation_TR.md`'den türetildi; buradaki metin daha hafif — ana fikirler artı sözlü olarak söylemeye değer ayrıntılar. İngilizce slayt destesi ayrı bir dosyada: `Arciel_Baez_Zamora_Slides_EN.md`.
>
> **Nasıl okunur.** Maddeler ≈ slaytta yazacak olan şey (gerçek slaytta kısa tut; ayrıntıyı sözlü anlat). `🖼️ GÖRSEL` = oraya hangi şemayı ya da ekran görüntüsünü koyacağını ve neyi işaret edeceğini söyleyen bir not. Bir backend destesi çoğunlukla **şemalardan** ve senin kurduğun gerçek kokpit ekranlarından oluşur (Pipeline hunisi, Faydalı Makaleler + YZ detayı). Burada gizli bir not satırı yok — rakamlar ve teknik terimler bilerek slayt metnine yazıldı: hem normal slayt metni gibi okunuyorlar hem de bir hoca takip sorusu sorduğunda aklında olmasını isteyeceğin şeyler.
>
> **Ekip bölümü (bir kez söyle, 2. slayt):** Arciel — backend'in tamamı (bu sunum); Ayşegül — etiketleyici frontend'inin tamamı; Huan — yeniden kullanılabilir parçalar (`fuzzyMatch`, öneriler, parola sıfırlama düzeltmesi, tema merkezileştirmesi, sonsuz kaydırma).

---

## Slayt 0 — Başlık

> 🖼️ **GÖRSEL — kapak şeması:** tüm hat soldan sağa tek bir akış olarak — **Tarayıcı → YZ kademesi → Normalleştirici + güven kapısı → Veritabanı → (düşük güven) İnsan kuyruğu / (yüksek güven) otomatik kesinleştirme.** İnsan kutusu hariç her şey "benim" tonunda. Başlık üstte.
> *Altyazı:* "Tüm literatürü güvenilir adaylardan oluşan temiz bir kuyruğa çeviren — ve kendi kendine çalışan — backend."

- **OpenNutri — Backend**
- Arciel Aliognis Baez Zamora
- *"Makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanı bir insana bırakan sistemi kurdum — ücretsiz altyapıda, beş dakikada bir, kendi kendine."*

---

## Slayt 1 — Problem: besin verisi hâlâ elle üretiliyor

> 🖼️ **GÖRSEL — ikiye bölünmüş çizim:** solda sayılarla dolu yoğun bir PDF tablosu; sağda neredeyse boş bir veritabanı. Aralarında bir ok: "elle, tek tek yazılıyor." Altında: "🐌 yavaş · 💸 pahalı · 📉 dar ve güncelliğini yitirmiş."
> *Altyazı:* "Veri var. Elle çıkarmak ölçeklenmiyor; denetimsiz bir YZ ile çıkarmak ise güvenilir değil."

- Her besin etiketi, diyet uygulaması ve beslenme kılavuzu **besin bileşim verisine** dayanır — protein, yağ, demir, C vitamini…
- Bugün bu veri **elle** üretiliyor: makaleyi oku, tabloyu bul, her sayıyı tek tek veritabanına yaz.
- Yavaş ve pahalı → veritabanları **dar** kalır ve **güncelliğini yitirir**.
- Veri zaten var — sürekli yayımlanıyor — ama yapısı belirsiz PDF'lerin içine gömülü.
- Bir YZ'ye denetimsiz de okutamazsın: bir etikette güvenilemeyecek kadar **çok hatalı sayı** çıkar.

---

## Slayt 2 — Bunu (ekip olarak) nasıl çözdük

> 🖼️ **GÖRSEL — mimari şema:** **[Backend hattı] → [Veritabanı] → [Etiketleyici frontend]**; YZ kutusundan "düşük güven → insan" ve "yüksek güven → otomatik tutulur" dalları çıkıyor. Backend + veritabanının **benim**, frontend'in Ayşegül'ün olduğunu vurgula.
> *Altyazı:* "Yapay zekâ sayıları önerir. İnsan yalnızca emin olunmayanları doğrular."

- İşi tersine çevirdik: **yapay zekâ makaleyi okuyup sayıları önerir; insan yalnızca yapay zekânın emin olmadıklarını doğrular** (düşük güvenli olanları).
- Üç parça:
  - **Backend hattı** (ben) — makaleleri bulur, PDF'leri indirir, YZ kademesini çalıştırır → *aday* değerler; ve "güvenilir mi, belirsiz mi" kararını verir.
  - **Veritabanı** (ben) — her şeyi saklar, inceleme iş akışını yürütür.
  - **Etiketleyici web uygulaması** (Ayşegül) — bir insanın belirsiz adayları kontrol ettiği yer.
- **Benim parçam backend'in tamamı — insandan önce ve çevresinde olan her şey. Bu sunumun geri kalanı onunla ilgili.**

---

## Slayt 3 — Benim parçam ve neden gerekli

*(Görsel yok — bu "neden gerekli" argümanı; arka arkaya üçüncü bir hat şeması yerine sade bir metin olarak daha iyi oturuyor. İstenirse alt satır: "Frontend, ancak kendisine ulaşan veri kadar iyi olabilir. Backend, ona ulaşan veriyi hazırlayan şeydir.")*

- Benim parçam **backend'in tamamı** — veritabanı, YZ hattı, makale tarayıcısı, öğrenme döngüsü ve bunların hepsini gözetimsiz, ücretsiz altyapıda, beş dakikada bir çalıştıran otomasyon.
- **Neden gerekli:** birinin doğru makaleleri *bulması*, PDF'leri zorlu yayıncı sitelerinden *indirmesi*, onları ucuza *okuması*, "güvenilir mi, belirsiz mi" *karar vermesi*, bir güvenlik modeli altında *saklaması* ve sunucu/bütçe olmadan *sistemi ayakta tutması* gerekiyor.
- Projenin asıl riskini taşıyan da bu: yanlış bir otomatik kabul bir gıda veritabanını bozar; hatalı bir politika veri sızdırır; takılı bir işçi her şeyi durdurur. **"Doğru, ucuz ve gözetimsiz" üçünün de aynı anda sağlanması gerekiyor.**

---

## Slayt 4 — Yaptıklarım: yedi parça

*(Görsel yok — bu ajanda slaytı; numaralı listenin kendisi zaten görsel. İstenirse alt satır: "Hepsi Supabase ve GitHub'ın ücretsiz katmanlarında, kendi kendine çalışan bir araştırma hattı.")*

1. **Veritabanı ve güvenlik sözleşmesi** — 31 tablo, 75 RLS politikası, herkesin çağırdığı RPC'ler.
2. **Makale tarayıcısı (crawler)** — sistemin ön kapısı: arama → filtre → indirme.
3. **Üç aşamalı YZ kademesi** — Gemma → Flash-Lite → Flash, tek bir ortak sözleşme.
4. **Deterministik normalleştirici ve güven kapısı** — tahmin → güvenilir veri ya da bir insanın işi.
5. **Geri besleme ile öğrenme döngüsü** — insan onayları sonraki taramayı yeniden puanlar.
6. **Günlük operasyon otomasyonu** — beş dakikalık cron'da bir controller + 5 paralel işçi.
7. **Referans verisi, optimizasyon, testler ve doküman** — bunu demo değil, sistem yapan şey.

---

## Slayt 5 — 1) Veritabanı ve güvenlik sözleşmesi

> 🖼️ **GÖRSEL — katmanlı şema:** beş katman — **Referans (gıdalar/besinler) · Keşif (makaleler/arama defteri) · Etiketleme · İş akışı motoru · YZ yönlendirme** — yanında bir rozet: **31 tablo · 75 RLS politikası · 26 RPC · 22 SECURITY DEFINER.** Bir köşeye `current_user_can_write() = NOT current_user_is_tester()` satırını koy.
> *Altyazı:* "`migration.sql` — 5.396 satır: Python hattı ile React uygulaması arasındaki sözleşme."

- **Tek dosya, projenin omurgası** — o olmadan hiçbir şey etiket gönderemez, makale kaydedemez, görev alamaz ya da doğru veriyi gösteremez.
- **Tek, idempotent bir migrasyon** — canlı veritabanına her zaman güvenle tekrar uygulanabilir (`ADD COLUMN IF NOT EXISTS`, önce `information_schema`'yı kontrol eden `DO` bloklarında yeniden kurulan kısıtlar).
- **En az yetki ilkesine dayalı güvenlik: 75 RLS politikası**, 6 `SECURITY DEFINER` yüklemi üzerine — salt okunur eğitim erişimi *tek bir olumsuzlamadan* geliyor: `NOT is_tester()`.
- **Ekibi yanlışlıkla kilitleyemezsin:** admin RPC'si geriye hiç yazma yetkili kokpit inceleyicisi kalmayacaksa işlemi reddeder; kayıt izin listesi, tarayıcının ne okuyabildiği ne de aşabildiği bir auth hook'uyla uygulanır.

---

## Slayt 6 — 1) Sözleşme: atomik görev alma + aynı hash'i üreten doğru

> 🖼️ **GÖRSEL — iki panel:** (solda) `claim_paper_stage_tasks` SQL'i, **`FOR UPDATE SKIP LOCKED`** vurgulu; beş işçi okunun her biri bağımsız bir görev kümesi alıyor. (sağda) **İnsan gönderisi** ve **YZ çıkarımı** ikisi de "kanonik JSON → SHA-256" akışından geçip **aynı hash'i** üretiyor.
> *Altyazı:* "Tek bir ifade 5 paralel işçiyi güvenli kılıyor. Tek bir disiplin YZ çıktısını insanınkiyle karşılaştırılabilir yapıyor."

- **`claim_paper_stage_tasks`**, kuyruktaki görevleri `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED` ile alır — bu tek ifade, **5 paralel GitHub işçisinin** hiç koordinasyona gerek kalmadan, aynı görevi iki kez işlemeden bağımsız görevler almasını sağlar.
- **Deterministik payload üreticileri:** bir SQL üreticisi, insan gönderisini Python normalleştiricisiyle *aynı* sıralama + `round(value,6)` kurallarıyla oluşturur; böylece aynı veriye ait bir insan gönderisi ile bir YZ çıkarımı **aynı hash'i üretir**.
- **`build_label_payload_diff`** — SQL içinde tam bir yapısal fark (eklenen/eksik satırlar için anti-join) → etiketleyici performans metriklerinin ham malzemesi.

---

## Slayt 7 — 2) Makale tarayıcısı (ön kapı)

> 🖼️ **GÖRSEL — huni şeması:** **Arama (Europe PMC / OpenAlex / Semantic Scholar / DergiPark) → Filtre (eklemeli, kesin veto yok, başlık+özet üzerinde) → İndirme (indir → katı tam metin kapısı).** "Önce ucuz üst veri, sonra pahalı PDF" diye işaretle. Filtre aşamasına kırmızı bir "kesin olumsuz veto yok" damgası koy.
> *Altyazı:* "Ürünün alan tanımını puanlamaya göm — ama gerçek bir makaleyi tek bir alakasız kelime için eleme."

- Tarayıcı yanlış makaleleri alırsa **model kotası ve etiketleyici zamanı boşa gider**; fazla katı olursa gerçek tabloları hiç bulamaz.
- **Arama → Filtre → İndirme** — önce ucuz üst veride filtrele; PDF'i (yavaş, hataya açık) yalnızca geçenler için indir.
- **Tamamen eklemeli puanlama, kesin veto yok:** olumsuz bir ifade ("klinik çalışma") puanı *düşürür*, doğrudan elemez — tek bir kelime, içinde bir bileşim tablosu da olan bir makaleyi öldüremez.
- **Girişte gevşek, çıkışta katı:** üst veri kapısı recall'i en üst düzeye çıkarır; tam metin kapısı katıdır — yöntem kanıtı (AOAC/HPLC/GC/ICP), `mg/100g` birimleri, bir tablo sinyali, bir gıda sinyali ve temel besin paneliyle en az 4 örtüşme ister.
- Kelime eşleştirmesi Unicode kelime sınırlarına duyarlı — Türkçedeki "et", "diet" içinde değil, gerçek bir kelime olarak eşleşir.

---

## Slayt 8 — 2) PDF indirme: yayıncı bot duvarlarını aşmak

> 🖼️ **GÖRSEL — yedek zinciri:** aşağı doğru inen numaralı adımlar — **1. PMC OA paketi (.tar.gz içinden en büyük .pdf'i çıkar) → 2. doğrudan indirme (`%PDF` doğrula) → 3. tarayıcı User-Agent'lı curl → 4. PMC proof-of-work çöz → 5. HTML içindeki .pdf bağlantısını ayıkla.** 4. adımı küçük bir "madencilik döngüsü" simgesiyle vurgula.
> *Altyazı:* "Bir bot duvarı, gerçek bir MD5 proof-of-work çözücüyle aşıldı."

- Yayıncı PDF'leri kolay vermiyor — bu yüzden indirme, **katmanlı bir yedek zinciri** (5 adım); her biri öncekinin alamadığını yakalıyor.
- **Zor olan adım:** yayıncı bir HTML bot duvarı döndürdüğünde, `_solve_pmc_pow` meydan okumayı ayrıştırıp bir **hashcash nonce'unu kaba kuvvetle çözer** — `md5(meydan+nonce)` belirli sayıda sıfırla başlayana kadar artırır — sonra çözüm çereziyle yeniden dener.
- **Aynı makaleyi asla iki kez taramaz:** canlıdaki tüm `canonical_key` değerleri + yerel kalıcı durumlardan (üst veride elenenler dâhil) oluşan bir atlama listesi.
- **Süre sınırlı (2.400 sn):** süre dolunca temiz biçimde durur, ama kabul edilen her makaleyi + bir huni raporunu yine de yazar — bir GitHub zaman aşımı asla iş kaybettirmez.

---

## Slayt 9 — 3) Üç aşamalı YZ kademesi

> 🖼️ **GÖRSEL — huni:** küçülen üç çubuk — **Küçük / Gemma ~1.500/gün → Orta / Flash-Lite ~500/gün → Güçlü / Gemini Flash ~20/gün → human_review_ready.** Her birini model adı + giriş moduyla etiketle. Aşamalar arasına "öncelik puanı en iyi N'yi seçer" oku koy.
> *Altyazı:* "Günde ~20 pahalı çıkarımı, elenmiş ~1.500 makalenin en iyisine harca — ilk gelene değil."

- Son Gemini çıkarımı **kıt (ücretsiz kotada ~20/gün)** — her şeyi onunla elemek bütçeyi işe yaramaz makalelere harcamak olurdu.
- Bu yüzden **üç aşamalı huni:** ucuz eleyici (Gemma ~1.500/gün) → orta yeniden sıralayıcı (Flash-Lite ~500/gün) → pahalı çıkarıcı (Gemini ~20/gün).
- **Onu huni yapan bir öncelik puanı:** her aşama, en eskiyi değil, yararlılığa göre **en iyi N**'yi işler — böylece o 20 çağrı en iyi adaylara gider.
- Hattın biçimi **kodda değil, veride** — eşikler, yedek modeller ve giriş modu bir `routing_stage_configs` tablosunda; bir model kod değişmeden değiştirilebilir.

---

## Slayt 10 — 3) Üç model, tek sözleşme — gerçeklikten sağ çıkmak

> 🖼️ **GÖRSEL — kod/JSON çizimi:** tek bir **ortak prompt** üç model simgesini besliyor; altında, dört farklı biçimli JSON (nesne · düz dizi · tek elemanlı dizi · iç içe food→nutrients) hepsi **tek bir kanonik köke** iniyor. Köşe notu: "Gemma + PDF modu → ⏱️ 5 sayfada 600 sn'yi aştı → metin modu."
> *Altyazı:* "Geçerli ama farklı biçimli çıktı kurtarılır, bir döngüye girip tekrar denenmez."

- Üç aşama da **aynı promptu** çalıştırır (`opennutri_evidence_payload_v2`) — *ürünü tanımlayan* ~25 satır: "yararlı bileşim verisi" nedir, neyin boş sayıldığı (müdahaleler, tek seferlik formülasyonlar, derlemeler).
- Her satır **kanıt meta verisi** taşır (`table_label`, `page_hint`, en fazla 20 kelimelik birebir bir `source_quote`) ki frontend vurgulayabilsin — ve `page_hint`, **PDF sayfa numarasıdır, asla basılı sayfa değil** (vurgulamayı çalıştıran talimat).
- **Bozuk JSON'dan sağ çıkma:** markdown çitlerini temizle, elle yazılmış bir dengeli parantez tarayıcısı, **4 farklı biçim** → tek bir kök; hatalı bir satır atılır, hata sayılmaz.
- **Güçlü aşama için doğrudan PDF** (gerçek sayfa numaraları); **Gemma metin modunda kalır**, çünkü **5 sayfalık bir PDF'te 600 sn'yi aşarak** zaman aşımına uğradığı ölçüldü — günde ~1.500'de ölümcül. Karar, geri alınmasın diye kodda ve dokümanda sabitlendi.

---

## Slayt 11 — 4) Deterministik normalleştirici

> 🖼️ **GÖRSEL — eleme şeması:** bir model satırı soldan sağa kapılardan geçiyor — **zorunlu alan → birim politikası (7 birim; kuru madde reddedilir) → referans çözümleme (ID→ad→takma ad; belirsiz→hiçbiri) → deterministik sıra + round(6) → SHA-256.** Sonra gerçek bir **AI Extraction Detail** paneli ekran görüntüsü (Güven, Kabul/giriş satır sayısı, ret nedeni rozetleri).
> *Altyazı:* "Model çıktısı, bir insanın göndereceği yapıya çevriliyor — ve her satırın neden atıldığının kaydı tutuluyor."

- Bir modelin ham çıktısı veritabanı verisi değildir — bir insanın göndereceği **yapıyla birebir aynı** hâle gelmeli.
- **Katı birim bekçisi:** yalnızca `g/100g · mg/100g · μg/100g · kcal/100g · kJ/100g · IU/100g · %` geçer; 100 g üzerinden zorunlu, **kuru madde reddedilir**, taze/yaş/olduğu gibi kabul.
- **Güvenli referans çözümleme:** verilen bir veritabanı ID'sini doğrula, *üstelik* adının da eşleştiğini kontrol et; **belirsiz adlar hiçbir şeye çözülür** (asla yanlış bağ yok); çözülemeyen gıda/besinler açıkça *özel* satır olarak tutulur.
- **Deterministik sıra + `round(6)` → SHA-256** — böylece bir YZ çıkarımı bir insan gönderisiyle bayt bayt karşılaştırılabilir ve bir `rejection_reasons` histogramı satırların *neden* atıldığını gösterir.

---

## Slayt 12 — 4) Güven kapısı — tut, yoksa bir insana gönder?

> 🖼️ **GÖRSEL — kapı şeması:** üzerinde iki eşik olan bir güven ekseni; oklar — **düşük güven → İnsan kuyruğu · yüksek + olumlu → otomatik kesinleştirilir · otomatik kesinleştirilenlerin örneklenmiş bir kısmı → İnsana geri zorlanır (AUDIT).** Gerçek ekran görüntüsü: `conf 0.xx` + **LIVE / AUDIT** rozeti gösteren bir **Faydalı Makaleler** satırı.
> *Altyazı:* "Bu, 'YZ önerir, insan emin olunmayanları doğrular' fikrinin kesin, tekrarlanabilir ve kendini kontrol eden hâli."

- **Güven nasıl karar verir:** her makale, aşamanın kendi eşiklerine göre yüksek/düşük × olumlu/olumsuz olarak gruplanır.
- **Kapı:** **düşük güven → insan etiketleme kuyruğu**; **yüksek güven + olumlu → otomatik kesinleştirilir**; zaten insan doğrusu olan bir makalenin üzerine asla yazılmaz.
- **Otomatik kabuller körü körüne güvenilmez, denetlenir:** `stable_audit_sample` (`SHA256(paper|stage|model)` vs `audit_rate·2⁶⁴`) **deterministiktir** ve yüksek güvenli kesinleştirmelerin bile örneklenmiş bir kısmını bir insana geri zorlar — otomatik yol üzerinde sürekli kalite kontrolü.
- **Tamamen tekrarlanabilir + denetlenebilir:** aynı makale → her zaman aynı karar, ve nedenini her zaman görebilirsin. *(Sistemin ölçeklenen kısmı bu — insan yalnızca belirsiz makaleleri görür.)*

---

## Slayt 13 — 5) Geri besleme ile öğrenme döngüsü

> 🖼️ **GÖRSEL — döngü şeması:** **insan onayları (paper_review_outcomes) → log-odds n-gram puanlaması (iyi / kötü / arka plan) → latest.json → tarayıcı sonraki sefer daha iyi sıralar → daha çok iyi makale → daha çok onay.** YZ sonuçları düğümüne "kendi üzerinde eğitilmez" damgası (döngüden çıkarılmış, üstü çizili).
> *Altyazı:* "Sabit bir anahtar kelime tarayıcısı ile gelişen bir araştırma hattı arasındaki fark."

- Her insan onayı/reddi, hangi kelimelerin *yararlı* bir makaleyi işaret ettiğine dair bir kanıt — ve **sonraki taramayı** yeniden puanlar.
- **Asla kendi üzerinde eğitilmez:** yalnızca `truth_source_kind = 'human_review'` sonuçları sayılır; YZ'nin kesinleştirdikleri dışlanır; açık çakışmalar ve bekleyen gönderiler öğretmez.
- **İyi / kötü / arka plan üzerinde yumuşatılmış log-odds** — asıl numara **arka plan grubu**: sıradan kelimeleri değil, yararlı makalelere *özgü* terimleri öne çıkarır. Başlık ile başlık+özet ayrı puanlanır (bir başlık ifadesi daha güçlü kanıttır).
- **Her dil için yedi öğrenilmiş havuz** üretir (filtre ağırlıkları, sorgu ifadeleri, gömme çapaları, kaynak/çift/batch/kavram puanları) — ve geri besleme bir **yumuşak puandır**, asla doğrudan ret değil.

---

## Slayt 14 — 6) Günlük operasyon otomasyonu — kendi kendine çalışır, ücretsiz

> 🖼️ **GÖRSEL — operasyon şeması:** beş dakikalık bir saat, **tek bir `refill-controller`**'ı (tara/yükle/doldur) + **5 paralel `drain-workers` matrisini** çalıştırıyor; beşi de veritabanına tek bir **`FOR UPDATE SKIP LOCKED`** kutusundan bağlanıyor. (Gerçek Pipeline kokpit ekran görüntüsü sonraki slaytta — bunu sade bir şema olarak tut.)
> *Altyazı:* "GitHub runner'larında ve ücretsiz bir Gemini kotasında çalışan, sürekli ve gerçek bir hat — sunucu yok."

- Tüm hattın sürekli *çalışması* gerekiyor — tara, günde ~1.500 ele, triyaj yap, çıkar — hem de **sunucu ve bütçe olmadan**.
- **Tek bir controller** (tarama yapabilen tek iş; sürmekte olan bir tarama asla yarıda kesilmez) **+ beş paralel işçi** (controller'a bağlı değil — "controller başarısız olsa bile işleme devam etmeli").
- Beş işçi paralel çalışırken güvenli, çünkü `FOR UPDATE SKIP LOCKED` — her biri birbirinden bağımsız bir görev kümesi alır, kilit yok, koordinasyon yok.
- **Sürdürülebilir bir tik, daemon değil:** eski görevleri kuyruğa geri alma, en az denenmişi öne alma ve beş dakikalık pencere içinde açık bir "dur/devam et" karar ağacı — öldürülen ve çakışan runner'lara rağmen ayakta kalır.

---

## Slayt 15 — 6) Ücretsiz katmanın sınırları için mühendislik

> 🖼️ **GÖRSEL — gerçek kokpit ekran görüntüsü:** senin kurduğun **Pipeline** ekranı — **"Paper Funnel"** çubukları (arama → filtre → yükleme → küçük / orta / güçlü → insan, korunan/düşen sayılarıyla) ve canlı **"Right Now"** ızgarası. Asıl operasyonel ürün bu; aşağıdaki dört kısıt da onun üstünde anlatılacak konuşma noktaları.
> *Altyazı:* "Buradaki her mimari seçim tek bir kısıtın sonucu: bunu ücretsiz yap."

- **İki saat dilimine göre kota günü muhasebesi** — Gemma bir UTC gününü; iki Gemini aşaması, Google'ın sıfırlamasına uyması için bir `America/Los_Angeles` gününü sayar; böylece huni tam olarak günlük bütçeyi harcar.
- **İç içe üç süre sınırı** (controller 75 dk · tarayıcı kısmi sonuçları yazarak 2.400 sn · her model çağrısı `SIGALRM` ile 300 sn) — tek bir yavaş makale iş süresini aşamaz.
- **PDF'ler kaynak URL'sinden, talep üzerine** sunulur (onları saklamak Supabase ücretsiz sınırlarını aşardı); CORS'a takılan yayıncı PDF'lerini bir **aynı kaynaklı PDF proxy'si** (`api/pdf.js`) çeker: **SSRF koruması, `%PDF-` sihirli bayt kontrolü, 25 MB sınırı ve 1 yıllık değiştirilemez önbellek** — her makale kaynaktan en fazla bir kez çekilir.

---

## Slayt 16 — 7) Referans verisi, testler ve dokümantasyon

> 🖼️ **GÖRSEL — gerçek bir test dosyası kesiti:** `test_ai_routing.py`'deki gerçek `pytest` fonksiyon adlarının ekran görüntüsü; neredeyse değişmezlerin bir tanımı gibi okunuyor — örn. `rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `audit_sampling_is_deterministic`, `build_labels_excludes_ai_model_outcomes`. (Burada tek somut bir panel, üç simgeli bir kolajdan daha iyi.)
> *Altyazı:* "Bir demo ile altı ay işletilmiş bir sistem arasındaki farkı yaratan gösterişsiz katman."

- **Referans ETL'i:** idempotent yükleyiciler USDA FoodData Central'ı kanonik gıda/besinlere aktarır — çakışmada upsert + **deterministik UUID'ler**, her referans ID'sini, yabancı anahtarların işaret etmesi için sabit tutar.
- **Tehlikeli koda ağırlık veren testler:** ~5.600 satır; yalnızca `test_ai_routing.py` **2.469 satır / 60 test** — normalleştirme determinizmi, birim politikası, denetim örneklemesinin determinizmi, "model asla kendi üzerinde eğitilmez".
- **Operasyonel altyapı olarak doküman:** README / AGENTS / STATE; *neden* Gemma metin modunda, *neden* tarayıcıda veto yok, *neden* PDF'ler kaynak URL'sinden sunuluyor — böylece kritik kararlar geri alınmıyor.

---

## Slayt 17 — Kapanış: hepsi neye varıyor

> 🖼️ **GÖRSEL — "rakamlarla" kartı + Slayt 0'daki kapak hat şeması:** büyük rakamlar — **~31.800 backend satırı · 216 commit · 5.396 satırlık şema · ~5.600 test satırı · 1.500 → 20/gün kademe · 6 aydır canlı.**
> *Altyazı:* "Üretimde işletildi, taşındı ve kurtarıldı — hem de ücretsiz altyapıda."

- **216 commit** boyunca **~31.800 satır** backend/operasyon/şema; yalnızca veritabanı sözleşmesi **5.396 satır** (31 tablo, 75 RLS politikası) ve tehlikeli mantık **~5.600 satır testle** sabitlenmiş.
- Günde ~1.500 makaleyi eleyip en iyi ~20'sini çıkaran bir **üç modelli kademe**; çıktısı bir insanınkiyle **aynı hash'i üreten** bir **deterministik normalleştirici**; ve güveniliri otomatik tutan, belirsizi insana yönlendiren, geri kalanın da örneklenmiş bir kısmını denetleyen bir **güven kapısı**.
- Bot duvarlarını bir proof-of-work çözücüyle aşan bir **tarayıcı**, kendi üzerinde eğitilmeden öğrenen bir **geri besleme döngüsü** ve hepsini beş dakikalık bir cron'da Supabase + Gemini'nin ücretsiz katmanlarında çalıştıran bir **otomasyon**.
- **Prototip değil — altı aydır canlı, işletildi/taşındı/kurtarıldı**; hatalı bir politikanın veri sızdıracağı ve yanlış bir otomatik kabulün bir veritabanını bozacağı bir ortamda, bu yüzden her biri olmayacak şekilde tasarlandı. **Benim backend'im, makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanı bir insana bırakan makine — her gün çalışacak kadar ucuz, bir besin etiketinde güvenilecek kadar dürüst.**
