# Günlük metinlerin teknik dayanakları

Bu dosya düzenleme ve teknik savunma içindir; basılı deftere eklenmesi gerekmez.
Kaynaklar uygulamanın bu özelliklere sahip olduğunu gösterir. Öğrencinin ilgili
işi hangi gün, kaç saatte veya tek başına yaptığını göstermez.

Detaylı revizyonda Büşra örneğine yaklaşmak için birinci tekil şahıs kullanıldı.
Bu cümleler doğrulanmış kişisel beyan değil, öğrenciye sunulan anlatım taslağıdır.
Basılı bilgi sayfası da bu ayrımı açıklar. Gerçek görev paylaşımına göre anlatım
geliştirme, entegrasyon, test veya inceleme olarak düzeltilmelidir.

Temel kapsam: `apps/nutrition-app/`. Aşağıdaki `lib/`, `test/` ve `android/` yolları
bu dizine göredir. Besin veri seti üretimi, araştırma hizmetleri ve etiketleme
uygulaması günlük çalışmalara eklenmemiştir. Destek servisleri mevcut bağımlılık
olarak anlatılmıştır; bunları öğrencinin yazdığı varsayılmamıştır.

| Gün | Teknik dayanak | Özellikle korunan sınır |
| --- | --- | --- |
| 01 | `README.md`, `lib/screens/today_screen.dart` | Kapsam yalnızca mobil uygulama; kurum toplantısı/oryantasyon uydurulmadı. |
| 02 | `pubspec.yaml`, `android/app/build.gradle.kts` | Android öncelikli geliştirme; diğer platformlarda çalıştığı iddia edilmedi. |
| 03 | `lib/main.dart`, `lib/state/app_controller.dart`, `lib/services/local_store.dart` | Dış servis hazırlığı yerel günlük açılışından ayrıdır. |
| 04 | `lib/screens/home_shell.dart`, `lib/theme/app_theme.dart`, `lib/widgets/day_header.dart` | Beş ana sekme; diyet ekranı ayrı bir bağlantıdır. |
| 05 | `lib/models/food.dart`, `lib/models/diary.dart`, `lib/models/voice_resolution.dart` | Kaynak kimliği, miktar ve kayıt anındaki besin değerleri ayrı tutulur. |
| 06 | `lib/services/core_api_client.dart` | API entegrasyonu; Core veri tabanını geliştirme iddiası yok. |
| 07 | `lib/screens/food_search_screen.dart`, `test/app_regression_test.dart` | Geciken/temizlenen arama yanıtları güncellik kontrolüyle ele alınır. |
| 08 | `lib/widgets/entry_detail_sheet.dart`, `lib/widgets/serving_sheet.dart` | Besin değiştirme, miktar değiştirmeden farklıdır. |
| 09 | `lib/models/diary.dart`, `lib/models/food.dart`, `test/diary_test.dart` | Satın alınan ağırlık yalnızca tam besin bağlantılı kullanılabilir katsayıyla çevrilir. |
| 10 | `lib/services/local_store.dart`, `test/diary_test.dart` | SharedPreferences JSON; bulut eşitleme/geri yükleme yok. |
| 11 | `lib/state/app_controller.dart`, `test/controller_batch_test.dart` | İyimser görünüm, sıralı yazma ve aynı işlemi tekrar saymama. |
| 12 | `lib/widgets/entry_detail_sheet.dart`, `lib/screens/voice_log_screen.dart`, `test/entry_detail_test.dart` | İptal eski kaydı silmez; ekran kapanışı yaşam döngüsüyle uyumludur. |
| 13 | `lib/models/diary.dart`, `test/diary_test.dart`, `test/app_regression_test.dart` | Enerji, besin başına seçildikten sonra toplanır. |
| 14 | `lib/screens/nutrients_screen.dart`, `lib/services/coach_service.dart` | Eksik mikronutrient bağlamı sıfır tüketim/eksiklik tanısı değildir. |
| 15 | `lib/screens/settings_screen.dart`, `lib/state/app_controller.dart`, `test/app_regression_test.dart` | Form senkronizasyonu ilgisiz kullanıcı girdisini ezmemelidir. |
| 16 | `lib/services/voice_recorder.dart`, `lib/screens/voice_log_screen.dart` | Geçici mono 16 kHz WAV; kayıt tamamlanmadan sürekli ses yüklemesi yok. |
| 17 | `lib/services/voice_recorder.dart`, `test/voice_log_test.dart` | 1,6 s son sessizlik; 30 s sınır; süreç ölümünde temizlik garantisi yok. |
| 18 | `lib/services/voice_api_client.dart`, `lib/services/supabase_config.dart` | Anonim oturum, multipart istek, dil/zaman bağlamı; mobilde gizli Gemini anahtarı yok. |
| 19 | `lib/models/voice_resolution.dart`, `lib/screens/voice_log_screen.dart` | Model yanıtı besin ögesi ölçümü değildir; Core ayrıntısı yüklenir. |
| 20 | `lib/screens/voice_log_screen.dart`, `test/voice_log_test.dart` | Bütün öğeler kullanılabilir olmalı; varsayılan 100 g ölçülmüş miktar değildir. |
| 21 | `lib/services/voice_api_client.dart`, `lib/models/personalization.dart` | Kuyruk beklemesi dahil uçtan uca sabit süre garantisi verilmez. |
| 22 | `android/app/src/main/kotlin/org/opennutri/opennutri_app/VoiceLogWidgetProvider.kt`, `android/app/src/main/kotlin/org/opennutri/opennutri_app/MainActivity.kt`, `lib/services/android_widget_bridge.dart` | Soğuk/sıcak başlangıç ve bir kez tüketilen Intent. |
| 23 | `lib/screens/settings_screen.dart`, `lib/screens/voice_log_screen.dart`, `test/widget_setup_test.dart` | Yerleşimi kişi onaylar; kaydetme bitmeden arka planda devam vaadi yok. |
| 24 | `lib/models/personalization.dart`, `lib/screens/diets_screen.dart`, `test/personalization_test.dart` | Altı şablon; mevcut kalori hedefi kullanılır; haftalık menü yok. |
| 25 | `lib/services/coach_service.dart`, `lib/screens/home_shell.dart`, `lib/widgets/daily_coach_card.dart` | Öneri tarihli anlık özettir; her günlük değişikliği model çağrısı değildir. |
| 26 | `lib/screens/coach_screen.dart`, `lib/models/personalization.dart` | Görüşme oturumluk; yalnız açık ifadelerden kalıcı tercih adayları; anlam kuralı model talimatına dayanır. |
| 27 | `lib/screens/oracle_screen.dart`, `test/app_regression_test.dart` | Oracle açılınca yüklenir ve Core aramasına yönlendirir; matematiksel optimum iddiası yok. |
| 28 | `lib/screens/settings_screen.dart`, `lib/screens/voice_log_screen.dart`, `test/widget_setup_test.dart` | Ayrı izinler, kapatma seçeneği ve görünmeyen bileşenin Future hatası. |
| 29 | `test/`, `analysis_options.yaml` | 14 Eylül'de 44 Flutter testi + temiz analiz; tam cihaz/konuşma ölçümü değil. |
| 30 | `pubspec.yaml`, `README.md`, `../../../../docs/consumer_app_audit_2026-09-05.md` | APK 1.1.2+5 kanıtı 5 Eylül denetiminden; mağaza yayını veya yeni kurulum iddiası yok. |

