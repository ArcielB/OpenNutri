# OpenNutri Yapay Zeka / Algoritma Ana Savunma Notları

## Slayt 01 — Başlık ve rol çerçevesi
Modellerle değil, sistem iddiasıyla başla. Projenin şimdiden tek döngü olarak çalıştığını söyle: arama, filtreleme, edinim, anotasyon ve geri besleme kullanımı.

## Slayt 02 — Problemin tanımı
Problemi üç baskı tanımlar: literatür dağınıktır, edinim pahalıdır ve Türkçe kapsam daha zayıftır. Bu yüzden erişim kalitesi anotasyondan önce önemlidir.

## Slayt 03 — Sistemin kimliği
Bu slaytı ne sunduğunuzu ve ne sunmadığınızı söylemek için kullanın. En iyi cümle: uzman anotasyonundan beslenen ve ondan öğrenen bir erişim sistemi sunuyoruz.

## Slayt 04 — Mimari haritası
Bu şekli soldan sağa yavaş anlatın ve sonra döngüyü kapatın. Sonraki slaytlar ayrıntılandığında buna geri dönün.

## Slayt 05 — Yapay zeka için veritabanı kesiti
Yapay zeka katmanının yalnızca paper kayıtlarını kullanmadığını vurgulayın. Arama kanıtı tablolarına ve etiket kanıtı tablolarına da dayanır.

## Slayt 06 — Kaynak stratejisi
Her kaynağın farklı bir açığı kapattığını açıkça söyleyin. Dil ayrımı kozmetik değildir; source prior'ları, query phrase'leri ve arama sırasını değiştirir.

## Slayt 07 — Sorgu üretim mantığı
Kurul, sorguların kısmen seed kısmen öğrenilmiş olduğunu duymalı. Phrase havuzu, sistemin tek bir phrase setine sıkışmaması için küçük bir exploration bölümü tutar.

## Slayt 08 — Görev sıralaması
Pair score'lar source-template-term performansını yakalar. Batch score'lar tam query batch'i yakalar. Statik öncelik, öğrenilmiş geri beslemenin üstündeki açık dil politikası katmanıdır.

## Slayt 09 — İlk geçiş filtresi
Arama kapısının bilinçli olarak ucuz ve toleranslı olduğunu vurgulayın. Eşik negatiftir çünkü bu kapı son karar katmanı değildir.

## Slayt 10 — Ana sıralama katmanı
Sıralama hikâyesinin çekirdeği budur: birkaç kanıt ailesinden gelen toplamsal puanlama. Tek bir sinyal tek başına makaleye karar vermez.

## Slayt 11 — Embedding tasarımı
Hangi embedding'lerin kullanıldığını sorarlarsa tam olarak şöyle cevap verin: İngilizce all-MiniLM-L6-v2, Türkçe/çok dilli paraphrase-multilingual-MiniLM-L12-v2. Sonra embedding'lerin meta veri puanlamasını desteklediğini, sıralamanın geri kalanını değiştirmediğini söyleyin.

## Slayt 12 — Etiket semantiği
Bu slayt tam olarak neyin eğitim verisine dönüştüğünü cevaplar. Ham sayılar yerine görünen son durumu vurgulayın ve çatışmaların bilinçli olarak dışlandığını söyleyin.

## Slayt 13 — Aktif geri besleme döngüsü
Döngünün uygulanmış mı yoksa sadece sinyal topluyor mu olduğunu sorarlarsa şöyle cevap verin: uygulanmış, toplu güncelleniyor ve sonraki çalıştırmaları şimdiden değiştiriyor.

## Slayt 14 — Operasyonel döngü
Bu slaytı projenin yalnızca kod modülleri değil, çalışan bir süreç olduğunu kanıtlamak için kullanın.

## Slayt 15 — Arayüz neden yapay zeka için önemlidir
Arayüz, insan kanıtının yapılandırılmış veriye dönüştüğü yerdir. En güçlü üç uygulama detayı regex tabanlı PDF eşleştirme, tıklama fallback mantığı ve search-session telemetrisidir.

## Slayt 16 — Kapsam disiplini
Bu sizin koruma slaydınızdır. En güvenli cümle şudur: mevcut sistem geri besleme güdümlü istatistiksel uyarlama ile öğreniyor, ancak henüz eğitilmiş bir sınıflandırıcı değil.

## Slayt 17 — Ana savunma iddiaları
Tartışma dağılırsa bu üç iddiaya geri dönün. Sonra tek bir somut uygulama detayıyla cevap verin.

## Slayt 18 — Ek ayırıcı
Bu slaytı yalnızca geçiş için kullanın. Uzun anlatmanıza gerek yok.

## Slayt 19 — Dil stratejisinin ayrıntısı
Kısa cevap şudur: kaynaklar, ifadeler ve öncelikler yeterince farklıdır; EN ve TR'yi birleştirmek kontrolü azaltır ve muhtemelen Türkçe kapsamı zayıflatır.

## Slayt 20 — Tam eşikler
Bu slaytı yalnızca kurul tam sabitleri sorarsa kullanın. Aksi halde sistemi toplamsal ve eşik tabanlı olarak özetleyin.

## Slayt 21 — Search-term ranking cevabı
Search term'lerin ML veya LLM ile mi sıralandığını sorarlarsa hayır deyin: feedback güdümlü istatistiksel puanlama ve elle tasarlanmış sıralama formülleriyle sıralanırlar.

## Slayt 22 — Phrase dışı feedback
Terimler dışında neyin öğrendiğini sorarlarsa şöyle cevap verin: pair score'lar, batch score'lar, concept score'lar ve source prior'lar.

## Slayt 23 — Edinim yolu
Bir paper'ın gerçekten kullanılabilir olduğunu nasıl bildiğinizi sorarlarsa şöyle cevap verin: meta veri kabulü yeterli değildir; proje PDF'yi getirir ve son kabulden önce tam metni doğrular.

## Slayt 24 — Arayüz ayrıntısı
Buradaki en iyi yapay zeka odaklı cümle şudur: arayüz, insan kanıtının yapılandırılmış veriye ve telemetriye dönüştüğü yerdir.

## Slayt 25 — Çalıştırma özeti uyarısı
Bu slaytı ham sayıları savunmak için değil, titizlik göstermek için kullanın. Aşama sayıları metadata_pass'e kadar gerçektir, ancak bu manifest 12 metadata-pass adayı terminal sonuç olmadan bırakır.

## Slayt 26 — Son Soru-Cevap slaytı
En güvenli üç cümle şunlardır: geri besleme döngüsü uygulanmıştır ama toplu güncellenir; search-term ranking istatistikseldir ve LLM tabanlı değildir; sıralama katmanı toplamsaldır.
