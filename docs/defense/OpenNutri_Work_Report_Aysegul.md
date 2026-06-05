# OpenNutri — Çalışma Raporu: Ayşegül Doğan (221229031)

*Ayşegül'e atfedilen annotator ön yüz (frontend) çalışmalarının kendi içinde bütün açıklaması. Ana rapora eşlik eden belgedir; sayılar 2026-06-05 tarihinde, `ac8bf72` HEAD'i üzerinden git geçmişinden yeniden türetilmiştir.*

## Bir bakışta

- **Alan:** annotator ön yüzünün tamamı — `apps/expert-annotator/src/**` (React 19 + Vite, Vercel üzerinde yayında).
- Bugün üretimde **~13.500 satır** ön yüz kodu çalışmaktadır; proje boyunca **+22.681 / −7.581** satırlık ön yüz değişimi (net **+15.100**).
- **Yalnızca PDF görüntüleyici + metin tarayıcı: 27 commit** — ön yüzün tek başına en zor alanı.
- **Atıf (katkı paylaştırma) kuralı:** Ayşegül, ilk MVP'yi ve çekirdek ön yüzü kendi `ayseguldogan2706-cpu` kimliği altında yazdı (7 commit, aşağıdaki temel). Uygulamayı `apps/expert-annotator/` altına taşıyan Mart ayındaki yeniden düzenlemeden sonra ön yüz gelişiminin büyük kısmı ekibin ortak entegrasyon makinesi üzerinden commit'lendi; ekibin yerleşik iş bölümüne göre **ön yüz alanındaki çalışma Ayşegül'e aittir** ve burada bu temelde kredilendirilmiştir. Huan'ın özelliklerine ait ~450 satırlık ön yüz (öneri ekleri, şifre sıfırlama sayfası, bulanık eşleştirme) hariç tutulmuştur ve Huan'ın raporunda ele alınmaktadır.

Ön yüz, OpenNutri'nin bir insanın gün boyu fiilen dokunduğu kısımdır ve en zor alt problemi — bir tarayıcının bir bilimsel makale PDF'i içindeki doğru hücreleri güvenilir biçimde vurgulamasını sağlamak — 4. ve 5. bölümlerde derinlemesine anlatılmaktadır.

---

## 1. Etiketleme aracı MVP'si — temel
**Commit `7c2d372` (2026-03-02, +5.010), Ayşegül'ün kendi kimliği altında yazıldı.**

- **Ne:** ilk çalışan uygulama — `App.jsx`, `Login.jsx`, `Annotate.jsx`, `FoodItemForm.jsx`, `PdfViewer.jsx`, `supabaseClient.js`, 695 satırlık bir `index.css` ve ilk şema. Ön yüzdeki her şey bundan büyüdü.
- **Neden:** hiç uygulama yoktu; bu, React + Supabase + Vite yığınını ve temel "bir makaleyi etiketle" döngüsünü kurdu.
- **Nasıl:** kimlik doğrulama (e-posta/şifre) ve veri için Supabase ile konuşan tek sayfalık bir React uygulaması; bir makale görünümünün yanında öğe başına yiyecek giriş formu ve temel bir PDF gösterimi.

## 2. Kimlik doğrulama ve tema
**Commit'ler `614a82c`, `6245a17` (2026-03-02).**

- Google OAuth ile oturum açma düğmesi (`Login.jsx`); açık/koyu **tema değiştirici** (`useTheme.js`); şifremi unuttum girişi; ilk `SuggestionModal.jsx` iskeleti (daha sonra Huan tarafından genişletildi).

## 3. Esnek besin modeli + otomatik tamamlama
**Commit `00fd645` (2026-03-03, +1.242/−80).**