## Eklenen somut ayrıntıların kontrol noktaları

| Gün | Ayrıntı | Kaynaktaki kontrol noktası |
| --- | --- | --- |
| 06–07 | 30 sonuç sınırı, 350 ms gecikmeli arama, ayrı normal/anlamsal istek numaraları | `CoreApiClient.searchFoods`, `FoodSearchScreen._scheduleSearch` ve temizlenen arama regresyonu |
| 09 | 52 × 1,82 = 94,64 kcal; 500 × 0,67 = 335 g; 161 × 3,35 = 539,35 kcal | `test/diary_test.dart` içindeki kontrollü elma/tavuk verileri; gerçek kişi ölçümü değildir |
| 11–12 | Yazma zinciri, son başarılı kopyaya dönüş, 100 → 150 g düzeltmede 52 → 78 kcal | `AppController._persistEntries`, `updateEntries`, `test/controller_batch_test.dart`, `test/app_regression_test.dart` |
| 13 | Energy 52 + özel Atwater 80 = 132; genel Atwater 90 ayrıca eklenmez | `DiaryEntry.calories`, `DailyTotals`, karma enerji regresyonu |
| 14 | 5, 0 ve eksik D vitamini alanı: toplam 5, kapsama 2/3; kalsiyum null | `CoachService._nutrientMetric` ve eksik mikronutrient testi |
| 16–18 | 16 kHz mono WAV, 100 ms seviye örneği, 800 ms başlangıç, -40 dBFS, 30 s kayıt sınırı | `OpenNutriVoiceRecorder`; dedektör testinin varsayılanı 2 s, gerçek kaydedici son sessizlik ayarı 1,6 s |
| 18 | 1 MB, 10 s belirteç, 30 s tüm ses yanıtı; bunlar uçtan uca toplam değildir | `VoiceApiClient._accessToken`, `_resolveVoice` |
| 19–20 | Önce seçilen kimlikler, `Future.wait`, requestId + conceptIndex | `VoiceLogScreen._prepareReview`, `_logAll`, `_ReviewItem` |
| 22–23 | Intent eylemi temizlenir, bekleyen işaret bir kez tüketilir, Toast ve görev kapanışı saklama sonrasındadır | `MainActivity`, `VoiceLogWidgetProvider`, `test/voice_log_test.dart` ve native Intent testleri |
| 24 | Dengeli şablonda 2.000 kcal → P125/C225/F66,7; uygun hedefte P150/C200 | `DietPreset.targetsForCalories`; açıklayıcı hesap, bireysel enerji ihtiyacı ölçümü değildir |
| 25–26 | Tarih ve revizyon kontrolü; altı görüşme mesajı, en fazla 30 kayıtlı tercih | `HomeShell._refreshDailyCoach`, `CoachScreen._conversation`, `AppController.addCoachMemories` |
| 28 | Görünür alan dışındaki FutureBuilder kurulmadan hata dönebilir; özgün Future korunarak `request.ignore()` çağrılır | `SettingsScreen._checkCoreHealth`, `test/widget_setup_test.dart` içindeki offscreen health testi |

