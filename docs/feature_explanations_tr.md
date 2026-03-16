# OpenNutri — Özellik Açıklamaları

## Kısa (Üst Düzey)

1. PDF işleme + depolama
Nedir: PDF’ler Supabase Storage’da saklanır ve uygulamada görüntülenir.
Nasıl çalışır: UI public URL üretir, React PDF (PDF.js) ile render eder.

2. PDF’de besin öğesi vurgulama
Nedir: Besin öğesi adları PDF içinde vurgulanır.
Nasıl çalışır: PDF metin katmanı taranır, eşleşmeler işaretlenir.

3. Bulanık besin öğesi eşleştirme
Nedir: Arama, küçük yazım/çekim farklarını tolere eder.
Nasıl çalışır: Token normalizasyonu ve puanlama ile en yakın eşleşme bulunur.

4. Besin öğesi hızlı ekleme açılır penceresi
Nedir: Vurgulu besin öğesine tıklayınca değer/birim girme paneli açılır.
Nasıl çalışır: Popover açılır, değer/birim alınır ve mevcut gıda öğesine eklenir.

## Orta (Öğretmen Seviyesi)

1. PDF işleme + depolama
Nedir: PDF’ler merkezi depolamada tutulur ve annotator arayüzünde görüntülenir.
Nasıl çalışır: `papers` tablosu dosya adlarını tutar. UI, Supabase Storage (papers bucket) üzerinden public URL üretir ve `PdfViewer` bileşenine verir.
PDF, `react-pdf` (PDF.js) ile render edilir. Bağlantı `apps/expert-annotator/src/pages/Annotate.jsx` ve `apps/expert-annotator/src/components/PdfViewer.jsx` içindedir.

2. PDF’de besin öğesi vurgulama
Nedir: PDF içinde besin öğesi kelimelerinin görsel vurgulanması.
Nasıl çalışır: Sayfa render olduğunda PDF.js metin katmanı span’ları taranır ve nutrient matcher çalıştırılır.
Eşleşen parçalar `<mark>` ile sarılır ve besin öğesi metadata’sı eklenir.
Mantık `apps/expert-annotator/src/utils/PdfTextScanner.js` dosyasındadır; kısmi kelime eşleşmesini önlemek için sınır kontrollü regex kullanılır.

3. Bulanık besin öğesi eşleştirme
Nedir: Arama, yazım ve çekim varyasyonlarına rağmen doğru besin öğesini bulur.
Nasıl çalışır: Metin normalizasyonu yapılır, tekil/çoğul dönüşümleri uygulanır, parantez içi takma adlar kontrol edilir ve exact/prefix/derived eşleşmeler puanlanır. Bu puanlama, öneri listesindeki seçeneklerin sıralamasını belirler.
Mantık `apps/expert-annotator/src/components/NutrientAutocomplete.jsx` dosyasındadır.

4. Besin öğesi hızlı ekleme açılır penceresi
Nedir: Besin öğesi değerini hızlı girmek için küçük bir panel.
Nasıl çalışır: Vurgulu besin öğesine tıklanınca, metnin yanına konumlanan popover açılır.
Kullanıcı değer ve birim girer, mevcut gıda öğesine ekler.
UI `apps/expert-annotator/src/components/NutrientPopover.jsx` içinde, durum güncellemesi `apps/expert-annotator/src/pages/Annotate.jsx` içinde yapılır.

## Uzun (Tam Açıklama)

1. PDF işleme + depolama
Nedir: Annotator’ın taradığı makaleleri tarayıcıda göstermesi için depolama + render hattı.
Nasıl çalışır: PDF’ler Supabase Storage’da (papers bucket) saklanır ve `papers` tablosunda filename ile referans edilir.
`apps/expert-annotator/src/pages/Annotate.jsx` içinde filename, `supabase.storage.from('papers').getPublicUrl(...)` ile public URL’e çevrilir.
Bu URL `apps/expert-annotator/src/components/PdfViewer.jsx` bileşenine verilir ve PDF `react-pdf` (PDF.js) ile render edilir.
PDF.js metin katmanı sayesinde span’lar taranabilir ve vurgulama yapılabilir.

2. PDF’de besin öğesi vurgulama
Nedir: PDF metninde besin öğesi terimlerinin vurgulanması.
Nasıl çalışır: Temel mantık `apps/expert-annotator/src/utils/PdfTextScanner.js` dosyasındadır.
`buildNutrientMatcher` her besin öğesi için regex üretir, “proximates/minerals” gibi genel grupları atlar.
`buildBoundaryRegex` kelime sınırlarını korur ve kısmi kelime vurgulamalarını engeller.
`highlightNutrientsInTextLayer` her metin span’ını tarar, eşleşmeleri toplar ve eşleşen aralıkları `<mark>` ile değiştirir.
Çakışmalar çözülür; aynı başlangıçta uzun eşleşme önceliklidir.
Tıklama yakalama için `pointerup`/`click` ve `elementsFromPoint`/caret API fallback’leri kullanılır.

3. Bulanık besin öğesi eşleştirme
Nedir: Harf/çekim farklarını tolere eden arama.
Nasıl çalışır: Puanlama mantığı `apps/expert-annotator/src/components/NutrientAutocomplete.jsx` dosyasındadır.
`normalizeText` ve `tokenize` büyük-küçük harf, noktalama ve boşlukları standardize eder.
`normalizeToken` tekil/çoğul ve düzensiz formları ele alır (örneğin mice → mouse).
Parantez içi takma adlar çıkarılır ve ayrıca puanlanır.
`scoreNutrientMatch` exact, alias, prefix ve derived token eşleşmelerine ağırlık verir, eksik tokenları cezalandırır.
Bu sayede harici ML olmadan toleranslı ve güvenilir eşleştirme sağlanır ve öneri seçeneklerinin sıralaması belirlenir.

4. Besin öğesi hızlı ekleme açılır penceresi
Nedir: Vurgulu terimden besin öğesi eklemek için hızlı giriş paneli.
Nasıl çalışır: Popover UI `apps/expert-annotator/src/components/NutrientPopover.jsx` içindedir.
`getBoundingClientRect()` ile tıklanan terimin yanına konumlanır.
Açılırken input’a odaklanır, dış tıklama veya Escape ile kapanır.
Onayda `{id, name, value, unit}` bilgisi döner.
`apps/expert-annotator/src/pages/Annotate.jsx` içindeki `handlePdfNutrientAdd` bu girdiyi mevcut gıda öğesine ekler ve tekrar eklemeyi önler.