- **Ne:** ürünü tanımlayan yeniden tasarım — yiyecek öğesi başına serbest besin satırları, ayrıca `FoodAutocomplete.jsx` (bugün 664 satır), `NutrientAutocomplete.jsx` (334) ve `NutrientPopover.jsx`.
- **Neden:** gerçek besin bileşim tabloları sabit bir besin kümesine sahip değildir; arayüz, etiketleyicinin herhangi bir besini değer/birim/bazla eklemesine izin vermelidir. Katı bir form bu veriyi temsil edemez.
- **Nasıl:** `FoodAutocomplete`, **yerel + uzak** yiyecek adaylarını ad normalizasyonuyla sıralar; besin popover'ı, tıklanan bir besin adına bir değerin iliştirilmesini sağlar.

## 4. PDF besin vurgulaması — kesinlik problemi
**Commit'ler `00fd645` (ilk hali), `6aba2f2`, `f383732`, `cce6945`, `c885403` ve `PdfTextScanner.js`'in sürekli büyümesi (145 → 2.323 satır).**

- **Ne:** **tespit edilen tablo bölgeleriyle sınırlı** tıkla-ekle besin vurgulaması. Görüntüleyici, PDF.js metin katmanından **sayfaya özel bir izin listesi (allowlist)** oluşturur ve yalnızca tablo gövdesi/başlık hücrelerini ve tablo başlık/altyazı satırlarını işaretler.
- **Neden:** görüntüleyicinin tüm amacı, etiketleyicinin makaledeki bir besine tıklayarak onu eklemesini sağlamaktır. Vurgulama her besin kelimesini — anlatı metnindeki kelimeler dahil — aydınlatırsa, tıklama hedefleri gürültüye dönüşür.
- **Bunu gerçekten zorlaştıran şey:** **bir PDF'in "tablo" kavramı yoktur.** PDF, konumlandırılmış metin parçacıklarından oluşan bir torbadır. "Yalnızca tabloyu" vurgulamak için tablo bölgesinin o parçacıkların geometrisinden *çıkarsanması* ve çevredeki paragraflarda geçen besin kelimelerinin dışlanması gerekir.
- **Nasıl çözüldü:**
  - Sayfa başına güvenilir bir tablo çapası (altyazı/başlık geometrisi) tespit et ve izin listesini ondan oluştur (`f383732`, `cce6945`).
  - Bir sayfada **güvenilir** çapa yoksa veya bir tablo altyazısız bir devam sayfasına akıyorsa, sayfa geneli metin eşleştirmesine geri düşmek yerine **o sayfada vurgulamayı bastır** (`6aba2f2`).
  - Makaleler/sayfalar arasında vurgu durumunu temiz biçimde sıfırla (`c885403`).
- **Ödünleşim (kapsam yerine kesinlik):** tek bir tablo hücresi içinde birden çok PDF metin parçacığına yayılan eşleşmeler bilinçli olarak bilinen bir takip işi olarak bırakılmıştır. Ürün kararı, bazılarını kaçırma pahasına bile olsa asla yanlış bir tıklama hedefi üretmemekti.

## 5. Yapay zekâ kanıt katmanları — koordinat tabanlı vurgulama
**17 commit: `63ac650`, `582c34e`, `a683c49`, `8fb77f5`, `ad1b38b`, `398cc46`, `b1ab87b`, `662a5f8`, `faf5341`, `82b09b0`, `c875853`, `5a23ac3`, `3564c57`, `8e89198`, `dc855e4`, `27c44ae`, `ac8bf72` (2026-05-13 → 06-05).**