Bu ayrıntılar mevcut kod/testlerden çıkarıldı. Belgelenmemiş toplantı, hata ayıklama
oturumu, mentör yönlendirmesi, iş saati veya kişisel cihaz deneyimi eklenmedi.

## Kaynak ve doğrulama ayrımı

- Teknik davranış haritası: [consumer_app.md](../../../../docs/consumer_app.md).
- Tarihli ölçüm/kurulum kanıtı: [5 Eylül denetimi](../../../../docs/consumer_app_audit_2026-09-05.md).
- Bu belge hazırlanırken 14 Eylül 2026 tarihinde `flutter analyze --no-pub` ve
  `flutter test --no-pub --reporter expanded` yeniden çalıştırıldı: temiz analiz,
  44 test başarılı. Yeni telefon etkileşimi veya canlı yapay zekâ çağrısı yapılmadı.
- İncelenen uygulama sürümü: `1.1.2+5`. Belge hazırlanırken uygulama kodu değişmedi.
- İlgili geçmiş: `9406337` (ilk Flutter günlük), `60aaa88` (günlük arayüzü),
  `e82d7ae` (hızlı kayıt/araç takımı), `2f93b18` (kişiselleştirme), `3dab691`
  (denetim düzeltmeleri), `79680cf` (miktar penceresi), `9cc6bf6` (araç takımı
  kurulumu ve model gösterimi). Bu kimlikler gelişim kanıtıdır, devam çizelgesi değildir.
- Önceki değerlendirmede verilen “yaklaşık 40 günlük iş kapsamı” tahmini deftere
  gerçek süre veya kişisel çalışma kanıtı olarak aktarılmadı.

## Doldurulacak veya doğrulanacak bilgiler

Üniversite/bölüm, öğrenci adı/numarası, kurum/adres, sorumlu kişi/unvanı, gerçek
günlük tarihler ve hangi işlerin öğrenciye ait olduğu henüz kullanıcı tarafından
doğrulanmadı. Örneklerdeki kişisel bilgiler, imzalar, kurum isimleri ve tarihler
yeni belgeye aktarılmadı. Resmî kapak ve kurum onayı için ilgili kurumun formu
kullanılmalıdır. Bu çalışma kurumsal staj kabul kararı vermez.