- **Ne:** bir makalenin yapay zekâ çıkarımı olduğunda, görüntüleyici sıkışık bir **Kaynaklar şeridi** gösterir ve yapay zekânın atıfta bulunduğu tam tablo/paragraf bloklarının üzerine, oluşturulan sayfaya ölçeklenmiş **her zaman açık koordinat katmanları** boyar. Destekleyici yardımcılar: `EvidenceLocations.js` (439 satır), `evidenceStatusCache.js`, `evidenceDedupStorage.js`.
- **Neden:** yapay zekâ çıktısını doğrulayan bir gözden geçiren, her değerin makalenin *neresinden* geldiğini — avlanmadan, anında — görmek zorundadır.
- **Zor problemler ve akıllı çözümler:**
  - **Çok sütunlu dergiler sütunları birleştiriyordu.** **Sütun kırpma sınırlarıyla (column-clip bounds)** ve parçacıkları **dar sütun oluklarında bölerek**, ardından sütunlar arası bitişikliği reddederek düzeltildi (`82b09b0`, `c875853`).
  - **Belge çöpü eşleşmeleri kirletiyordu.** Kurum bağlantıları, makale-geçmişi kenar çubukları, anahtar kelime kutuları ve telif hakkı satırları, kanıt blokları oluşturulmadan önce filtrelenir (`8e89198`).
  - **Yapay zekânın `page_hint`'i güvenilmezdir.** Model yalnızca çıkarılmış metni görür, dolayısıyla bir dergi ön baskısında *basılı* sayfa numarasını bildirir (örneğin 5 sayfalık bir dosyada `1217`). `page_hint`, PDF'in sayfa sayısını aştığında, vurgulama bunu **belirleyici olmayan (non-gating)** olarak ele alır — altyazı numarası + birebir kaynak alıntısı, kanıtı herhangi bir sayfada metinden bulur (`27c44ae`). Üstbilgi/altbilgide tespit edilen basılı sayfa etiketleri gerçek PDF sayfalarına eşlenir.
  - **Katmanlar oluşturmalar arasında titriyordu.** Kararlı bölge kimlikleri ve bastırılmış iç işaretler onları sabit tutar (`82b09b0`); aynı tablo/paragraftaki yinelenen kaynaklar tek bir katmana ve tek bir çipe indirgenir (`5a23ac3`, `3564c57`).
  - **Gözden geçirenler yanlış sayfaya iniyordu.** En yeni değişiklik (`ac8bf72`, 2026-06-05) **kanıt sayfalarını önce** oluşturur ve ilkini otomatik açıp vurgular.
- **Tasarım duruşu:** bu katmanlar *geniş gezinme rehberidir*, piksel-tam besin eşleştirmesi değil; eşleşmeyen yapay zekâ kanıtı görünür kalır ama "doğrulanmadı" olarak işaretlenir, böylece gözden geçiren asla konumlanmamış bir değere güvenmeye yanıltılmaz.

## 6. Yapay zekâ ön-doldurma doğrulama arayüzü + iş akışı yüzeyleri
- **Yapay zekâ ön-doldurma:** kaydedilmiş taslağı olmayan bir kuyruk makalesi, en son Gemini `normalized_payload_json` değeri **düzenlenebilir yiyecek/besin satırları olarak önceden yüklenmiş** halde açılır; böylece etiketleyici boştan başlamak yerine yapay zekâ çıktısını doğrular/düzeltir. Mevcut taslaklar/gönderimler asla üzerine yazılmaz ve yapay zekânın *gerekçesi* gizlenir — yalnızca DB ile uyumlu satırlar gösterilir, ayrı bir "yapay zekâ ön-doldurma" başlığı olmadan (sessiz bir arayüz için bilinçli ürün kararı).
- **Destekleyici arayüz:** `AiDetailPanel.jsx` (yapay zekâ çıkarım ayrıntıları), `HelpRequestModal.jsx` (kafa karıştırıcı bir makaleden "Yardım İste"), `PayloadSummary.jsx`, `EvidenceStrip.jsx`, test modu değiştirici (yalnızca yerel yazma), anında geri-al onayıyla genel "veri yok" atlama.
- **Zor kısım:** ön-doldurma, insan emeğini asla ezmeden taslaklar ve gönderimlerle bir arada var olmalıdır — veri çekme, üst çubuk ve görünüm yönlendirmesinin sahibi olan 1.163 satırlık merkezi orkestratör `Annotate.jsx` içinde korunmuştur.

## 7. Kod tabanının görünümlere (views) ayrıştırılması
**Commit'ler `675feee`, `9de76ba`, `cf35755` (2026-05-16).**

- Saf yardımcılar `utils/annotateHelpers.js` (574 satır) içine çıkarıldı, küçük bileşenler ayıklandı ve `src/views/` altına **8 alt görünüm** bölündü: `QueueView` (227), `ApprovalView` (199), `DashboardView` (171), `AllPapersView` (140), `PipelineOpsView` (162), `SuggestionsReviewView`, `MySuggestionsView`, `ReviewerAdminView`. Bu, sürekli büyüyen tek bir `Annotate.jsx`'i bakımı yapılabilir bir orkestratör-artı-görünümler yapısına dönüştürdü — her yeni sekme eklendiğinde kendini amorti eden türden bir yeniden düzenleme.

## 8. Ön yüz performans ve maliyet revizyonu
**Commit'ler `e15356e`, `390c162`, `376d687`, `9d0fbc0`, `ac8bf72` (2026-06-04 → 06-05).**

- **Ne:** kokpit verisi yalnızca kendi sekmesi açıldığında tembel yüklenir; **kendi barındırdığımız bir PDF.js worker'ı** (harici CDN bağımlılığı yok); oturumlar arası kalıcı olan ve **sonraki kuyruk makalelerini önceden getiren**, tarayıcı Cache Storage içinde **kalıcı bir PDF önbelleği** (`pdfCache.js`, 107 satır); profil çekme işlemiyle paralel çalışan tek bir yalın RPC ve bloklamayan bir kabuk etrafında yeniden kurulan kuyruk.
- **Neden:** sayfa yükleme süresi ve Supabase **veri çıkışı (egress)**, ücretsiz katmandaki bağlayıcı kısıtlardı; görüntüleyici en ağır ekrandır.
- **Ödünleşim:** çok daha az gidiş-dönüş ve aktarılan bayt karşılığında daha fazla istemci tarafı önbellekleme/eşgüdüm karmaşıklığı — bu, uygulamanın ücretsiz katman ömrünü doğrudan uzatır.

---

## Mevcut ön yüz kod tabanı (bugün yayında olan)

| Dosya | Satır | Rol |
| --- | --- | --- |
| `utils/PdfTextScanner.js` | 2.323 | PDF metin katmanı eşleştirme, tablo bölgesi tespiti, tıklama çözümleme |
| `index.css` | 2.970 | Tüm uygulama stili, açık/koyu tema |
| `pages/Annotate.jsx` | 1.163 | Merkezi orkestratör: veri çekme, üst çubuk, görünüm yönlendirme |
| `components/PdfViewer.jsx` | 939 | react-pdf gösterimi, yakınlaştırma, kaydırma, katman boyama |
| `components/FoodAutocomplete.jsx` | 664 | Normalizasyonla yerel + uzak yiyecek sıralaması |
| `utils/annotateHelpers.js` | 574 | Saf yardımcılar: biçimlendiriciler, yük normalizasyonu, pipeline hunisi |
| `utils/EvidenceLocations.js` | 439 | Kanıt-kaynağı koordinat yardımcıları |
| `components/NutrientAutocomplete.jsx` | 334 | Besin sıralama + seçim |
| `src/views/` içindeki 8 görünüm | ~1.170 | Queue, Approval, Dashboard, AllPapers, Pipeline, Suggestions×2, ReviewerAdmin |
| Bileşenler, hook'lar, testler | kalan | `NutrientPopover`, `AiDetailPanel`, `EvidenceStrip`, `PayloadSummary`, hook'lar, `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225) |

## Bunun neden önemli bir çalışma gövdesi olduğu

Ön yüz, **~13.500 satır yayında olan React** kodudur ve projenin tek en zor arayüz problemini — keyfi bilimsel PDF'lerde güvenilir, tabloyla sınırlı, koordinat-doğru vurgulama — görüntüleyici ve tarayıcıya yapılan **27 commit** boyunca soğurmuştur. Ayrıca tüm insan-döngüde pipeline'ını kullanılabilir kılan yapay zekâ-doğrulama iş akışını ve uygulamayı ücretsiz katman sınırları içinde tutan geç bir performans turunu da taşır. Bu, her makale için her etiketleyicinin ve gözden geçirenin kullandığı yüzeydir.
